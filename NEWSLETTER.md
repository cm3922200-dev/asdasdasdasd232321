# MCSearch Newsletter — Profile Notice

Szablon HTML do wysyłki jako **newsletter** (nie sam Discord / nie spamowy invite).

## Plik
`email-profile-notice.html`

## Subject / preview
- **Subject:** `Your MCSearch profile notice — *|MCNICK|*`
- **Preview text:** `Staff notice for *|MCNICK|* — please review on mcsearch.io`

## Merge field (nick Minecraft)
| Narzędzie | Tag nicka |
|-----------|-----------|
| **Mailchimp** | `*|MCNICK|*` (utwórz merge field `MCNICK`) |
| **Brevo** | zamień `*|MCNICK|*` → `{{ contact.MCNICK }}` |
| **Ręcznie** | zamień `*|MCNICK|*` na konkretny nick |

W liście kontaktów musisz mieć kolumnę / atrybut z nickiem Minecraft (`MCNICK`).

## Jak wysłać (Mailchimp — najprościej)
1. Audience → dodaj merge field **MCNICK** (Text).
2. Zaimportuj listę: email + MCNICK.
3. Campaigns → **Email** → Create → **Code your own**.
4. Wklej całą treść `email-profile-notice.html`.
5. Subject jak wyżej → Send / Schedule.

## Jak wysłać (Brevo)
1. Contacts → atrybut **MCNICK**.
2. Campaigns → Email → Design → **Code your own** / HTML.
3. Zamień wszystkie `*|MCNICK|*` na `{{ contact.MCNICK }}`.
4. Zamień `*|UNSUB|*` na tag unsubscribe Brevo (wstawia automatycznie w stopce kampanii).
5. Wyślij do listy.

## Ważne
- W szablonie **nie ma** linków `discord.gg` (żeby nie wpadało w spam).
- CTA: najpierw `https://mcsearch.io`, potem profil `https://mcsearch.io/profile/*|MCNICK|*`.
- To **nie wysyła się samo** z GitHub Pages — musisz wkleić HTML do narzędzia newslettera.
