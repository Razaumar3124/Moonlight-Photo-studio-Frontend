# Design System

Derived from `reference_designs/` (login, register, memory_wall). Tokens live in
[`frontend/src/styles/theme.css`](../frontend/src/styles/theme.css) as a Tailwind v4 `@theme`
block. Each token becomes a utility class automatically, e.g. `--color-brand-600` → `bg-brand-600`.

**Rule:** don't hard-code hex values or arbitrary pixel values in components. If a value is
missing, add a token to `theme.css` and record it here.

## Design direction

Warm, heritage, premium: "a family photo studio since 1985". Cream paper backgrounds, deep
crimson as the single strong colour, fine gold lines as ornament, serif headlines. The UI
should feel calm and well spaced, never busy. Photography carries the emotion and the chrome
stays quiet.

## Colour

| Token          | Hex       | Used for                                                              |
| -------------- | --------- | --------------------------------------------------------------------- |
| `brand-600`    | `#9B1118` | Primary buttons, logo, active toggles/tabs, links                     |
| `brand-700`    | `#820D13` | Primary hover / pressed                                               |
| `brand-900`    | `#4A0A0D` | Dark crimson in decorative corner swooshes                            |
| `brand-50/100` | —         | Selected-state tints (e.g. selected layout thumbnail)                 |
| `gold-400`     | `#C9A25A` | OR dividers, EST rules, thin decorative curves (non-text)             |
| `gold-600`     | `#8C6A2F` | "EST. 1985" **text** (4.6:1; gold-400/500 fail AA for small text)     |
| `cream-100`    | `#FDF6EC` | Page background                                                       |
| `cream-50`     | `#FFFCF7` | Inputs, cards, secondary buttons                                      |
| `cream-200`    | `#F8ECDC` | Subtle panel / segmented-control background                           |
| `cream-300`    | `#EFDFC9` | Decorative borders/dividers (not field boundaries)                    |
| `cream-600`    | `#9F8B77` | Form-field borders (3.0:1, WCAG 1.4.11). Rest at `/70`, hover at full |
| `ink-900`      | `#2A1712` | Headings                                                              |
| `ink-700`      | `#4A3329` | Body text, labels                                                     |
| `ink-500`      | `#7A6356` | Secondary text, placeholders, helper text                             |
| `success-500`  | `#2F8F4E` | "New" badge                                                           |
| `danger-600`   | `#C21F26` | Destructive actions ("Remove"), form errors                           |

Contrast: `brand-600` on `cream-100` and white on `brand-600` both pass WCAG AA for body text.
Only use `ink-500` for text 14px or larger.

### Planner palette ("Gallery Atelier", 2026-11-07)

The Memory Wall planner uses quieter chrome, so the photos carry the colour. Tokens in `theme.css`:

| Token                           | Hex                                           | Used for                                                                             |
| ------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `ivory-50/100/200/300`          | `#FFFDF9` / `#F7F1E8` / `#EFE7DB` / `#E3D8C8` | Rails & popovers / app background / control tracks / hairlines                       |
| `charcoal-900/800/700/500/300`  | `#1F1B19` … `#ABA19A`                         | Headings, selected thumbs, "on" switches, Request a Quote / body / helper / disabled |
| `champagne-300/400`             | `#D9C29A` / `#C4A574`                         | Selected swatch ring, AI sparkle, hover outline on wall frames                       |
| `stage-950/900/800/700`         | `#140F0C` … `#4A3A30`                         | The dark, softly lit stage behind the wall                                           |
| `shadow-primary/pop/wall/thumb` | —                                             | Crimson CTA glow / menus & popovers / the wall on the stage / segmented thumbs       |

**In the planner, red is a signal, not a theme.** Solid crimson only for **Generate Layout** (and the
Download button inside fullscreen). Crimson outline for the **selected frame** (wall, navigator,
badge) and the active AI preset. Crimson text for links and Remove. Segmented controls, switches,
steppers, tabs and unit chips are neutral (white thumb on linen, charcoal "on"). Request a Quote
is charcoal (`Button variant="dark"`).

