# Auth UI Responsive Audit (Login & Register)

**Status:** ✅ implemented 2026-11-07 with the approved decisions: both 1536×735 and 1280×600, the text floors,
extra compression below 600px, compact phones with safe areas, and full size kept at ≥ 880px. The current
behaviour is in [RESPONSIVE.md](RESPONSIVE.md#height-aware-density-auth-fluid-see-auth_responsive_auditmd).
The analysis below is kept as the record. One deviation: `viewport-fit=cover` is applied only while an auth page
is mounted (`useViewportFitCover`), not in `index.html`, because the Memory Wall doesn't pad for safe areas yet.
**Date:** 2026-11-07
**Scope:** `/login`, `/register` (and `/forgot-password`, which shares the shell)
**Related docs:** [RESPONSIVE.md](RESPONSIVE.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), [ASSETS.md](ASSETS.md) (W1, W2)

## 0. Method and evidence

- **Screenshots used:** `register-old.png`, `register-new.png`, `login-old.png` and `login-new.png` from
  `OneDrive/Pictures/Screenshots/` (they are not in the repo). All four were readable.
- **Code read:** everything under `features/auth/`, the shared UI primitives (`TextField`, `PasswordField`,
  `PhoneField`, `Button`, `Divider`, `TextLink`, `Logo`, `EstablishedTag`), `index.css`, `styles/theme.css`,
  `config/media.ts`, `hooks/useMediaQuery.ts` and `assets/auth.ts`.
- **Measured in a browser:** a production build (built into a temp folder, so the repo and `dist/` were not
  touched), rendered in headless Edge (Playwright) at 25 viewports × 2 pages. I recorded scroll overflow, element
  boxes and computed styles. The figures in this report come from those runs, not from estimates.

### 0.1 What the screenshots actually are (key finding)

All four screenshots are about 1917×920 **device** pixels. Measured against the code (the input `h-12` is 48 CSS px):

| Shot         | Input height (device px) | Device px per CSS px | Rendered at                                   |
| ------------ | ------------------------ | -------------------- | --------------------------------------------- |
| register-old | 60                       | 1.25                 | 1536×735 CSS viewport (Windows 125%, 100% zoom) |
| login-old    | 60                       | 1.25                 | same                                          |
| register-new | 48                       | 1.00                 | same screen at **80 % browser zoom**          |
| login-new    | 54                       | 1.125                | same screen at **90 % browser zoom**          |

I rendered the current build at the zoomed viewports (1920×919 at DPR 1.0 for register, 1707×817 at DPR 1.125 for
login). Both renders match `register-new` and `login-new` to within about 4 px. So:

> **The "new" targets are the current design scaled down uniformly: Register × 0.80, Login × 0.90.** The left hero
> panel looks the same in old and new because it is sized in percentages.

> ⚠️ **Resolution mismatch, needs your confirmation.** The screenshots come from a 1920×1080 panel at 125 % scaling.
> That gives a **1536×864 CSS screen** and a **≈1536×735 browser viewport**. That is not a 1280×720 screen. A real
> 1280×720 screen (100 % scaling, maximised Edge, taskbar visible) leaves only a **≈1280×585–633** viewport. This
> plan targets the stricter case (≥ 1280×600 with no scroll), so it also covers the 1536×735 setup.

## 1. Current UI problems

Measured vertical overflow (`scrollHeight − innerHeight`, in px). "Browser" viewports = screen minus a 48 px taskbar
and about 63 px of browser chrome.

| Viewport                     | Login     | Register  | Notes                                     |
| ---------------------------- | --------- | --------- | ----------------------------------------- |
| 1536×735 (your screenshots)  | 0         | **104**   | register-old shows this scrollbar         |
| 1280×720 (whole screen)      | 0         | **119**   |                                           |
| 1280×633 (browser)           | **76**    | **206**   |                                           |
| 1280×585 (browser + taskbar) | **124**   | **254**   |                                           |
| 1366×657 (browser)           | **52**    | **182**   |                                           |
| 1440×789 / 1600×789          | 0         | **50**    |                                           |
| 1920×969, 2560×1329          | 0         | 0         | fits; large empty bands above and below   |
| 1024×768 (tablet landscape)  | 0         | **71**    |                                           |
| 768×1024 (tablet portrait)   | 0         | 0         |                                           |
| 430×932                      | 0         | **28**    |                                           |
| 390×844 / 390×664 (real)     | 0 / 152   | 132 / 312 |                                           |
| 375×667 / 375×553 (Safari)   | 173 / 287 | 308 / 422 |                                           |
| 320×568                      | 292       | 403       |                                           |
| 844×390 (phone landscape)    | 319       | 449       |                                           |

There is no horizontal overflow at any size.

Problems found:

1. **Register scrolls on every laptop-class viewport** (≤ 800 px tall), including your own screen.
2. **Login scrolls on realistic 1280/1366 browser viewports.** Earlier verification used whole-screen sizes
   (1280×720) instead of the browser content area, so it missed this.
3. **Controls and type are oversized for the viewport height.** Inputs and buttons are fixed at 48 px, inputs use
   16 px text, the register column is 480 px wide, and the logo is 144–160 px wide even on 600-px-tall screens.
4. **Large spacing is reserved for the decorations.** On every landscape viewport under 880 px tall, the column
   reserves **80 px** of bottom padding (`short:pb-20`) so the footer link clears the corner wave.
5. **Only one density step.** The `short` variant (≤ 880 px tall) tightens some gaps, but it does not touch control
   heights, label or input font sizes, field gaps or column width. Between `short` and full size there is a jump of
   about 40 px in the logo and 12 px in the title.
6. **Phones carry a lot of empty space.** Phones get `pt-10 pb-24` (136 px of padding), a 176 px logo and a 40 px
   title, so even Login scrolls on 375×667.
7. **Large desktops** are fine in size, but the content sits in a small island (448 px out of 2560 px). That is
   acceptable, and the brief asks not to grow it much.

## 2. Old vs new comparison

Sizes are in CSS px at your 1536×735 viewport (screenshot px ÷ 1.25).

| Element                  | Register old → new          | Login old → new       |
| ------------------------ | --------------------------- | --------------------- |
| Logo width               | 144 → **≈154** (full tier × 0.8) | 160 → **≈144**   |
| "EST. 1985" text         | 14 → **≈11**                | 14 → **≈12.6**        |
| H1 title                 | 34 → **32**                 | 36 → **≈32.4**        |
| Subtitle                 | 16 → **≈12.8**              | 18 → **≈16.2**        |
| Field label              | 14 → **≈11.2**              | 14 → **≈12.6**        |
| Input height             | 48 → **≈38.4**              | 48 → **≈43**          |
| Input text / placeholder | 16 → **≈12.8**              | 16 → **≈14.4**        |
| Field width              | 432 → **≈346**              | 400 → **≈360**        |
| Primary / Google button  | 48 → **≈38.4**              | 48 → **≈43**          |
| Password hint            | 14 → **≈11.2**              | n/a                   |
| Field-to-field rhythm    | ≈88 → **≈74**               | ≈92 → **≈83**         |
| Footer prompt            | below the fold → visible    | visible (both)        |
| Hero panel               | unchanged (56 % / 44 % split, same crop) | unchanged |
| Corner ornaments         | unchanged size; bottom-right wave now in view | unchanged |

What changes visually: the form column is narrower and denser, more cream shows around it, and all content fits
in the viewport with even top and bottom margins. Alignment, palette and hierarchy stay the same.

⚠️ Copying `register-new` exactly would make labels and the hint **≈11 px** and the input text **≈12.8 px**. That is
below a comfortable reading floor (see §7 and §8). I recommend matching the **density and footprint** of the new
shots while keeping minimum text sizes.

## 3. Root cause analysis

| #   | Cause                                                                                                                                                                                         | Where                                              |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| R1  | Fixed control heights: `h-12` on the field wrapper, `lg: h-12 px-5 text-base` on the button. No height-aware sizing.                                                                          | `TextField.tsx:53`, `Button.tsx:29`                |
| R2  | Input text is fixed at `text-base` (16 px) on every device. It only needs to be 16 px on iOS touch devices, to stop zoom on focus.                                                            | `TextField.tsx:83`                                 |
| R3  | Only one height breakpoint (`short` ≤ 55rem, landscape). The 735 / 657 / 600 px heights all get the same treatment.                                                                           | `index.css:16`                                     |
| R4  | `short:pb-20` (80 px) is always applied under `short`. It overrides the register `compact` `hero-fits:pb-6`, because `short` is declared after `hero-fits` and wins at equal specificity. Measured: pb 80 px at 1280×633 and at 1536×735. | `AuthLayout.tsx:37–40`                             |
| R5  | Bottom-right wave stays `w-36` (144 px) on short screens, which forces R4's clearance.                                                                                                          | `AuthDecorations.tsx:23,37`                        |
| R6  | Column widths `max-w-md` (448) and `max-w-[30rem]` (480) are fixed. The register subtitle bleeds into the padding (`sm:-mx-6`).                                                                | `AuthLayout.tsx:37,40`, `AuthHeader.tsx:63`        |
| R7  | Spacing is a stack of fixed gaps: page `gap-9`/`gap-6`, form `gap-5`/`gap-4`, `AuthForm` `gap-6`/`gap-5`, field `gap-2`, button `mt-1`, header `mt-8`/`mt-6`. Nothing scales with height. | `LoginPage.tsx:13`, `RegisterPage.tsx:13`, `AuthForm.tsx:40,45,56`, `AuthHeader.tsx:30,38`, `TextField.tsx:46` |
| R8  | Logo and title use width breakpoints (`sm:w-56 hero-fits:w-60`, `sm:text-5xl`). Width does not predict the available height.                                                                  | `AuthHeader.tsx:31,46–47`                          |
| R9  | The `short` variant requires landscape (`min-aspect-ratio: 1/1`). Portrait phones never compact, which is intentional per RESPONSIVE.md, but it is the reason for the phone scroll.           | `index.css:16`                                     |
| R10 | Testing gap: "no overflow" was checked at whole-screen sizes (1280×720, 1366×768), not browser viewports.                                                                                     | RESPONSIVE.md, ROADMAP.md                          |

Things that are **not** causes: the hero (`sticky h-dvh`, `object-cover`) is correct, `min-h-dvh` is correct, and
there is no horizontal overflow at any width.

## 4. Responsive design strategy

**Principle:** the form panel's density follows the **available height**. Width only decides the layout (split or
single column).

