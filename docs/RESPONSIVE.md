# Responsive Behaviour

Mobile-first. Tailwind breakpoints (min-width):

| Prefix | Min width | Typical device                    |
| ------ | --------- | --------------------------------- |
| (none) | 0         | Phones (design floor: 320px)      |
| `sm`   | 640px     | Large phones                      |
| `md`   | 768px     | Tablets portrait                  |
| `lg`   | 1024px    | Tablets landscape / small laptops |
| `xl`   | 1280px    | Laptops (laptop mockups)          |
| `2xl`  | 1536px    | Desktops                          |
| `3xl`  | 1792px    | Wide desktops (custom token)      |

Global rules: no horizontal scroll at 320px; side gutter `px-4` on phones, `sm:px-6`, `lg:px-8`;
use `min-h-dvh` (not `h-screen`) so mobile browser chrome doesn't clip content; controls are 40–48px
tall, and nothing interactive is under 24×24px (WCAG 2.5.8). Small standalone links get a ≥ 36px hit area.

## Login & Register

| Viewport                                                | Layout                                                                                                                                                                            |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Default (phones, portrait tablets, near-square windows) | Single column, form only (matches `mobile_view.png`). Cream background, leaves and crimson corner waves as decorative absolutely-positioned SVGs. Form max-width ~28rem, centred. |
| `hero-fits` (≥ lg **and** landscape ≥ 4:3)              | Hero photo left (fluid, ~56%; `object-cover`, per-asset `objectPosition`), form panel right (`minmax(30rem, 44%)`). Form max-width ~28rem, vertically centred.                    |
| `2xl+`                                                  | Same split. Cap the form panel's content width and let the hero absorb extra space.                                                                                               |

The hero photos have their tagline **baked in** (ASSETS.md W2), so the hero uses the custom
`hero-fits` variant (`hidden hero-fits:block`) instead of plain `lg:`. Panel ratios narrower than
~0.66:1 would crop the text. Render the `<img>` only when that media query matches, so phones
never download it.

### Height-aware density (`auth-fluid`, see [AUTH_RESPONSIVE_AUDIT.md](AUTH_RESPONSIVE_AUDIT.md))

Width picks the layout. **Height** picks the density. `<main class="auth-scope">` (Register adds
`data-density="compact"`) carries CSS custom properties defined in `src/index.css`. Components use
them through the `auth-fluid:` variant, which is active when the viewport is ≤ 55rem tall or ≤ 40rem wide.

| Regime               | When                                              | Behaviour                                                                                     |
| -------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Full size            | > 880px tall (portrait tablets, ≥ 900px desktops) | The original design, unchanged classes. No extra growth at 2560×1440.                         |
| Landscape, 768–880px | e.g. 1440×789, 1600×789                           | Fluid: logo, title, gaps and controls interpolate down from full size.                        |
| Landscape, 600–768px | 1536×735, 1366×768/657, 1280×720/633/600          | ≈ reference shots (`login-new` ≈ 90 %, `register-new` ≈ 80 % of full size). Controls 40–44px. |
| Landscape, < 600px   | 1280×585, landscape phones                        | Tightest: smaller logo, title, subtitle, waves. Scrolls when content still can't fit.         |
| Portrait phones      | ≤ 40rem wide, or portrait ≤ 880px tall            | Fluid between 560 and 840px tall. 44px touch controls, 16px inputs, safe-area padding.        |

Rules:

- **Vertical sizes** use `clamp(min, calc(V + (100dvh − H0) · Δ / span), max)`.
- **Text** steps in rem and never uses `dvh`, so it follows browser zoom and the user's font size. Floors are 13px labels, 14px inputs (16px on touch, to avoid iOS focus zoom), 12px hint and error text, and 40px controls (44px on touch).
- **Shared primitives** (`TextField`, `Button size="lg"`) read `--field-*` and `--button-lg-*` with fallbacks equal to the defaults. Pages that don't set them (the Memory Wall dialogs) are unchanged.
- **Corner ornaments** scale with the same properties, so short screens need no extra bottom padding for the footer link.
- **Safe areas:** `useViewportFitCover` adds `viewport-fit=cover` only while an auth page is mounted. The column pads with `env(safe-area-inset-*)`.
- **Scrolling** is never disabled. The column uses `min-h-dvh`, so it scrolls with the keyboard open, at 200 % zoom, with large fonts, and when validation errors appear.

