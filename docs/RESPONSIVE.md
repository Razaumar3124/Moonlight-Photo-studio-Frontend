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

**`short` variant** (`max-height: 55rem` **and** landscape): tighter vertical rhythm and a smaller logo
and waves, so the form fits without scrolling on 1366×768, 1280×720 and 1180×820. Portrait phones keep
the mockup's spacing and scroll. Verified with no overflow at 320×568 → 2560×1440, 844×390 and
720×450 (1440×900 at 200% zoom).

**Register** uses `compact` density: a 30rem column (the mockup's register form is wider than
login's), smaller logo, a fluid one-line title (`clamp(1.75rem, 8.5vw, 2.5rem)`) and tighter gaps. It
fits without scrolling at 1440×900 and up and on portrait tablets. With 4 fields plus the password
hint it scrolls ~70–140px on 768/720-high laptops (the hero stays sticky) and on phones.

## Memory Wall Planner

The laptop mockup is a 3-column dashboard. It must collapse cleanly:

| Viewport | Layout                                                                                                                                                                                                                                        |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `< md`   | Single column: **Canvas** first, then Wall Configuration → Layout → AI Assistant → Frame & Photo → Preview Settings, all collapsible. A fixed bottom bar holds Preview / Templates / Saved + **Request a Quote** (labels shrink below 360px). |
| `md–lg`  | Canvas full width on top; the side panels sit below in a 2-column grid.                                                                                                                                                                       |
| `xl+`    | 3 columns as in the mockup: left config (~22rem) · canvas (fluid) · right frame panel (~24rem). Action bar spans the full width beneath.                                                                                                      |
| `2xl+`   | Same, with a max container width (~1600px) centred.                                                                                                                                                                                           |

Header: logo + "Memory Wall Planner" title. On phones, hide the subtitle and the vertical
divider and collapse Profile to an avatar button.

Canvas: keep the wall's aspect ratio derived from width × height inputs (`aspect-[w/h]`
via inline style). Dimension guides and labels scale with the container. Frame-index chips (1–9)
scroll horizontally on small screens instead of wrapping.

## Testing checklist per screen

Check at **320, 375, 414, 768, 1024, 1280, 1440, 1920** widths, in portrait and landscape on phone
widths, with browser zoom at 200%, and with keyboard-only navigation.