1. **Layout (unchanged):** split hero/form under `hero-fits` (≥ 1024 px wide and landscape ≥ 4:3). Single column
   otherwise. Keep the 56/44 split and `minmax(30rem, 44%)`.
2. **Density tiers by height**, with fluid interpolation inside each tier:

   | Tier   | Condition (landscape, or any orientation for phones)       | Purpose                                           |
   | ------ | ---------------------------------------------------------- | ------------------------------------------------- |
   | `tall` | height > 880 px                                            | today's full design, capped (does not grow past 1440 px tall) |
   | `mid`  | 721–880 px                                                 | ≈ login-new density                               |
   | `low`  | 600–720 px                                                 | ≈ register-new density (your 1536×735 lands at the top of this tier) |
   | `min`  | < 600 px                                                   | tightest; scrolling is allowed if the content still doesn't fit |

   Spacing and the title interpolate with `clamp(min, calc(a·dvh + b), max)`, so moving between tiers is smooth.
   **Body text, labels and inputs use rem steps, never `dvh`**, so text still grows with browser zoom and user
   font settings (WCAG 1.4.4).
3. **Scope:** all density values become CSS custom properties set on the auth `<main>`. `TextField` and `Button`
   read them **with fallbacks equal to today's values**, so the Memory Wall dialogs (`SaveDesignDialog`,
   `TemplatesDialog`, `SavedDesignsDialog`, `CanvasPanel`) don't change.
