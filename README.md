# Motus — motus.cy

Single-page landing site. Plain HTML/CSS/JS, no build step, no dependencies.

- `index.html` — the entire site (styles and script are inline).
- `DESIGN.md` — the design contract. Read before changing anything visual.

## Run locally

```
python3 -m http.server 8000
```
then open http://localhost:8000

## Deploy (Vercel)

1. Push this folder to a GitHub repo (private is fine).
2. On [vercel.com](https://vercel.com), "Add New… → Project", import that repo.
   Framework preset: **Other** (it's a static site — no build command, no output directory
   needed; Vercel will serve `index.html` as-is).
3. Deploy. You'll get a `*.vercel.app` preview URL — check it loads correctly before
   pointing the real domain at it.
4. In the Vercel project → **Settings → Domains**, add `motus.cy` (and `www.motus.cy` if
   wanted). Vercel will show you DNS records to set.
5. Domain is registered at [registry.nic.cy](https://registry.nic.cy) — log in there, find
   the DNS management page for `motus.cy`, and add the records Vercel gave you in step 4
   (usually an `A` record pointing at Vercel's IP, or a `CNAME` for the `www` subdomain).
   DNS changes can take up to 24–48h to propagate, though it's often much faster.
6. Once Vercel shows the domain as "Valid Configuration", `https://motus.cy` is live.

## Known limitations before this counts as fully "production"

See **Known gaps** in `DESIGN.md` — the contact forms don't submit anywhere real yet
(by design, deferred until the CRM pipeline is finalized). Everything else on the page
(copy, links, WhatsApp/Telegram buttons, phone number, address) should be reviewed by the
business owner before going live — this session could not independently verify that the
phone number, address, or Google Maps link embedded in the page are current/correct.
