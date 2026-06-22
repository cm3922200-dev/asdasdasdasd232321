# mclookup — static site for Cloudflare

Upload **all files in this folder** to your GitHub repo root.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main site |
| `creeper-logo.png` | Logo |
| `suspended.txt` | Suspended usernames list |
| `wrangler.toml` | Deploy config + SPA routing (no _redirects needed) |

## Cloudflare — Workers (Git + wrangler)

1. Push this folder to GitHub (repo root).
2. Cloudflare → Workers & Pages → Connect to Git.
3. Build command: *(empty)*
4. Deploy command: `npx wrangler deploy`
5. Root directory: `/`
6. After Success → Settings → Domains & Routes → add `*.workers.dev` subdomain.

## Cloudflare — Pages (simpler, optional)

1. Push this folder to GitHub.
2. Create → **Pages** → Connect to Git.
3. Framework: **None**, build: *(empty)*, output: `/`
4. You get `https://your-repo.pages.dev` automatically.

## GitHub upload (browser)

1. github.com → New repository → e.g. `mclookup`
2. Add file → Upload files → drag everything from this folder
3. Commit

Do **not** upload the `email/` folder or any `.postmark-token` files.