4. **Phones (portrait):** compact the header, cut the 136 px of padding to about 48 px, and keep 44 px touch
   controls with 16 px input text. Login fits at ≥ 390×664. Register fits at ≥ 390×844. Smaller phones scroll
   naturally, with nothing clipped.
5. **Landscape phones and short tablets (< 480 px tall):** single column and `min` tier. **Scrolling is the correct
   behaviour here.** A 4-field form cannot fit in 375 px without unreadable text.
6. **Never** add `overflow: hidden` or `h-dvh` to the form column. The column keeps `min-h-dvh` plus normal
   document scroll, so it degrades to scrolling when the keyboard opens, at 200 % zoom, at large user fonts, or when
   errors appear.

## 5. Viewport behaviour matrix

"Browser" = realistic content area. Target sizes are given as control height / title size.

| Resolution (browser viewport) | Layout                 | Tier      | Target                                   | Expected result                                   |
| ----------------------------- | ---------------------- | --------- | ---------------------------------------- | ------------------------------------------------- |
| 1280×720 (≈1280×585–633)      | split 717 / 563        | low / min | 40 px / 28 px                            | Both fit at ≥ 600 px tall. At 585: Login fits, Register within ≈0–20 px (decision D2) |
| 1536×735 (your screenshots)   | split 860 / 676        | low       | 40 px / 30–32 px                         | Both fit, about 40 px margin top and bottom       |
| 1366×768 (≈1366×657)          | split 765 / 601        | low       | 40 px / 29 px                            | Both fit                                          |
| 1440×900 (≈1440×789)          | split 806 / 634        | mid       | 44 px / 34 px                            | Both fit                                          |
| 1600×900 (≈1600×789)          | split 896 / 704        | mid       | 44 px / 34 px                            | Both fit                                          |
| 1920×1080 (≈1920×969)         | split 1075 / 845       | tall      | 48 px / 40–44 px                         | Fit, balanced vertical centring                   |
| 2560×1440 (≈2560×1329)        | split 1434 / 1126      | tall, capped | 48–52 px / 48 px, column ≤ 30rem      | Fit, no further growth                            |
| 1024×768 tablet landscape     | split 544 / 480        | low/mid   | 44 px (touch) / 30 px                    | Both fit                                          |
| 768×1024 tablet portrait      | single column          | tall      | 48 px                                    | Fit (today: fits)                                 |
| 430×932 (≈430×800)            | single column          | phone     | 44 px / 32 px                            | Both fit                                          |
| 390×844 (≈390×664)            | single column          | phone     | 44 px / 30 px                            | Login fits; Register fits only without browser bars, so it scrolls ≈40–60 px |
| 375×667 (≈375×553)            | single column          | phone-min | 44 px / 28 px                            | Login ≈ fits; Register scrolls                    |
| 320×568 (≈320×460)            | single column          | phone-min | 44 px / 26 px                            | Both scroll (cannot fit legibly)                  |
| 844×390 / 667×375 landscape   | single column          | min       | 40–44 px                                 | Scroll; nothing clipped                           |

