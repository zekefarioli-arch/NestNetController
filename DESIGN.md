# DESIGN.md

The rules for the panel's look and feel. Distilled from the design rules of Mock O'Clock (same discipline, a different identity): follow them for any change in `frontend/`.

## 0. Context
- Product: the web panel of NestNetController, a home firewall that is **closed by default**. The owner opens groups of devices (family phones, TVs, Echo) and sees at a glance what has internet and what does not.
- User: one adult, mostly on a phone, often at night or in a hurry, sometimes locked out of their own internet. The stakes are real (cutting a camera, a TV mid-film), so the panel must be calm, exact and hard to misread.
- Stack: static HTML, Tailwind (browser build, `static/js/tailwind.js`) and vanilla JS. No build step, **no request to the internet**: the panel has to render on a device that has no internet. Fonts, icons and scripts are served by the panel itself.
- Tone: a quiet instrument panel. It states facts in plain words and never raises its voice.

## 1. Aesthetic direction: the breaker panel
A switchboard in a hallway cupboard: engraved plates, a lever per circuit, a pilot lamp that is lit when the circuit is live.
- The memorable element is the **lever** (section 5). Everything around it is quiet.
- Hierarchy comes from typography, hairline rules and whitespace, not from boxes, shadows or colour.
- Collections are ruled lists, never grids of identical cards.
- Text is left aligned. Line length under 75 characters.
- Never pure white (#FFFFFF) or pure black (#000000), including text on a coloured fill.
- Avoid the generated-page defaults: warm cream with a serif and a terracotta accent, near-black with acid green, hairline broadsheet columns, all-caps eyebrow labels, `A · B · C` meta strings, arrows appended to buttons, emoji as icons, gradients, glassmorphism.

## 2. Typography
- Barlow Condensed (500, 600) for plates (group names), figures and the headline. Barlow (400, 600) for everything else. Two families, two weights each, self-hosted in `static/fonts/` with `font-display: swap`.
- Scale (px): 12 / 14 / 16 / 18 / 24 / 32 / 48 / 64. Body 16 with line height 1.55; figures use `font-variant-numeric: tabular-nums`.
- Sentence case everywhere. No all caps.

## 3. Colour tokens
All colours are CSS variables on `:root` (light) and `.dark`; components never hardcode a colour.
- Light, a painted enamel panel: `--bg #E3E8E2`, `--surface #EDF0EA`, `--ink #15201B`, `--muted #4A5852`, `--border #BAC4BC`, `--lamp #8F4A06` (text), `--lamp-fill #E9A53F`, `--on-lamp #15201B`.
- Dark, the same panel at night: `--bg #11171A`, `--surface #182025`, `--ink #E6EAE4`, `--muted #9AA7A1`, `--border #2B383E`, `--lamp #F0AE4B`, `--lamp-fill #F0AE4B`, `--on-lamp #17130E`.
- Status: `--danger` (#B42318 light, #F97066 dark) only for real errors; `--warning` for the dry-run notice and partial results.
- Amber means one thing: **internet is on**. It is never decoration.
- `--border` is for dividers only (about 1.5:1). Anything that needs a visible boundary (levers, inputs, buttons) uses `--muted`, which meets 3:1.
- Default to the system theme; a manual choice is saved and applied by an inline script in `<head>` so the page never flashes the wrong theme. Both themes must be complete and pass WCAG AA.

## 4. Space, shape, depth
- 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Radius 6px for controls, 10px for containers, a full radius only for the lever. Depth by 1px borders and background shifts; shadows only for toasts.

## 5. The lever
- A recessed track with a sliding slug. Off: slug on the left, track empty. On: slug on the right, track filled with `--lamp-fill`.
- State is never colour alone: slug position, the engraved `I` and `O` on the track, and the words "Internet on" / "Internet off" beside it.
- 44px minimum hit area, a real `<button role="switch" aria-checked>`, keyboard operable, visible focus ring.
- Protected and always-on groups (equipment, cameras, essential devices) have no lever: a lock icon and the words "Always on". The backend refuses to switch them off, so the interface never offers it. Changing the state of a lever is a request to the server; the lever shows a busy state until the server answers and then redraws from the server's answer, never optimistically.

## 6. Layout
- Mobile first. From 1024px two columns, 5/7: the statement and the scenes on the left, the breakers and the activity on the right.
- The page opens with a sentence about the house, built from real data ("The network is closed by default. 3 groups are on."), not with a logo and a button.
- Sections are named by what they hold: "Breakers", "Scenes", "Activity". Activity is a timeline, so its times are the structure.

## 7. Components and states
- Every control defines default, hover, focus-visible, active, disabled and busy.
- Every data view has a loading state (skeleton rows, not a spinner), an empty state (what it is + the next action) and an error state (what happened + a retry).
- One filled primary button per view (sign in). Scenes are the exception to "no boxes": an action has to look pressable, so each scene is a bordered button with a visible "Apply" chip. Never rely on a person guessing that text is a control.
- Labels always visible above inputs. Errors say what to do.

## 8. Icons
- Lucide only, inline SVG, stroke 1.5, `currentColor`; 16px inline, 20px in buttons. Decorative icons are `aria-hidden`; icon-only buttons have an `aria-label`.

## 9. Motion
- 150 to 250ms, ease-out, only to explain a change: the slug sliding, a toast entering, a row opening. No entrance animations on load. `prefers-reduced-motion` turns it all off.

## 10. Accessibility
- Fully keyboard navigable; visible focus ring (2px, offset 2px); semantic HTML first. Toasts are an `aria-live` region. Touch targets at least 44x44px.

## 11. Copy
- Name things by what the person understands: "Internet on", not "allowlist enabled". One name per action through the whole flow: the button, the toast and the activity line say the same thing.
- Errors say what happened and what to do. No apologies, no exclamation marks.

## 12. Process
Propose the structure before coding a screen, build one screen at a time, reuse tokens, and check each screen in light and dark, on a phone and on a desktop, with a headless browser before calling it done.
