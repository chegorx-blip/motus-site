# Motus — Design Contract

This file documents the design system actually implemented in `index.html`. It is not a
proposal — it reflects an already-approved brand (Brandbook v0.3, `~/Desktop/MOTUS/`) and an
already-built landing page. Treat every value below as fixed. If a new section is added, reuse
these tokens; do not invent new colors, fonts, radii, or shadow values without updating this
file first.

## Brand

Motus imports verified used cars from Japan to Cyprus and sources vehicles locally. Positioning:
"Born from a garage, not a used-car lot" — mechanic-led, not sales-led.

**Voice principles** (from `MOTUS_Positioning_and_Story.docx` / `MOTUS_Website_Brief.docx`,
carried into every section of this site):
- No hype, no CAPS, no emoji, no countdown timers, no fake urgency.
- Honesty over persuasion: urgency comes from real catalog status (`In stock` / `On the way`),
  not manufactured scarcity.
- Claims are backed by process (inspection, guarantee), not adjectives.

## Color — "Deep Cyprus"

```
--pine:   #21463A   primary panel / brand green
--ink:    #14201A   near-black text, dark-mode background
--bronze: #B4894E   accent — CTAs, focus rings, logo dot. Used sparingly (≤5% of a screen).
--sage:   #4A6D5E   muted text on light backgrounds
--stone:  #E9E4D9   muted text on dark backgrounds, light-mode borders base
--paper:  #F6F3ED   light-mode background, text-on-panel
```

Semantic tokens (`:root`, with light/dark overrides driven by `prefers-color-scheme` and a
`data-theme` attribute for manual override):

| Token | Light | Dark |
|---|---|---|
| `--bg` | paper | ink |
| `--bg-panel` | pine | pine |
| `--text` | ink | paper |
| `--text-muted` | sage | stone |
| `--accent` | bronze | bronze |
| `--surface` | `#fff` | `rgba(246,243,237,.045)` |
| `--border` | `rgba(74,109,94,.28)` | `rgba(233,228,217,.16)` |

Bronze is the only accent color in the system. It never appears as a large fill — only CTAs,
the logo dot, focus outlines, active tab underline.

## Typography

| Role | Family | Weight | Notes |
|---|---|---|---|
| Body | IBM Plex Sans | 400 / 600 | Self-hosted, subset for Latin + Cyrillic + Greek |
| Headings (h1–h3) | **Golos Text** | 700 | Loaded via Google Fonts. Replaces Space Grotesk, which has no Cyrillic glyphs and silently fell back to a system font on the RU site — fixed 2026-08-05. |
| Labels / mono (`.mono`, eyebrows, tabs) | **IBM Plex Mono** | 400 | Loaded via Google Fonts. Replaces Space Mono for the same Cyrillic reason. |

Scale (mobile → desktop via `clamp()`, not fixed breakpoint jumps):
- H1: `clamp(32px, 4.6vw + 14px, 52px)`, line-height 1.08
- H2 (section titles): `clamp(26px, 3vw + 14px, 36px)`
- H2 (small, e.g. modal): `clamp(22px, 2.4vw + 12px, 28px)`
- Eyebrow/mono label: `clamp(8.5px, 2.4vw, 11px)`, letter-spacing `clamp(0.06em, 1.6vw, 0.18em)`
- Body: 15px / 1.65 line-height
- `.mono` labels: 11px, uppercase, letter-spacing 0.18em

`text-wrap: balance` on all headings.

## Layout

- Container: `max-width: 720px` (`.wrap`), `1120px` for wider sections (`.wrap-wide`, widened 2026-08-06
  from 960px — on very wide monitors (2560px+) the old 960px column left excessive dead margin on
  both sides; also raised `h1.headline`'s clamp max from 52px to 42px in the same pass, because past
  the `wrap-wide` cap the text column stops growing while `vw`-based font size kept growing, so wide
  screens got an oversized heading crammed into a fixed-width column and wrapped badly)
- Horizontal padding: `24px`
- Breakpoints in use: `460px, 480px, 520px, 640px, 860px` (mobile-first; `860px` is the main
  hero two-column threshold, everything below is single-column)
- No fixed 12-column grid — sections use flex/grid ad hoc per component, always keyed to the
  container width above

## Components

- **Buttons** (`.btn-primary`): bronze fill, ink text, `border-radius: 4px`, subtle shadow
  (`0 4px 14px rgba(20,32,26,.3)`), `filter`/`transform` transition on hover — no color-swap
  hovers.
- **Cards / panels**: `border-radius: 3px–4px` for tight components (buttons, tags),
  `15px–18px` for larger panels (modal, popovers). No large-radius "soft SaaS" cards.
- **Modal** (`.request-modal`): centered panel, backdrop, tab switcher (Japan/Cyprus intent),
  closes on Escape/backdrop click. Full-bleed on screens ≤640px.
- **Chat FAB**: bottom-corner floating button expanding to a small menu (WhatsApp/Telegram).
- **Language switch**: text buttons, bronze underline for active state — not a dropdown.

## Motion

- Standard transition duration: **0.18s–0.2s**, `ease`. Slightly longer (0.4s–0.6s) only for
  hero entrance and modal open/close.
- Hero elements animate in once on load (`opacity` + `translateY`), staggered ~120ms apart —
  never repeats, never re-triggers on scroll.
- Ken Burns slow zoom on the hero photo only (15s loop) — the one exception to "no ambient
  motion," used because it's a real product photo, not decoration.