## 6. Component-level change plan

| File                                                  | Change                                                                                                                                                                                                                           | Risk                                                                        |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `src/index.css`                                       | Add height-tier variants (for example `h-mid`, `h-low`, `h-min`, plus portrait-phone handling). Add an auth scope class with density custom properties per tier (control height, field gap, section gap, padding, title clamp). Keep `hero-fits`, and keep `short` until it is replaced. | Low. Additive                                                               |
| `src/config/media.ts`                                 | No change unless a JS-gated query changes. The hero stays gated by `heroFits`.                                                                                                                                                  | None                                                                        |
| `components/ui/TextField.tsx`                         | Wrapper height → `h-[var(--field-h,3rem)]`. Label gap → `var(--field-label-gap,0.5rem)`. Input text → `var(--field-font,1rem)` with 16 px forced on `pointer:coarse`. Label and hint sizes via variables with today's fallbacks. | Medium: shared with SaveDesignDialog. Fallbacks keep it identical           |
| `components/ui/PasswordField.tsx`                     | The toggle is `size-10` with `-mr-2`. In a 40 px field the 40 px hit area fills the field height, which is fine. Check it doesn't overflow at 38 px; if it does, cap it with `max-h-full`.                                        | Low. Toggle logic untouched                                                 |
| `components/ui/Button.tsx`                            | `lg` size → `h-[var(--control-h,3rem)]` and `text-[length:var(--control-font,1rem)]`.                                                                                                                                            | Medium: `lg` is used in 3 planner places. Fallbacks keep them identical     |
| `features/auth/components/AuthLayout.tsx`             | Apply the auth scope class to `<main>`. Replace the fixed `pt/pb` with variable-driven fluid padding. Remove the `short:pb-20` override. Column width per variant: `max-w-[25.5rem]` login, `max-w-[25rem]` register (tiered).    | Medium. Retest the footer vs wave at every size                             |
| `features/auth/components/AuthDecorations.tsx`        | Bottom-right wave: smaller in the `low` and `min` tiers (≈ `w-28`). Top-right wave and leaves: scale in the `min` tier. This removes the need for 80 px clearance.                                                             | Low. Decorative and `aria-hidden`                                           |
| `features/auth/components/AuthHeader.tsx`             | Logo width tiered (§7). Title → fluid `clamp()` per tone. Subtitle tiered by rem steps. Header gaps → variables. Review the register subtitle bleed `sm:-mx-6` against the narrower column.                                       | Low                                                                         |
| `components/brand/EstablishedTag.tsx`                 | Optional `size` prop (or inherit via a variable) so the auth pages can use 12 px in the low tiers. Other uses (PlaceholderPage) stay the same.                                                                                   | Low                                                                         |
| `features/auth/components/AuthForm.tsx`               | Gaps → `gap-(--auth-field-gap)` / `gap-(--auth-section-gap)`. Remove the `compact`-branch class duplication in favour of variables (`compact` keeps selecting the register value set).                                         | Low                                                                         |
| `components/ui/Divider.tsx`                           | No code change. It inherits the gaps.                                                                                                                                                                                           | None                                                                        |
| `features/auth/components/AuthSwitchPrompt.tsx`       | Text `text-sm` in the low and min tiers (it is `sm:text-base` today).                                                                                                                                                           | None                                                                        |
| `features/auth/components/LoginForm.tsx`              | "Forgot Password?" row gap → a variable. The `-my-2 py-2` hit-area trick stays.                                                                                                                                                 | Low                                                                         |
| `features/auth/pages/LoginPage.tsx`, `RegisterPage.tsx`, `ForgotPasswordPage.tsx` | Page stack gap → a variable. No logic change.                                                                                                                                                       | None                                                                        |
| `docs/RESPONSIVE.md`, `docs/ROADMAP.md`               | Update the auth section, add the tier table, and change the verification list to browser viewports.                                                                                                                              | None                                                                        |

