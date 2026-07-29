---
name: weekly-review
description: Run the recurring АвтоЭксперт business review — revenue, client flow, staff check-in, second-location search, and roapp.io financial access. Use when the user says it's review day (пн/вт) or asks to do the weekly АвтоЭксперт check-in.
metadata:
  source: "[REF: tasks/mission-roadmap.md#1a, #3]"
  version: 1.0.0
---

# Weekly Review (АвтоЭксперт)

Structured 30–45 min check-in so attention doesn't only go "where it's boiling over" (see mission-roadmap 1a — reactive management is the named problem this replaces).

## When to run

User signals review day (пн/вт), or asks directly. Not a background/automatic job — no local scheduler runs this; it fires only when asked.

## Inputs

- Current numbers: revenue, client flow (from wherever the user has them — roapp.io export, verbal, notes)
- Any staff/team signal the user has (mood, complaints, departures, competitor poaching attempts — see key-person risk, mission-roadmap 3)
- Status of second-location search (calls to contacts — good spots on Cyprus aren't publicly listed)

## Workflow

1. **Revenue + client flow** — ask for/record the numbers. Level 2 verification (light) unless a figure will drive a financial decision, then Level 3 per AGENTS.md.
2. **Staff check-in** — ask what the user noticed this week. Flag anything touching the key-person risk (manager+admin couple, admin's exclusive control of roapp.io CRM).
3. **roapp.io independent access** — until resolved, ask each cycle: did the user check Настройки → Пользователи/Роли for a separate owner login with full financial-report access? Don't let this quietly drop off — mission-roadmap marks it high priority, blocked only on the user doing it personally (he's the payer, so he can).
4. **Second location** — status of the call-around/search. No date attached to this item; it's tracked here, not forgotten.
5. **Reputation lever** — confirm written смета/акт is going out before work starts on new clients (mission-roadmap 4). Not a review question so much as a standing check.
6. **Log the outcome** — append a dated one-line entry to `tasks/weekly-review-log.md` (create it on first run) so reviews accumulate into a visible trend instead of living only in chat history.

## Guardrails

- Don't invent numbers. If the user doesn't have a figure handy, mark `[PLACEHOLDER: user]` and move on — don't estimate.
- roapp.io access is the user's own action (he's the account payer) — never suggest doing anything that looks like circumventing the admin's role; frame strictly as "owner adds themselves a read-access login."
- This is not a substitute for the CRM work tracked separately in MOTUS_CRM_status.md — different business (АвтоЭксперт vs Motus).