- `prefers-reduced-motion: reduce` is respected globally (`transition: none !important`).
- No parallax, no scroll-jacking, no floating decorative shapes.

## What NOT to do (generic-AI-design guardrails)

- No purple/blue gradients — this is a two-tone brand (pine + bronze), full stop.
- No glassmorphism, no glow effects.
- Bronze accent stays under ~5% of any screen's area — it is not a second primary color.
- No countdown timers or fabricated urgency copy, per brand voice.
- No stock-photo hero — the hero image/video is real inventory, not lifestyle stock.

## Site architecture & content (added 2026-08-06, from owner review + reference pass)

References used for this pass: **Bring a Trailer** (chosen by the owner — plain, information-
dense, trust through specifics, not decoration) for header/nav structure; **Anassa Hotel**
(Paphos) for "one strong photo, almost no text" restraint, which the existing Deep Cyprus
palette already leans toward. Explicitly *not* following the two weakest local competitors
(DriveClick/buycars.cy — cluttered icon-grid, unlocalized pricing widget; generic "photo +
headline + 2 buttons" template shared by most Cyprus import dealers).

**Header, two bars (mirrors BaT's structure, not its content):**
- Black top bar: logo, primary nav, language switch (already correct — plain text, bronze
  underline, not a flag dropdown), and a visible link to the request page (bronze weight,
  equivalent to how BaT prints "Submit a Vehicle" — not buried).
- White second bar, topic tabs: "Почему именно мы" (see differentiation note below), "Виды
  оплат", and **one slot intentionally left open** for whatever topic the deeper market/model
  research surfaces as worth its own tab — do not fill this speculatively.

**Hero must carry both services, not just Japan import.** Currently only "Verified cars from
Japan…" — needs a visible, non-buried second thread for Cyprus local sourcing ("need a car
now, don't want to wait on shipping — we source locally too"). Whether that's a hero subline,
a second CTA, or a dedicated strip below the fold is an implementation call — the requirement
is visibility, not a specific placement.

**"Why us" needs real differentiation, not the current 3 generic claims.** Verified competitor
copy (Japan Motors, DriveClick, others) already says "inspected / warranty / transparent
price" near-verbatim — keeping those three claims as the *entire* differentiation section reads
identical to every competitor. Fold in something competitors don't say: the AutoExpert
ownership/partnership angle below is the strongest candidate.

**AutoExpert partner-pricing mention.** Motus's owner also owns AutoExpert (service/tuning
garage, Limassol) — Motus buyers get some of the best prices on Cyprus for post-purchase work
(ceramic coating, polishing, JDM infotainment "region change," etc.) through that ownership.
State this compactly and vividly (one strong line/card), not as an exhaustive service list —
overwhelming detail was explicitly ruled out. Whether "we own both companies" is said outright
or softened to "partner pricing" is an open copywriting call, not decided yet.

**Request flow becomes a standalone page, not the current modal.** Existing `.request-modal`
(Japan/Cyprus tab switcher, per-intent field groups) already has the right internal logic —
promote it to its own route (e.g. `/order`) instead of a same-page modal, because it must also
work as a cold-open destination: shared via direct link or QR code to people who've never seen
the homepage, so it can't assume any prior context. Requirements for that page:
- First interaction is the intent choice (Japan import vs. Cyprus search) — genuinely different
  field sets per path, confirmed explicitly by the owner, not one shared form.
- The form should surface what the client is *getting* while they fill it in — included
  services, bonuses, anything free — not just collect fields silently. It should read as
  selling, not just intake.
- Fast and simple over clever — no unnecessary steps, no login/account system (there's no
  ongoing account relationship to support, unlike BaT's bidding/watchlist mechanics — adding
  auth here would be pure unneeded complexity).
- Must support a `?src=` style query tag per traffic source (QR at reception, a future QR at a
  parts shop, etc.) so visits can be attributed later once analytics is live.

**Form backend:** submissions go through one decoupled endpoint (not hard-wired straight into
a spreadsheet API from the client) so the destination can change later — currently the target
is the "MOTUS CRM — Рабочая" Google Sheet's "Заявки" tab (where staff already look), with
Bitrix24 (free tier, chosen 2026-08-06 for lead/pipeline management) as the likely next
destination once connected — swapping should mean reconfiguring the endpoint, not rebuilding
the form.

**Analytics:** Google Analytics (chosen over a cookieless paid alternative — accepted the
cookie-consent-banner tradeoff) plus Vercel Web Analytics/Speed Insights (scripts already added
to `index.html`, awaiting the owner enabling both in the Vercel dashboard).

## Known gaps (tracked, not silently fixed)

- **Form submission is not wired to a backend yet.** Both the quick-form and the detailed
  request modal currently just show a success state locally (see comments in the `<script>`
  block). Target: a decoupled endpoint → "Заявки" tab in the MOTUS CRM sheet (see above),
  deferred until that pipeline is built (separate task).
- **Request modal needs to become the standalone `/order` page** described above — not done yet.
- **Hero/why-us copy still needs the content changes above** (dual-service visibility,
  differentiated why-us, AutoExpert partner line) — not yet written into `index.html`.
- **Header not yet restructured** into the black-bar/white-bar layout described above.
- No cookie-consent banner yet for Google Analytics — required once GA is actually added (EU/
  Cyprus, GDPR).
- Hero photo/video are embedded as base64 inside `index.html` for portability; consider moving
  to hosted files if the page weight becomes a problem (currently ~1MB total).