No changes to hooks, validation, routing, assets or tests' expectations. Unit tests query by role or label, so they
are unaffected.

## 7. Recommended design values

The values below are CSS px. `L` = Login, `R` = Register. Text never goes below the floors in the last column.

| Token                     | `tall` (> 880)            | `mid` (721–880)    | `low` (600–720)    | `min` (< 600)      | Phone portrait     | Floor          |
| ------------------------- | ------------------------- | ------------------ | ------------------ | ------------------ | ------------------ | -------------- |
| Logo width                | L 240 / R 192             | L 176 / R 160      | L 144 / R 136      | L 120 / R 112      | L 160 / R 144      | —              |
| EST text                  | 14                        | 12                 | 12                 | 11                 | 12                 | 11             |
| H1                        | L 48 / R 40               | L 36 / R 34        | L 32 / R 30        | L 28 / R 26        | clamp(26, 8vw, 36) | 26             |
| Subtitle                  | L 18 / R 16               | L 16 / R 15        | L 15 / R 14        | 14 / 13            | 15 / 14            | 13             |
| Label                     | 14                        | 14                 | 13                 | 13                 | 14                 | 13             |
| Field / button height     | 48                        | 44                 | L 42 / R 40        | 40                 | 44 (touch)         | 40 (44 touch)  |
| Input text                | 16                        | 15                 | 15 / 14            | 14                 | **16** (iOS)       | 14             |
| Button text               | 16                        | 15                 | 15                 | 14                 | 16                 | 14             |
| Hint / error text         | 14                        | 13                 | 12.5               | 12                 | 13                 | 12             |
| Label → input gap         | 8                         | 6                  | 6                  | 4                  | 6                  | —              |
| Field → field gap         | L 20 / R 16               | L 16 / R 14        | L 14 / R 10        | L 12 / R 8         | 14 / 12            | —              |
| Header → form gap         | L 36 / R 24               | L 24 / R 18        | L 20 / R 14        | 12 / 10            | 24 / 18            | —              |
| OR divider block          | 24 + 24                   | 16 + 16            | 12 + 12            | 8 + 8              | 16 + 16            | —              |
| Column padding y          | clamp(1.5rem, 6dvh, 5rem) | clamp(1rem, 4dvh, 2.5rem) | 1rem–1.5rem   | 0.75rem            | 1.5rem top / 1.5rem bottom | —    |
| Field width (column − px-6) | L 400 / R 432           | L 368 / R 360      | L 360 / R 352      | L 360 / R 352      | 100 % (≤ 400)      | —              |
| Bottom-right wave         | w-44 (3xl w-60)           | w-36               | w-28               | w-24               | w-32               | —              |