**Planner type roles:** Playfair Display only for the project title and the section titles
(17px). DM Sans for everything else, **including all buttons**. The section numerals ("01", "02",
"03") are DM Sans 11px, `tracking-[0.18em]`, `gold-600`. Labels are 13px semibold `charcoal-700`.

## Typography

| Role            | Font             | Tailwind                             | Sizes (mobile → desktop)        |
| --------------- | ---------------- | ------------------------------------ | ------------------------------- |
| Page title      | Playfair Display | `font-display`                       | `text-4xl` → `lg:text-5xl`, 600 |
| Hero tagline    | Playfair Display | `font-display`                       | `text-2xl` → `lg:text-4xl`      |
| Panel heading   | Playfair Display | `font-display`                       | `text-xl` → `text-2xl`          |
| Body / subtitle | DM Sans          | `font-sans` (default)                | `text-base` → `lg:text-lg`      |
| Field label     | DM Sans 600      | `text-sm font-semibold`              |                                 |
| Eyebrow (EST.)  | DM Sans 600      | `text-xs tracking-[0.3em] uppercase` |                                 |

Both fonts are **self-hosted** via `@fontsource` (imported in `src/main.tsx`): Playfair Display 600
(latin) and DM Sans variable. That means no third-party requests (CSP + privacy), and `font-display: swap`. If you need another
weight, import its file there; don't add Google Fonts links. The mockups use serif
headlines close to Playfair Display. Swap the font if the brand has an official one and
update `--font-display` only.

## Shape, depth, spacing

- **Radius:** inputs and buttons `rounded-field` (10px); planner panels `rounded-card` (16px);
  swatches and step badges `rounded-full`.
- **Shadow:** cards `shadow-card`, inputs `shadow-field`, primary CTA `shadow-button`. Keep
  them soft and warm-tinted. Never use grey drop shadows.
- **Field height:** 48px (`h-12`) on all viewports, which keeps tap targets ≥ 44px.
- **Spacing:** Tailwind's 4px scale. Form fields stack with `gap-5`, and label-to-input spacing is `gap-2`.

## Component inventory (from the mockups)

These are the reusable building blocks to create in `components/ui/`. Feature-specific
composites go in `features/<feature>/components/`.

### Built so far

`Button` (`primary`, `primary-gradient` (Register CTA), `secondary`, `ghost`; `loading`), `TextField`
(`leftIcon`, `startAddon`, `rightSlot`, `hint`, `error`), `PasswordField`, `PhoneField` (fixed country
code, announced in the label), `Divider`, `TextLink`, `Logo`, `EstablishedTag`, `Alert`, `Spinner`.
Auth: `AuthLayout` / `AuthHeader` (`compact` for longer forms), `AuthForm` (shared form skeleton), `GoogleSignIn`, `AuthSwitchPrompt`.
Text fields show a real outline in Windows High Contrast (`forced-colors:`), since box-shadow rings are dropped there.

**Gotcha:** with `cn()`, put `leading-*` _after_ any font-size class. tailwind-merge drops a
line-height that precedes a font-size utility.

### Shared primitives (`components/ui/`)

| Component          | Variants / props                                                                                              | Seen in                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `Button`           | `primary` (crimson), `secondary` (cream outline), `ghost`, `link`; `size`; `leftIcon`; `loading`; `fullWidth` | All screens                  |
| `IconButton`       | round/square, used for +/−, carousel arrows                                                                   | Planner                      |
| `TextField`        | label, `leftIcon`, `rightSlot`, error, helper                                                                 | Login, Register              |
| `PasswordField`    | `TextField` + show/hide eye toggle                                                                            | Login, Register              |
| `PhoneField`       | `TextField` + fixed country-code prefix (`+91`)                                                               | Register                     |
| `Divider`          | plain or with centred label ("OR"), gold line                                                                 | Login, Register              |
| `SegmentedControl` | options[], value, onChange (ft/in/cm/m, Grid/Salon/Centre/Row)                                                | Planner                      |
| `Toggle` (switch)  | checked, label, description                                                                                   | Planner                      |
| `NumberStepper`    | − value + with unit                                                                                           | Planner (Frame Gaps, Mat)    |
| `Select`           | native select styled                                                                                          | Planner (Frame Size)         |
| `SwatchPicker`     | colours[], value; selected ring                                                                               | Planner (paint, wood, mount) |
| `Badge`            | `new` (green), `neutral` ("Interactive")                                                                      | Planner                      |
| `Card` / `Panel`   | numbered header (`StepBadge` + title + subtitle), body                                                        | Planner                      |
| `Logo`             | full lockup / compact                                                                                         | All screens                  |

