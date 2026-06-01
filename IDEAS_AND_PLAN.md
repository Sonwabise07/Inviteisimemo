# Invitisimemo — Making it cleaner, simpler & world-class

A practical plan, written against your actual codebase. It's organised so you can
ship the cheap, high-impact things first and leave the bigger bets for later.

---

## What's already strong (keep this)
- The aesthetic is genuinely good — the dark + gold palette is consistent and premium.
- Deep feature set: 23 designs, 20 patterns, 14 effects, personalised links, QR, RSVP, gift registry, reactions, comments, CSV export.
- Solid engineering foundations already in place: CSRF, rate limiting, audit log, migrations, S3-ready uploads.
- The SA-local angle (Umemulo, Lobola, Ndebele, Stokvel, Xhosa/Zulu/Venda patterns) is a real differentiator. Lean into it — nobody global does this well.

The problem isn't capability. It's that **the power is shown all at once**, which makes a simple task (invite people to a party) feel like operating a control panel. The fix is sequencing and restraint, not removing features.

---

## The one principle to design around
Your own create page already says it: **"Make it feel clear before it feels fancy."** Make that the rule for the whole product.

> Every screen should ask the user for the *smallest next thing*, and hide everything else until it's needed.

The pack-locking change we just shipped is the first example: pick a vibe → the entire design panel collapses into one "✓ style set for you" line → the user only types names and dates. Apply that same move everywhere.

---

## Tier 1 — Quick wins (hours, not days)

1. **Default to packs, make "from scratch" the side door.**
   Most people don't want to choose a font. Land them on the pack grid; "Start from scratch" stays available but small. (Pack-locking is already in — this is just emphasis.)

2. **Cut the create form to 3 visible steps, not 6.**
   Group it as **Who & What** (host, event, date, venue) → **Look** (pack, locked) → **Extras** (music, photos, gifts, programme — all optional, collapsed by default). Six expandable sections reads as "six things I must do."

3. **One primary button per screen.**
   On `created.html` and `subscribe.html` there are now two priced options — good — but make the *recommended* one visually dominant and the other quieter. Two equal gold buttons cause hesitation.

4. **Replace jargon with guest-language.**
   "Personalised links", "broadcast", "ITN" → "Invite each guest by name", "Message everyone", (hide the technical word entirely). Write for the aunty planning a 21st, not a developer.

5. **Autosave drafts.**
   The create form is long; a refresh or a phone call mid-way loses everything. Save to `localStorage` on input, restore on load. Cheap, huge relief.

6. **Show the price difference in plain terms.**
   "Hosting one event? R15. Hosting a few this year? R99/mo pays for itself after 7 invites." Let the maths make the choice for them.

---

## Tier 2 — Medium effort (this is where "world-class" lives)

7. **A real mobile-first create flow.**
   We've done a responsive CSS pass, but the *structure* is still desktop-shaped (a long scroll). Phones want a **wizard**: one question per screen, a fat "Next" button pinned to the bottom, a progress bar at the top. ~80% of invite links get opened on a phone — the host is probably on one too.

8. **A "preview as a guest" that feels like the real thing.**
   You have `/preview-draft`. Make it a phone-framed mockup the host can flick through before paying. Seeing the finished invite is the single best motivator to pay — sell the outcome, not the feature list.

9. **Make sharing the centre of gravity.**
   The product's growth engine is the invite itself: every guest who opens one is a potential host. So:
   - Add a small, tasteful "Made with Invitisimemo" footer on published invites (removable on subscription — another reason to upgrade).
   - One-tap WhatsApp share is already there; add "share to status" and a pre-written message with the event name and date filled in.
   - After a guest RSVPs, show "Hosting something soon? Make your own →".

10. **Guest experience polish.**
    - RSVP in **one tap** from the personalised link (name pre-filled), with "+1?" as a second tap, not a form.
    - A calendar "Add to Google/Apple Calendar" button — guests forget; you reduce no-shows.
    - Live countdown + "23 people coming" social proof.

11. **Tighten the visual system.**
    23 designs is a lot to maintain and to choose from. Audit them: keep the 12 that look genuinely distinct and premium, retire near-duplicates. Fewer, better options = a cleaner picker and less to QA. Same logic for 20 patterns.

12. **Trust & polish on the money screens.**
    Add the PayFast logo, "cancel anytime", and a one-line refund/terms note near the pay buttons. On a R15–R99 South African purchase, visible trust signals materially lift conversion.

---

## Tier 3 — Bigger bets (roadmap, when the basics are tight)

13. **Templates marketplace / seasonal packs.** Matric season, festive season, Heritage Day, Valentine's. Drop a themed pack the week before — gives people a reason to come back.
14. **Host dashboard insights.** "32 opened, 18 yes, 4 maybe, 6 haven't viewed" with a one-tap "nudge the 6". Hosts love feeling on top of it.
15. **WhatsApp-native RSVP.** In SA, WhatsApp *is* the internet. A WhatsApp number that collects RSVPs and replies automatically would be a category-defining feature.
16. **Vendor tie-ins.** Cake, décor, catering, MCs as optional add-ons on the invite — a revenue line beyond the invite fee.
17. **Multi-language UI.** isiZulu / isiXhosa / Afrikaans toggle. You already greet guests in multiple languages; extend it to the whole host experience.

---

## Concrete near-term order
1. Tier-1 items 1–6 (a weekend).
2. Tier-2 item 7 (mobile wizard) and item 9 (sharing loop) — these move the metrics most.
3. Item 11 (design audit) to reduce maintenance drag.
4. Then revisit Tier 3 with real usage data.

## How to know it's working
Track four numbers:
- **Create → publish rate** (how many started invites actually get paid for & published)
- **Invite open rate** (guests who open the link)
- **Guest → new host conversion** (the viral loop)
- **Single-invite vs subscription mix** (tells you who your users really are)

If create→publish is low, the form is still too heavy. If guest→host is low, your sharing loop isn't visible enough. Let those two numbers drive what you build next.