Breakpoints: keep Tailwind's width breakpoints and `hero-fits`. Add **height** variants in rem (so they respond to
zoom and user font size): `h-mid` `(max-height: 55rem)`, `h-low` `(max-height: 45rem)`, `h-min` `(max-height:
37.5rem)`, each combined with `(min-aspect-ratio: 1/1)` for desktop. Add a separate portrait-phone variant (`max-width:
40rem`) for the phone column.

Fluid title, for example: `text-[clamp(1.625rem,calc(3.2dvh+0.5rem),3rem)]`. That gives ≈28 at 633, 31.5 at 735,
36.8 at 900 and 48 at ≥ 1350. The rem floor and ceiling keep it zoom-responsive.

Estimated Register stack at the `low` tier: header ≈ 124 + gap 14 + 4 fields ≈ 270 + hint 20 + button 50 +
divider 36 + Google 40 + prompt 32 ≈ **586 px**. That fits a 633 px viewport with about 24 px margins, and is
tight at 600. Login ≈ **470 px**, which fits everywhere ≥ 520 px tall.

## 8. Overflow and accessibility risks

| Risk                                                                                                                                                                       | Handling                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Viewport-unit text doesn't scale with zoom.** At 200 % zoom the dvh value halves.                                                                                         | Only the title, logo and spacing use `dvh`, always inside `clamp()` with rem bounds. Labels, inputs and buttons use rem steps.                            |
| **User font size 20 px+** or Windows text scaling 150 %.                                                                                                                    | All tiers are in rem, so the form grows and scrolls. No fixed heights and no `overflow:hidden`.                                                          |
| **Validation errors add lines.** Four register errors add ≈ 4×22 px, plus the form `Alert`.                                                                                  | Accept scrolling in the error state. The column is `min-h`, not `h`. Focus-first-invalid already scrolls into view.                                       |
| **Google "coming soon" alert** adds ≈ 70 px.                                                                                                                                | Same: it scrolls. Optionally render it as a compact toast. Out of scope unless approved.                                                                   |
| **Mobile keyboard** shrinks the visual viewport.                                                                                                                             | Use `dvh`/`svh` only for the outer `min-height`. Don't lock the height. `enterKeyHint` is already set. Browsers scroll the focused input into view.        |
| **iOS zoom on focus** if the input text is < 16 px.                                                                                                                          | Force 16 px under `(pointer: coarse)`. Smaller input text only on fine pointers (desktop).                                                                |
| **Touch targets** below 44 px on tablets in the `low` tier (1024×768).                                                                                                       | Under `pointer: coarse`, the minimum control height is 44 px. WCAG 2.5.8 (24 px) is met everywhere. The forgot-password link keeps its 36 px hit area.     |
| **Safe areas** on notched phones in landscape.                                                                                                                               | Add `viewport-fit=cover` handling: `px-[max(1rem,env(safe-area-inset-left))]` on the column. This needs one `index.html` meta change (`viewport-fit=cover`), listed as decision D4. |
| **Corner ornaments overlapping text** when the column gets narrower or the waves get smaller.                                                                                | Re-run the overlap check for prompt, logo and title against every ornament at all matrix viewports.                                                        |
| **Hero crop.** Taglines are baked in (W2).                                                                                                                                   | Unchanged split. The worst ratio in the matrix (1280×585 → panel 1.23:1) keeps the tagline inside the visible band (checked against the W2 bounds). Keep the `hero-fits` guard. |
| **Hero resolution** on 1920+ panels (935 px source rendered at 1075–1434 px).                                                                                                | Already known (ASSETS W2). Not changed by this work.                                                                                                     |
| **Shared primitives regress the Memory Wall planner.**                                                                                                                       | Variables with today's fallbacks. Visually re-check SaveDesignDialog and the CanvasPanel/Templates/Saved `lg` buttons.                                    |
| **tailwind-merge** drops `leading-*` before font-size utilities (already noted in AuthHeader). Arbitrary `text-[length:var()]` needs the `length:` hint so it isn't read as a colour. | Use the type hints `text-[length:…]`, keep `leading-*` last, and review the merged output in tests.                                                       |
| **Windows High Contrast.** The focus ring fallback exists.                                                                                                                   | Unchanged. Re-check after the height changes.                                                                                                             |