### Feature composites

- **Auth** (`features/auth/components/`): `AuthLayout` (hero image + form split),
  `AuthHero`, `AuthHeader` (logo + EST. + title + subtitle), `GoogleButton`, `LoginForm`, `RegisterForm`.
- **Memory wall** (`features/memory-wall/components/`): `PlannerHeader` (+ `FitStatus`,
  `RequestQuoteButton`), `Rail` / `RailSection`, `WallSection`, `ArrangementSection`,
  `AiLayoutsSection`, `Stage` (+ `GenerateCluster`: Regenerate, Redesign, Generate Layout), `WallCanvas` /
  `WallSvg`, `ViewToggles`, `FrameInspector` (navigator + Photo / Frame / Mount tabs),
  `SidePanel` / `MobileSheet` (`ControlPanels.tsx`), `MobileActionBar`, and the dialogs.
- **Shared primitives added 2026-11-07:** `Menu` (menu button with item, radio and checkbox items),
  `Tabs` / `TabPanel`, `Tooltip` (via `IconButton tooltip`), `useDismiss`. Planner sizes on the
  existing primitives: `Button` `sm`/`compact` + `dark`/`quiet`/`stage`, `SegmentedControl`
  `appearance="neutral" | "stage"` + `size="xs"`, `Switch size="sm"`, `NumberStepper size="sm"`,
  `SwatchPicker size="sm"`, `Select compact`, `IconButton` `quiet`/`stage` + `shape="square"`.
  The defaults are unchanged, so the auth pages render as before.

## Iconography

The mockups use thin-stroke outline icons (user, lock, mail, eye-off, grid, bookmark, reset,
download, expand). Use **one** consistent outline set. We recommend `lucide-react`
(tree-shakeable, 1.5–2px stroke, matches the mockups). Brand-specific marks (logo, Google
"G", leaf sprigs, corner swooshes) are custom SVGs in `src/assets/` (see [ASSETS.md](ASSETS.md)).

## Motion

Subtle only: 150–200ms colour/shadow transitions on hover and focus, a 150ms `pop-in` for menus and
popovers, frames gliding to new positions (480ms), and a light `shimmer` across the wall while
Generate Layout works. All motion is disabled under `prefers-reduced-motion` (handled globally in
`index.css`).

## Contrast (verified 2026-11-05)

| Pair                                       | Ratio | Rule                                          |
| ------------------------------------------ | ----- | --------------------------------------------- |
| ink-900 heading on cream-100               | 15.9  | ✅                                            |
| ink-500 subtitle / placeholder on cream-50 | 5.5   | ✅ (placeholders use full ink-500, never /80) |
| gold-600 EST text on cream-50              | 4.9   | ✅                                            |
| brand-600 link on cream-50                 | 8.3   | ✅                                            |
| danger-600 error on cream-50               | 5.8   | ✅                                            |
| white on brand-600 button                  | 8.4   | ✅                                            |
| cream-600 field border on cream-100        | 3.0   | ✅ non-text                                   |

## Accessibility baseline

- Every input has a visible `<label>`; icons inside fields are `aria-hidden`.
- Password toggle is a real `<button>` with `aria-label="Show password"` / `"Hide password"`.
- Focus ring: global `:focus-visible` crimson outline; inputs show a crimson ring on their wrapper. Never remove one without a replacement.
- Touch targets ≥ 24px (WCAG 2.5.8). Standalone small links get `py-2 -my-2` for a ≥ 36px hit area.
- Toggle buttons keep a constant `aria-label` and expose state with `aria-pressed`.
- Swatches and segmented controls are radio groups (keyboard arrows, `aria-checked`).
- Decorative images (`alt=""`); meaningful photos get descriptive alt text.