**Verified** (browser viewports, not whole-screen sizes):

- **No scroll on either page:** 1280×585, 1280×600, 1280×633, 1280×720, 1366×657, 1366×768, 1536×735, 1440×789, 1440×900, 1600×900, 1920×969, 1920×1080, 2560×1440, 1024×768, 768×1024, 430×932 and 390×844.
- **Login also fits** at 390×664 and 375×667.
- **Scrolls, as expected (nothing clipped):** Register on phones under ≈ 800px tall, Login on 375×553 and 320×568, and both pages on landscape phones.

## Memory Wall Planner

A fixed-height studio workspace (`h-dvh`, no page scroll). See
[MEMORY_WALL_REDESIGN_AUDIT.md](MEMORY_WALL_REDESIGN_AUDIT.md) §3, §7, §8. **Width decides the
structure** (`useLayoutMode` in `MemoryWallPage.tsx`). **Height decides the density** (the
`.planner-scope` custom properties in `index.css`).

| Mode      | When                                                                            | Layout                                                                                                                                  |
| --------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `desktop` | ≥ 1280px wide                                                                   | Header · set-up rail (`--pl-rail-l`) · stage (fluid) · frame inspector (`--pl-rail-r`)                                                  |
| `split`   | < 1280px and landscape (≥ 480px wide): tablets, small laptops, landscape phones | Header · stage · one side panel with **Set up / Frame** tabs                                                                            |
| `stacked` | Portrait phones and tablets                                                     | Header · stage (≤ 50dvh) · docked sheet with **Wall / Layout / Frame / View** tabs · bottom bar (Regenerate, Redesign, Generate, Quote) |

| Density tier      | Rule                                  | `--pl-ctl` | Target                     |
| ----------------- | ------------------------------------- | ---------- | -------------------------- |
| compact (default) | —                                     | 36px       | 1536×735, 1366×768         |
| dense             | `max-height: 40rem`                   | 32px       | 1280×600, landscape phones |
| roomy             | `min-height: 50rem` and ≥ 1440px wide | 40px       | 1920×1080 and up           |
| touch             | `pointer: coarse`                     | 40px       | any                        |

Rules:

- Rails, the side panel and the sheet scroll **internally** (`overflow-y-auto`, and `relative`
  so `sr-only` children can't stretch the document). The stage never scrolls: the wall fits a
  `container-type: size` box on both axes (`WallCanvas fit="container"`).
- Every scroll container and grid track is `min-h-0` / `minmax(0,1fr)`. The shell's column is
  `minmax(0,1fr)`, so a wide header can't widen the page.
- Selecting a frame on the wall switches the side panel or sheet to its **Frame** tab.
- The bottom bar hides while a text field in the sheet has focus (on-screen keyboard).
- Below 320px tall (`tiny`), the shell falls back to normal page scrolling.
- The stage is a container (`@container/stage`). When it is narrow, the view toggles move into
  the ⋯ menu and button labels collapse to icons.

## Testing checklist per screen

Check at **320, 375, 414, 768, 1024, 1280, 1440, 1920** widths, in portrait and landscape on phone
widths, with browser zoom at 200%, and with keyboard-only navigation.

Test heights as **browser viewports**, not screen sizes. Subtract the taskbar (~48px) and the browser
chrome (~63–87px). A 1280×720 screen leaves ≈ 1280×585–633 px, and 1920×1080 at 125 % scaling
leaves ≈ 1536×735 px.