## 9. Implementation plan

1. **Tokens and variants** (`index.css`): height tier variants and auth density custom properties. Nothing consumes
   them yet, so there is no visual change.
2. **Primitives** (`TextField`, `Button`, optional `EstablishedTag` size): read the variables with today's fallbacks,
   then confirm the Memory Wall planner is pixel-identical.
3. **Auth shell** (`AuthLayout`, `AuthDecorations`): scope class, fluid padding, remove the 80 px clearance, resize
   the waves per tier, set the column widths.
4. **Header and form rhythm** (`AuthHeader`, `AuthForm`, pages, `LoginForm`, `AuthSwitchPrompt`): logo, title,
   subtitle and gaps per tier.
5. **Phone portrait pass:** padding, header compaction and touch sizes.
6. **Verify:** `npm run check`. Then a browser sweep on the 25 viewports in §5 (browser-viewport sizes) for both
   pages, plus Forgot Password. Assert vertical overflow is 0 where §5 says "fit", horizontal overflow is 0
   everywhere, and no ornament overlaps text. Also check 200 % zoom, 20 px default font, the error state, the
   Google notice, keyboard-only navigation, forced colours, and screenshot comparison against `login-new` and
   `register-new` at 1536×735@1.25.
7. **Docs:** update RESPONSIVE.md (tier table, browser-viewport testing rule) and ROADMAP.md.

## Decisions needed before implementation

- **D1 — Target viewport.** Your screenshots imply a 1536×735 browser viewport, not 1280×720. Should I target
  **both** (plan above: fit down to 1280×600), or only 1536×735?
- **D2 — Readability floors vs literal match.** Copying `register-new` gives 11 px labels and a 12.8 px input font. I
  propose floors of 13 px labels, 14 px inputs and 12 px hints, with slightly taller controls (40 px instead of 38).
  Accept the floors?
- **D3 — Very short viewports.** Below about 600 px tall (for example 1280×585 with the taskbar), Register may still
  scroll by about 0–20 px. Accept that, or compress further (for example a 36 px logo with EST inline)?
- **D4 — Phones.** Compact the phone layout as proposed (it changes the current `mobile_view` spacing), and add
  `viewport-fit=cover` safe-area padding (a one-line `index.html` meta change)?
- **D5 — Large screens.** Keep today's full-size design at ≥ 880 px tall, with a small optional step up at
  2560×1440, or freeze it at the current size?
