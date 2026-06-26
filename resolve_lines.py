#!/usr/bin/env python3
"""
Resolve previous usernames in lines.txt to current Mojang names.
Outputs current.txt and merges current names into suspended.txt.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINES_FILE = ROOT / "lines.txt"
CURRENT_FILE = ROOT / "current"
SUSPENDED_FILE = ROOT / "suspended.txt"
CACHE_FILE = ROOT / "name-cache.json"
REPORT_FILE = ROOT / "resolve-report.txt"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)
NOTE_RE = re.compile(r"\([^)]*\)")
SEPARATOR_RE = re.compile(r"^-{3,}$")


def clean_username(raw: str) -> str | None:
    name = NOTE_RE.sub("", raw).strip().strip(":-/|")
    name = re.sub(r"\s+", " ", name)
    if not name or name.lower() in ("active mail",):
        return None
    if "@" in name:
        return None
    return name


def split_nicks(nick_part: str) -> list[str]:
    nick_part = nick_part.strip()
    if " / " in nick_part:
        chunks = re.split(r"\s*/\s*", nick_part)
    elif "/" in nick_part:
        left, right = nick_part.split("/", 1)
        left, right = left.strip(), right.strip()
        looks_like_two = (
            re.match(r"^[a-zA-Z][a-zA-Z0-9_]{2,}$", left)
            and re.match(r"^[a-zA-Z][a-zA-Z0-9_]{2,}$", right)
        )
        chunks = [left, right] if looks_like_two else [nick_part]
    else:
        chunks = [nick_part]
    nicks = []
    for chunk in chunks:
        u = clean_username(chunk)
        if u:
            nicks.append(u)
    return nicks


def parse_line(line: str) -> list[tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#") or SEPARATOR_RE.match(line):
        return []
    emails = EMAIL_RE.findall(line)
    if not emails:
        return []
    first_email = emails[0]
    idx = line.lower().find(first_email.lower())
    nick_part = line[:idx] if idx >= 0 else line
    nick_part = EMAIL_RE.sub("", nick_part)
    nick_part = NOTE_RE.sub("", nick_part).strip()
    nick_part = nick_part.replace(":", " ").replace(" - ", " ").replace("-", " ")
    nick_part = re.sub(r"\s+", " ", nick_part).strip(" :-/|")
    nicks = split_nicks(nick_part)
    if not nicks:
        return []
    rows: list[tuple[str, str]] = []
    for nick in nicks:
        for email in emails:
            rows.append((nick, email.lower()))
    return rows


def load_cache() -> dict[str, dict]:
    if CACHE_FILE.exists():
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        # migrate old string cache
        if raw and isinstance(next(iter(raw.values())), str):
            return {
                k: {"current": v, "status": "cached", "uuid": None}
                for k, v in raw.items()
            }
        return raw
    return {}


def save_cache(cache: dict[str, dict]) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def fetch_current_name(username: str) -> tuple[str, str, str | None]:
    """Return (current_name, status, uuid). status: ok|not_found|error"""
    url = "https://api.ashcon.app/mojang/v2/user/" + urllib.parse.quote(username)
    req = urllib.request.Request(url, headers={"User-Agent": "MCLookup-Resolver/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        current = (data.get("username") or username).strip()
        uuid = data.get("uuid")
        return current, "ok", uuid
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return username, "not_found", None
        return username, f"error_{e.code}", None
    except Exception as e:
        return username, f"error_{e}", None


def consolidate_by_email(
    entries: list[tuple[str, str]], cache: dict[str, dict]
) -> None:
    """If one email maps to multiple nicks, share resolved current name via UUID."""
    by_email: dict[str, list[str]] = {}
    for user, email in entries:
        by_email.setdefault(email, []).append(user)

    for email, users in by_email.items():
        uuid_to_current: dict[str, str] = {}
        for user in users:
            info = cache.get(user, {})
            if info.get("status") == "ok" and info.get("uuid"):
                uuid_to_current[info["uuid"]] = info["current"]

        if not uuid_to_current:
            # same email, one nick resolved with a rename — apply to not_found siblings
            currents = {
                cache[u]["current"]
                for u in users
                if cache.get(u, {}).get("status") == "ok"
                and cache[u]["current"].lower() != u.lower()
            }
            if len(currents) == 1:
                shared = next(iter(currents))
                for user in users:
                    if cache.get(user, {}).get("status") == "not_found":
                        cache[user] = {
                            "current": shared,
                            "status": "inferred_email",
                            "uuid": None,
                        }
            continue

        for user in users:
            info = cache.get(user, {})
            if info.get("status") != "not_found":
                continue
            # try matching via another nick on same email that shares uuid
            for other in users:
                oi = cache.get(other, {})
                if oi.get("uuid") in uuid_to_current:
                    cache[user] = {
                        "current": uuid_to_current[oi["uuid"]],
                        "status": "inferred_email",
                        "uuid": oi.get("uuid"),
                    }
                    break


def load_suspended() -> set[str]:
    names: set[str] = set()
    if not SUSPENDED_FILE.exists():
        return names
    for line in SUSPENDED_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        n = line.strip()
        if n and not n.startswith("#"):
            names.add(n)
    return names


def main() -> int:
    if not LINES_FILE.exists():
        print(f"Missing {LINES_FILE}", flush=True)
        return 1

    entries: list[tuple[str, str]] = []
    seen_rows: set[tuple[str, str]] = set()
    for line in LINES_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        for user, email in parse_line(line):
            key = (user.lower(), email)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            entries.append((user, email))

    unique_users = list(dict.fromkeys(u for u, _ in entries))
    print(f"Parsed {len(entries)} user+email pairs, {len(unique_users)} unique usernames", flush=True)

    cache = load_cache()
    report: list[str] = []
    renamed = 0
    not_found = 0
    errors = 0

    pending = [
        u
        for u in unique_users
        if u not in cache
        or str(cache[u].get("status", "")).startswith("error")
    ]
    workers = 2 if any(
        str(cache.get(u, {}).get("status", "")) == "error_429" for u in pending
    ) else 12
    delay = 1.0 if workers == 2 else 0.05
    print(f"  Fetching {len(pending)} names ({len(unique_users)-len(pending)} cached), workers={workers}...", flush=True)

    def resolve_one(user: str) -> tuple[str, dict]:
        current, status, uuid = fetch_current_name(user)
        return user, {"current": current, "status": status, "uuid": uuid}

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(resolve_one, u): u for u in pending}
        for fut in as_completed(futures):
            user, info = fut.result()
            cache[user] = info
            done += 1
            if done % 50 == 0:
                save_cache(cache)
                print(f"  [{len(cache)}/{len(unique_users)}] resolved...", flush=True)
            time.sleep(delay)

    save_cache(cache)
    consolidate_by_email(entries, cache)
    save_cache(cache)

    inferred = 0
    resolved = 0
    for user in unique_users:
        info = cache.get(user, {})
        current = info.get("current", user)
        status = info.get("status", "cached")
        if status == "ok" and current.lower() != user.lower():
            renamed += 1
            report.append(f"RENAMED {user} -> {current}")
        elif status == "inferred_email":
            inferred += 1
            renamed += 1
            report.append(f"INFERRED {user} -> {current} (same email)")
        elif status == "not_found":
            not_found += 1
            report.append(f"NOT_FOUND {user}")
        elif str(status).startswith("error"):
            errors += 1
            report.append(f"ERROR {user} ({status})")
        else:
            resolved += 1

    if inferred:
        print(f"  Inferred {inferred} names from shared emails", flush=True)

    current_lines: list[str] = []
    for user, email in entries:
        current = cache.get(user, {}).get("current", user)
        current_lines.append(f"{current}:{email}")

    CURRENT_FILE.write_text("\n".join(current_lines) + "\n", encoding="utf-8")

    suspended = load_suspended()
    before = len(suspended)
    for user in unique_users:
        suspended.add(cache.get(user, {}).get("current", user))
    header = [
        "# MCLookup suspended usernames — one per line (case-insensitive).",
        "# Lines starting with # are ignored.",
    ]
    SUSPENDED_FILE.write_text(
        "\n".join(header) + "\n" + "\n".join(sorted(suspended, key=str.lower)) + "\n",
        encoding="utf-8",
    )

    summary = [
        f"pairs={len(entries)}",
        f"unique_users={len(unique_users)}",
        f"renamed={renamed}",
        f"not_found={not_found}",
        f"inferred={inferred}",
        f"suspended_before={before}",
        f"suspended_after={len(suspended)}",
        f"added={len(suspended) - before}",
    ]
    REPORT_FILE.write_text("\n".join(report) + "\n\n" + "\n".join(summary) + "\n", encoding="utf-8")
    print("Done.", " | ".join(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
