# Memory Wall Planner: UI/UX Redesign Audit

**Status:** ✅ Implemented 2026-11-07 (see ROADMAP.md → "Memory Wall redesign"). This document is
the design rationale. Where the build differs, the code, RESPONSIVE.md and DESIGN_SYSTEM.md are current.
**Date:** 2026-11-07
**Scope:** `frontend/src/features/memory-wall/**`, the shared primitives it uses (`components/ui/*`),
`styles/theme.css`, `index.css`, and the two screenshots from the current build (1536×735 browser
viewport, scrolled to the top and to the bottom). Also compared against `reference_designs/memory_wall/laptop_view.png`.

**How to read this document**

- **[Existing]** means the feature exists today. I checked the implementation, not only the screenshot.
- **[Proposed]** means a new presentation or interaction. Each one reuses existing state and actions
  unless it says otherwise.
- File references are relative to `frontend/src/`.

---

## Contents

1. [Current UI Assessment](#1-current-ui-assessment)
2. [Design Direction](#2-design-direction)
3. [Proposed Layout](#3-proposed-layout)
4. [Before vs After (component level)](#4-before-vs-after-component-level)
5. [Interaction Improvements](#5-interaction-improvements)
6. [Pagination Removal](#6-pagination-removal)
7. [Responsive Behaviour](#7-responsive-behaviour)
8. [No-Scroll Strategy](#8-no-scroll-strategy)
9. [Preservation Checklist](#9-preservation-checklist)
10. [Required Assets](#10-required-assets)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Current UI Assessment

### 1.1 What works (keep)

The engineering underneath is strong, and the redesign should keep it as it is:

- **One reducer as the source of truth** (`lib/plannerState.ts`). Every control dispatches one
  action. `buildScene` derives the full layout from state. Inputs are clamped and sanitised in the reducer.
- **Live geometry**: the canvas is an SVG whose viewBox is measured in inches. Frames animate to new
  positions (`WallSvg.tsx`, 480 ms transform transition). Frames are focusable buttons with `aria-pressed`.
- **Accessibility**: real radio groups for segmented controls and swatches, `role="switch"`,
  native `<dialog>` with focus trapping, an `aria-live` arrangement summary, reduced-motion support,
  and Undo toasts in place of confirmation dialogs.
- **The fullscreen "gallery stage"** with view toggles and a Download button that shows its status
  (`FullscreenPreviewDialog.tsx`). This is the most refined surface in the app today, and its patterns
  are reused in the proposal below.

### 1.2 Problems found (screenshots + code)

| #   | Problem                                                                                                                                                                                                                                                                                                                                         | Evidence                                                                                                                                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | **The page scrolls at both target viewports.** At 1536×735 the canvas, Generate button, Preview Settings and action bar don't fit. Screenshot 2 shows the bottom of the page after scrolling.                                                                                                                                                   | `MemoryWallPage.tsx` uses `min-h-dvh` with a normal document flow. Columns are `items-start`, so each one grows to its content. The canvas is `maxHeight="min(56vh, 36rem)"`, plus a summary, carousel, two action tiles (~90 px) and a 52 px Generate button below it. |
| P2  | **The right column is the tallest block, so it sets the page height.** Frame & Photo has 9 control groups stacked, plus Preview Settings below.                                                                                                                                                                                                 | `FramePanels.tsx`: frame chips, photo picker, samples switch, size select, orientation, 8 finish swatches, mount switch, mount colours, mat stepper. All are always expanded.                                                                                           |
| P3  | **Red is everywhere.** Step badges, the active segmented option, active unit chips, every switch, frame chips, the selected swatch ring, the Generate button, the Quote button, the Download button and icons in the action bar are all `brand-600`. When everything is emphasised, nothing is.                                                 | Screenshot 1: ten or more solid red elements in one viewport. `SegmentedControl` and `Switch` use `peer-checked:bg-brand-600` and `checked ? bg-brand-600`.                                                                                                             |
| P4  | **Inconsistent type roles.** Playfair Display is used for page titles, panel titles, sub-headings ("Selected Frame #1"), button labels (Generate, Regenerate, Redesign, Quote, action-bar titles) and the frame number "#1". Serif button labels make the UI look like a brochure rather than a tool, and size and weight vary between buttons. | `CanvasPanel.tsx` `ActionTile` and Generate: `font-display`. `ActionBar.tsx`: `font-display text-base` / `text-xl`. `StepCard`: `text-xl`. Canvas title: `text-2xl`.                                                                                                    |
| P5  | **Too many boxes.** Cards contain cards that contain bordered tiles. Frame & Photo, for example, goes card → cream box → photo row box → thumbnail with border. That makes four nested borders.                                                                                                                                                 | `FramePanels.tsx` (`rounded-xl border bg-cream-100/60` inside a `StepCard`). Same pattern in `ActionBar` (bordered card containing bordered buttons).                                                                                                                   |
| P6  | **Oversized controls for a dense tool.** Text inputs are 44 px, segmented controls 40 px, switches 28×48, steppers 40 px, Generate 52 px, quote button ~80 px tall. These sizes suit a sign-up form, not a configurator with about 25 controls.                                                                                                 | `Button md: h-11`, `DimensionInput h-11`, `Switch h-7 w-12`, `ActionBar min-h-14 text-xl`.                                                                                                                                                                              |
| P7  | **Duplicate and competing actions.** "My Saved Templates" appears in both the action bar and the Profile menu. Save/Reset sit in the canvas header, Preview/Templates/Saved/Quote in a bottom bar, and Generate/Regenerate/Redesign below the canvas. That puts actions in three different places with no clear grouping.                       | `PlannerHeader.tsx` ProfileMenu + `ActionBar.tsx` + `CanvasPanel.tsx` header.                                                                                                                                                                                           |
| P8  | **Confusing terms.** "Save Design" saves into "My Saved **Templates**". "All Templates" means curated layouts. The AI Assistant also applies templates. Users can't tell whether a saved design is the same thing as a template.                                                                                                                | `MemoryWallPage.tsx` toast: `saved to My Saved Templates`. `SavedDesignsDialog` title.                                                                                                                                                                                  |
| P9  | **Numbered steps suggest an order that doesn't exist.** Steps 1–4 imply a sequence, but the reducer allows any order. Step 4 (Preview Settings) holds view toggles, not a step. The AI Assistant has no number, so it sits outside the sequence.                                                                                                | `StepCard step={1..4}`. `AiAssistantPanel` uses an icon.                                                                                                                                                                                                                |
| P10 | **The variant carousel's meaning is unclear.** Three dots under the canvas look like an image carousel. Users don't know what "option 2" changes, and the effect for a uniform grid is only a different column count.                                                                                                                           | `VariantCarousel` in `CanvasPanel.tsx`. See §6.                                                                                                                                                                                                                         |
| P11 | **"Regenerate" barely changes some layouts.** For the default 9 identical frames in a Grid, Regenerate only reshuffles which photo goes in which slot (`slotOrder` in `scene.ts`). `gridLayout` ignores `seed`, so the arrangement looks the same, which contradicts the subtitle "new arrangement".                                            | `lib/geometry/scene.ts` `slotOrder()` and `layouts.ts` `gridLayout` (no `seed` in its signature). Noted here as a copy and expectation issue. The logic stays unchanged in this phase.                                                                                  |
| P12 | **Warnings push the layout down.** `scene.warnings` render as full-width alert rows under the canvas. When a design doesn't fit, which is exactly when the user needs the controls, the Generate button gets pushed further out of view.                                                                                                        | `CanvasPanel.tsx` `<ul>` of warnings.                                                                                                                                                                                                                                   |
| P13 | **The frame selector doesn't scale.** Numbered circles 1–N (up to 16) don't show which photo is in which frame. The link to the canvas exists (clicking a frame selects it), but nothing tells users they can click the canvas.                                                                                                                 | `FrameChips` in `FramePanels.tsx`. `WallSvg` selection already works.                                                                                                                                                                                                   |
| P14 | **Canvas guides compete with the art.** The width arrow, height arrow with a two-line label and an eye-level line with a pill label all sit on the photo with heavy pills and shadows. Index badges sit at the frame corners on top of the moulding.                                                                                            | `WallCanvas.tsx` overlays.                                                                                                                                                                                                                                              |
| P15 | **The header is tall and the sticky header bleeds through.** It is about 100 px at 1536 wide. Screenshot 1 shows the translucent header over scrolled content (the sofa image shows through behind the title), which looks unfinished.                                                                                                          | `PlannerHeader.tsx` `bg-cream-50/90 backdrop-blur`, `w-40` logo, 2-line title.                                                                                                                                                                                          |
| P16 | **Mixed icon sizing.** Icons are 14, 16, 18, 20, 24 and 28 px within one screen (`size-3.5 … size-7`), and some sit inside coloured circles while others don't. The Sparkles icon is gold, every other icon is red.                                                                                                                             | Grep of `size-*` on icons across `components/`.                                                                                                                                                                                                                         |
| P17 | **Unequal column widths and alignment.** The left column (19–22 rem) and right column (20–24 rem) differ. Inner controls don't share a grid: the gap stepper and unit toggle don't line up with Number of Frames.                                                                                                                               | `xl:grid-cols-[minmax(19rem,22rem)_minmax(0,1fr)_minmax(20rem,24rem)]`.                                                                                                                                                                                                 |
| P18 | **The mobile bottom bar repeats the desktop action set**, but Generate and Save are not in it, even though they are the two most important actions on mobile.                                                                                                                                                                                   | `ActionBar.tsx` phone nav: Preview / Templates / Saved / Quote.                                                                                                                                                                                                         |

### 1.3 Root cause

The page is built as a **long document of equal-weight cards**. It needs to be an **application
workspace** with one hero (the wall), two quiet tool rails, and actions grouped by intent. Most of
P1–P18 follow from that one structural choice, so the fix is structural first and visual second.

---

## 2. Design Direction

### 2.1 Concept: "The Gallery Atelier"

The interface should feel like a **framer's studio with a gallery wall**. The chrome is calm and
quiet: ivory paper, fine hairlines, champagne details and charcoal type. The wall preview is lit like
an exhibition and carries all of the emotion. Moonlight red is used **only where it means
something**: the brand, the single primary action in view, and the frame currently selected.

Design principles:

1. **The wall is the hero.** It gets at least 50 % of the viewport area at every breakpoint.
2. **Red is a signal, not a theme.** At most about 3 red elements are visible at once: the logo, one
   primary button, and the selected-frame outline.
3. **Quiet controls, loud content.** Neutral selected states (charcoal on ivory) for segmented
   controls, toggles and chips.
4. **Group by intent.** Rails are split into _Set up the wall_, _Arrange_, and _Customise the
   selected frame_. View options live on the canvas. Project actions live in the header.
5. **Progressive disclosure.** Rarely changed settings (mount details, gap unit, view toggles) take
   one click to reach and never push primary content out of view.

### 2.2 Colour palette

The existing tokens stay, so the auth pages remain unaffected. New tokens are added to
`styles/theme.css`, scoped by name to the planner surfaces.

| Role               | Token (proposed)         | Hex       | Use                                                                  |
| ------------------ | ------------------------ | --------- | -------------------------------------------------------------------- |
| Brand primary      | `brand-600` (existing)   | `#9B1118` | Primary CTA, selected frame on canvas, active rail indicator         |
| Brand deep         | `brand-800` (existing)   | `#6A0C11` | Primary hover, burgundy text accents                                 |
| Burgundy wash      | `brand-50` (existing)    | `#FDF2F2` | Selected-frame tint in the navigator                                 |
| **Ivory (panels)** | `ivory-50` _new_         | `#FFFDF9` | Rail and popover surfaces                                            |
| **Cream (page)**   | `ivory-100` _new_        | `#F7F1E8` | App background behind rails                                          |
| **Linen (track)**  | `ivory-200` _new_        | `#EFE7DB` | Segmented tracks, inputs at rest, switch off                         |
| **Hairline**       | `ivory-300` _new_        | `#E3D8C8` | Dividers, panel edges (decorative)                                   |
| **Field edge**     | `cream-600` (existing)   | `#9F8B77` | Input borders (keeps 3:1, WCAG 1.4.11)                               |
| **Champagne**      | `champagne-300` _new_    | `#D9C29A` | Selected swatch ring, AI sparkle, section numerals, focus halo glow  |
| **Champagne text** | `gold-600` (existing)    | `#8C6A2F` | Small gold text (4.9:1)                                              |
| **Charcoal 900**   | `charcoal-900` _new_     | `#1F1B19` | Headings, selected segmented thumb, switch on, secondary-dark button |
| **Charcoal 700**   | `charcoal-700` _new_     | `#3D3633` | Body text, labels                                                    |
| **Charcoal 500**   | `charcoal-500` _new_     | `#6F6560` | Helper text (≥ 14 px only; ≈5.3:1 on ivory-50)                       |
| **Charcoal 300**   | `charcoal-300` _new_     | `#ABA19A` | Disabled, placeholder icons                                          |
| **Stage**          | `stage-900` _new_        | `#2A211D` | Dark gallery stage behind the wall (centre pane)                     |
| Success (fit)      | `success-500` (existing) | `#2F8F4E` | "Fits wall" dot + text                                               |
| Warning (fit)      | `gold-600` (existing)    | `#8C6A2F` | "Check fit"                                                          |
| Danger             | `danger-600` (existing)  | `#C21F26` | Remove photo, errors                                                 |

**Why charcoal instead of the current brown ink:** the brown `ink-*` scale sits too close to the
cream and wood tones, so the chrome blends into the photos. A warm charcoal separates the UI from
the art while keeping the warmth. `ink-*` stays for the auth pages.

**Red usage rules (to be written into DESIGN_SYSTEM.md):**

- Solid red: **Generate Layout** (the primary action in the workspace) and the logo. On mobile, the one primary in the bottom bar.
- Red outline: the **selected frame** on the canvas and in the navigator.
- Red text: links and the "Remove" text action (danger red).
- Not red: segmented selections, switches, steppers, step numbers, unit chips, icons in buttons.

### 2.3 Typography

There are no new font dependencies. Both families are already self-hosted.

| Role                | Family                     | Size / weight / tracking                | Where                                                |
| ------------------- | -------------------------- | --------------------------------------- | ---------------------------------------------------- |
| Project title       | Playfair Display 600       | 20 px / 1.2                             | Header: "Living Room Gallery Wall"                   |
| Section title       | Playfair Display 600       | 17 px / 1.25                            | Rail sections ("The Wall", "Arrangement", "Frame 3") |
| Section numeral     | DM Sans 600                | 11 px, `tracking-[0.18em]`, champagne   | "01", "02", "03" eyebrow                             |
| Label               | DM Sans 600                | 13 px                                   | Field labels                                         |
| Body / control text | DM Sans 500                | 13–14 px                                | Inputs, segmented options, menu items                |
| Helper / meta       | DM Sans 400                | 12 px                                   | Descriptions, DPI info, arrangement summary          |
| Buttons             | **DM Sans 600**            | 13 px (sm), 14 px (md), 15 px (primary) | All buttons. **No serif in buttons.**                |
| Numeric             | DM Sans 600 `tabular-nums` | 14 px                                   | Dimensions, steppers                                 |
| Canvas guides       | DM Sans 500                | `clamp(10px, 1.3cqi, 12px)`             | Dimension pills                                      |

Playfair is limited to the project title and the section titles. That removes about 12 serif usages
and makes the hierarchy readable at a glance. Optional later step: load Playfair Display **italic
500** (one more `@fontsource` file, ~20 KB) for an editorial accent on the empty-state line
("Every wall tells a story"). Not required.

### 2.4 Iconography

- **One set:** `lucide-react` (already installed). Stroke `1.75`. Sizes: **16 px** in controls and
  menus, **18 px** in toolbar icon buttons, **20 px** only in the mobile bottom bar.
- Icon colour follows the text colour (`currentColor`, charcoal). Red icons appear only inside red buttons.
- Champagne is reserved for the AI sparkle (`Sparkles`) and "Recommended" marks.
- Icon-only buttons always get a visible tooltip and an `aria-label`. The `ViewToggle` in the fullscreen dialog is the model to follow.
- Suggested mapping: Wall `Ruler`/`BrickWall`, Arrangement `LayoutDashboard`, Frame `Frame`,
  Photo `ImagePlus`, Mount `SquareDashed`, View `Eye`, Sofa `Sofa`, Badges `Hash`, Guides `Ruler`,
  Fullscreen `Expand`, Download `Download`, Templates `LayoutTemplate`, Saved `FolderHeart`,
  Save `Bookmark`, Reset `RotateCcw`, Generate `Sparkles`, Regenerate `Shuffle`, Redesign `Wand2`,
  Quote `ArrowRight`.

### 2.5 Component styling language

| Element              | Spec                                                                                                                                                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rails**            | Flush to the viewport edges, `ivory-50`, 1 px `ivory-300` inner edge, no shadow, no radius. Sections are separated by hairlines, **not cards**.                                                                                                  |
| **Stage (centre)**   | `stage-900` with a soft radial spotlight (the same gradient family as the fullscreen dialog, lighter). The wall sits on it with a deep, soft shadow. The rest of the UI stays light, so the dark stage pulls the eye to the art.                 |
| **Inputs**           | 36 px high (32 px dense), `ivory-50` fill, 1 px `cream-600/60` edge, 8 px radius, unit suffix in muted text (not a red chip). Focus: 2 px brand ring at 20 % plus a border change.                                                               |
| **Segmented**        | Linen track (`ivory-200`), 2 px inset, selected thumb **white with a charcoal label and a soft shadow**. The thumb slides 150 ms. 32 px high.                                                                                                    |
| **Switch**           | 20×36 px, off `ivory-300`, on `charcoal-900`, white knob. Keeps the 44 px hit area through `before:`.                                                                                                                                            |
| **Stepper**          | 32 px, borderless ± buttons inside a linen pill, value centred and tabular.                                                                                                                                                                      |
| **Swatches**         | 24 px (28 px touch), 1 px inner hairline. Selected: 2 px **champagne ring** offset 2 px plus a tiny check, and the name appears beside the label. Hover: scale 1.08 and a tooltip with the name.                                                 |
| **Buttons**          | `primary` red solid 36 px, `dark` charcoal solid (new variant), `secondary` ivory with a hairline, `ghost`, `icon` (32 px square, 8 px radius, tooltip). Radius 8 px everywhere. Shadows only on primary (`0 6px 16px -6px rgb(155 17 24/.45)`). |
| **Chips / badges**   | 22 px pill, 12 px text, dot plus label for status ("● Fits wall").                                                                                                                                                                               |
| **Popovers / menus** | `ivory-50`, 12 px radius, `shadow-[0_12px_32px_-8px_rgb(31_27_25/.25)]`, 1 px hairline, 160 ms fade-and-rise (reuse `toast-in`).                                                                                                                 |
| **Spacing**          | 4 px grid. Rail padding 16 px (12 px dense), section gap 20 px (14 px dense), label→control 6 px.                                                                                                                                                |
| **Radius scale**     | 6 (chips/swatches), 8 (controls), 12 (popovers, thumbnails), 16 (sheets, dialogs).                                                                                                                                                               |

---

## 3. Proposed Layout

### 3.1 Desktop workspace (≥ 1280 px wide)

The page becomes a fixed-height application shell: header plus a three-pane body. **The bottom
action card row is removed.** Its actions move into the header (project actions) and the stage
toolbar (view actions).

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ ☾ MOONLIGHT │ Living Room Gallery Wall ✎  ● Fits wall     Templates  My Designs  [Save]  [Request a Quote →]  (◉▾) │  52px
├──────────────────────┬────────────────────────────────────────────────────┬───────────────────┤
│ 01 THE WALL          │ ┌ stage toolbar ─────────────────────────────────┐ │ 03 FRAME  ‹ 3/9 › │
│ Width [12  ft] Height│ │ Grid·Salon·Centre·Row   👁 Sofa # Guides  ⤢  ⋯ │ │ ▢▢▣▢▢▢▢▢▢ (thumbs)│
│ [9  ft]   ft in cm m │ └────────────────────────────────────────────────┘ │───────────────────│
│ Paint ○●○○○○○ Cream  │                                                    │ [Photo][Frame][Mount] │
│──────────────────────│        ┌───────────── 12 ft ─────────────┐         │                   │
│ 02 ARRANGEMENT       │        │   ▣  ▢  ▢                        │         │  ┌────┐ Upload / │
│ Frames  (− 9 +)      │        │   ▢  ▢  ▢       eye level 60 in  │ 9 ft   │  │ 📷 │ Replace  │
│ Gap  (− 3 +) in|cm   │        │   ▢  ▢  ▢                        │         │  └────┘ Remove   │
│──────────────────────│        │        ▬▬▬ sofa ▬▬▬              │         │  300 DPI · Good   │
│ ✦ AI LAYOUTS         │        └──────────────────────────────────┘         │  ☐ Sample fill    │
│ [img][img]           │  60 × 72 in · 9 frames · 23 % of wall               │                   │
│ [img][img]           │            [⇄ Regenerate] [✎ Redesign] [✦ Generate Layout ▾] │ Apply to all ›   │
└──────────────────────┴────────────────────────────────────────────────────┴───────────────────┘
   288 px (rail)                         fluid stage                          320 px (inspector)
```

**Header (52 px; 48 px dense)**

- Left: compact logo (`w-28`), hairline, **project title** in Playfair (existing `state.title`,
  displayed read-only). Next to it, a **fit status chip** (moved from the canvas header,
  `scene.fits`), which opens the warnings popover (see §5.3).
- Right, grouped by intent: `Templates` (ghost), `My Designs` (ghost, opens SavedDesignsDialog),
  `Save` (secondary), **Request a Quote** (`dark` charcoal solid), then the Profile avatar.
- The "Design a wall full of memories." tagline moves to the empty state and loading screens only.
- The header is **opaque** (fixes P15).

**Left rail: "Set up" (288 px; 272 px dense)**

- `01 The Wall`: width and height on one row (2 columns), unit segmented control (`ft in cm m`)
  under the dimensions, paint swatches with the shade name.
- `02 Arrangement`: Frames stepper, Gap stepper with an inline `in | cm` mini-toggle. **The layout
  style segmented control moves to the stage toolbar**, because it changes what you see and belongs
  next to the art.
- `✦ AI Layouts`: the 4 presets as a 2×2 grid of 4:3 thumbnails with labels under them. The
  thumbnails are bigger and easier to read than today's 4-across strip, and they fit because the
  rail no longer holds the layout-style or preview sections. A "See all templates" link at the
  bottom opens TemplatesDialog (an existing action in a second, contextual place).
- The rail scrolls internally if needed (see §8). At the target viewports it does not need to.

**Centre: Stage**

- **Stage toolbar** (40 px, transparent over the dark stage, light text):
  - Left: layout style segmented control (Grid · Salon · Centre · Row) **[Existing control,
    moved]**.
  - Right: view toggle group (Sofa · Badges · Guides), the same `ViewToggle` pattern as fullscreen
    **[Existing settings, moved from Preview Settings]**, then Fullscreen ⤢, then an overflow `⋯`
    menu (Download PNG [Proposed placement, existing function], Reset planner [Existing]).
- **Wall canvas**: sized to fit the remaining space in both dimensions while keeping its aspect ratio (§8.3).
- **Stage footer** (48 px):
  - Left: arrangement summary as small meta text (the existing `aria-live` line, shortened:
    "60 × 72 in · 9 frames · 23 % of wall").
  - Right: the **generation cluster**: `Regenerate` (ghost-light), `Redesign` (ghost-light),
    **`Generate Layout`** (red primary) with an attached `▾` that opens the **Variations** menu
    (see §6.4).

**Right rail: "Inspector" (320 px; 300 px dense)**

- Header: `03 Frame` + `‹ 3 of 9 ›` stepper.
- **Frame navigator**: a horizontal strip of 36 px photo thumbnails (one per frame, numbered under
  each). Selected thumbnail: red 2 px ring plus a burgundy wash. Empty frames show a dashed
  placeholder. With 16 frames it scrolls sideways and the selected one stays in view. Replaces
  `FrameChips` (P13).
- **Tabs**: `Photo · Frame · Mount` (a WAI-ARIA tablist, 32 px):
  - **Photo**: thumbnail (72 px) + Upload / Replace + Remove + DPI/quality line + orientation
    mismatch nudge + drop zone (the whole tab panel is the drop target) + "Fill empty frames with
    samples" switch.
  - **Frame**: Size select + Orientation segmented + Wood finish swatches.
  - **Mount**: Mount switch + Mount colour swatches + Mat margin stepper.
- Footer (sticky inside the rail): `Apply this frame's style to all frames` (secondary,
  full-width) **[Existing action, more prominent and clearly worded]**.

Tabs keep each panel to 3–5 controls, so the inspector never needs to scroll at 600 px tall.

### 3.2 Proportions at the two target viewports

Measured as browser viewport (CSS px). These are the numbers the implementation must hit.

|                                               | **1536 × 735** (compact tier)                                                           | **1280 × 600** (dense tier)                                 |
| --------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Header                                        | 52                                                                                      | 48                                                          |
| Body height                                   | 683                                                                                     | 552                                                         |
| Left rail / right rail                        | 288 / 320                                                                               | 272 / 300                                                   |
| Stage width (with 0 gutters; rails are flush) | 928                                                                                     | 708                                                         |
| Stage toolbar + footer                        | 40 + 48                                                                                 | 36 + 44                                                     |
| Stage padding (y)                             | 2 × 16                                                                                  | 2 × 10                                                      |
| **Available for wall**                        | **928−48 × 563 → 750 × 563** (12×9 ft wall at 4:3)                                      | **708−32 × 452 → 603 × 452**                                |
| Wall area vs today                            | about **+55 %** (today ≈ 600×450 at the top of the page, with no room for the controls) | Today the canvas is cut off and controls are below the fold |

The rails fit without internal scrolling at both sizes with the dense tokens:
left rail at 600 px ≈ 48 (Wall heading) + 36 (dims) + 32 (units) + 36 (paint) + 40 (Arrangement heading) + 2×36 + 40 (AI heading) + 2×(96+18) ≈ 532 px. The rail is allowed to scroll internally if zoom or larger text pushes it over (§8).

### 3.3 Why not keep the bottom action bar

The current bottom bar takes about 110 px of height (with the card) to hold four actions, and two of
them (Preview, Saved) duplicate other entry points. Moving project actions into the header puts them
in the place users expect from editors such as Figma, Canva and Shopify configurators. View actions
go onto the stage, and the bar's height goes back to the wall.

---

## 4. Before vs After (component level)

| Component (file)                                       | Before                                                                                                                 | After                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Page shell** `pages/MemoryWallPage.tsx`              | `min-h-dvh` document. 3-col grid `items-start` plus an action bar below.                                               | `h-dvh grid grid-rows-[auto_minmax(0,1fr)] overflow-hidden` at md+. Body is `grid-cols-[18rem_minmax(0,1fr)_20rem]`. Falls back to document scroll below a minimum height (§8.4). All handlers unchanged.                                                                                                                                                    |
| **Header** `PlannerHeader.tsx`                         | ~100 px. Large logo, 2-line title, translucent blur, Profile only.                                                     | 52 px opaque bar. Compact logo, project title, fit chip, grouped actions (Templates, My Designs, Save, Quote), Profile. The Profile menu keeps "My Designs" (duplicates are fine in a menu) and Sign out.                                                                                                                                                    |
| **StepCard** `StepCard.tsx`                            | Card with a red numbered circle, serif `text-xl` title, border and shadow.                                             | Replaced by `RailSection`: a champagne numeral eyebrow, 17 px serif title, optional right-side "aside" value, hairline separator, no card. It is collapsible only on mobile sheets. `StepCard` stays until nothing references it.                                                                                                                            |
| **Wall config** `ConfigPanels.tsx` WallConfigPanel     | 3 stacked groups with full-size controls. Unit is a 4-button red segmented control.                                    | Same controls at compact density. Unit segmented control uses the neutral thumb. The red unit chip inside `DimensionInput` becomes a muted suffix.                                                                                                                                                                                                           |
| **DimensionInput** `DimensionInput.tsx`                | 44 px, red unit chip.                                                                                                  | 36/32 px, muted unit suffix. Behaviour unchanged (commit on blur/Enter, arrows, clamp message).                                                                                                                                                                                                                                                              |
| **Layout panel** `ConfigPanels.tsx` LayoutPanel        | Style segmented + gap stepper + gap unit + frame count.                                                                | Style segmented → stage toolbar. Gap and Frames stay in the rail as two aligned rows (label left, control right). Gap unit becomes an inline `in                                                                                                                                                                                                             | cm` mini-toggle attached to the stepper. |
| **AI Assistant** `ConfigPanels.tsx` AiAssistantPanel   | 4 tiny thumbnails across, long subtitle, green "New" badge.                                                            | 2×2 larger thumbnails with labels. Subtitle shortened to "Curated for your wall". Badge becomes a champagne "AI" spark. Active preset gets a red 2 px ring plus a check. "All templates →" link.                                                                                                                                                             |
| **CanvasPanel** `CanvasPanel.tsx`                      | Card with title + badge + Save/Reset, canvas, summary, warnings list, **carousel**, 2 tall tiles, full-width Generate. | `Stage`: toolbar (style, view toggles, fullscreen, overflow), canvas fitted to the space, footer (summary + generation cluster). **Carousel removed** (§6). Warnings → fit-chip popover. Save → header. Reset → overflow menu.                                                                                                                               |
| **WallCanvas** `WallCanvas.tsx`                        | Height capped by `maxHeight` CSS. Heavy guide pills.                                                                   | Fits a size container on both axes (§8.3). Guides become thinner (1 px at 40 % charcoal), with smaller pills on a frosted ivory background. The eye-level label sits at the right edge, outside the art. The selected frame's badge is red; other badges are only shown on hover or focus when "badges" is on, and always shown in "badges" mode (see §5.1). |
| **WallSvg** `WallSvg.tsx`                              | Red 3 px selection stroke. Dashed focus ring.                                                                          | Selection: 2 px red stroke + 6 px soft red glow (SVG filter, UI-only, `data-export="exclude"`) + a slight lift (shadow offset). Hover: 1 px champagne outline. Export stays unchanged because the UI layers are excluded.                                                                                                                                    |
| **Generate / Regenerate / Redesign** `CanvasPanel.tsx` | Two 90 px serif tiles + a 52 px full-width red button.                                                                 | A 36 px cluster: `⇄ Regenerate` and `✎ Redesign` as light ghost buttons with tooltips carrying the current subtitles, then **✦ Generate Layout** red primary with a `▾` split for Variations.                                                                                                                                                                |
| **ActionBar** `ActionBar.tsx`                          | 4 big cards (desktop). Fixed bar (phone).                                                                              | **Desktop: removed.** Actions live in the header and stage. **Phone: redesigned** bottom bar (§7.4). Keep `QuoteButton` logic as the shared `RequestQuoteButton`.                                                                                                                                                                                            |
| **FrameSelectionPanel** `FramePanels.tsx`              | 9 stacked groups, nested boxes, number chips.                                                                          | Inspector: header with `‹ n/N ›`, thumbnail navigator, Photo/Frame/Mount tabs, sticky "Apply to all" footer. `PhotoPicker` keeps its upload, error, busy and mismatch logic and is restyled.                                                                                                                                                                 |
| **PreviewSettingsPanel** `FramePanels.tsx`             | Collapsible card with 3 switches.                                                                                      | **Removed as a panel.** The three toggles become the stage toolbar view group (icon + tooltip + `aria-pressed`). They also appear in the mobile "View" sheet with full labels.                                                                                                                                                                               |
| **SegmentedControl** `components/ui`                   | Red filled selected cell, 40 px.                                                                                       | Neutral thumb (white on linen), 32 px, `tone="light" \| "onDark"` for the stage toolbar. Same radio semantics.                                                                                                                                                                                                                                               |
| **Switch** `components/ui`                             | 28×48 red.                                                                                                             | 20×36 charcoal. Same `role="switch"`.                                                                                                                                                                                                                                                                                                                        |
| **NumberStepper** `components/ui`                      | 40 px bordered.                                                                                                        | 32 px linen pill, `size="sm"`. Same commit logic.                                                                                                                                                                                                                                                                                                            |
| **SwatchPicker** `components/ui`                       | Large circles, red check ring.                                                                                         | 24 px, champagne ring, hover tooltip with the name. Same radio group.                                                                                                                                                                                                                                                                                        |
| **Button** `components/ui`                             | `md` 44 px, `lg` 48 px.                                                                                                | Add `size="sm"` (32 px) and `"compact"` (36 px), plus variant `dark`. Existing sizes stay for auth.                                                                                                                                                                                                                                                          |
| **Badge** `components/ui`                              | Pill tones.                                                                                                            | Add a `status` style (dot + label) for fit.                                                                                                                                                                                                                                                                                                                  |
| **Dialogs**                                            | Fullscreen, Templates, Saved, Save.                                                                                    | Keep. Fullscreen: remove the carousel and the ←/→ hint (§6). Restyle headers to the new tokens. Saved dialog renamed "My Designs" (title copy only).                                                                                                                                                                                                         |

---

## 5. Interaction Improvements

### 5.1 Immersive, connected canvas

- **[Existing → refined] Click-to-select frames.** The selection outline becomes clearer (glow + lift).
  Selecting a frame on the canvas scrolls the navigator thumbnail into view and briefly pulses the
  inspector header (200 ms champagne underline) to show the connection.
- **[Proposed] Canvas hint.** On the first visit a small, dismissible coach mark appears on the
  stage: "Tip: click any frame to edit it". It is stored in `localStorage` as a convenience only,
  wrapped in try/catch.
- **[Proposed] Frame hover card.** Hover or focus on a frame shows a tiny label ("Frame 4 · 12×16
  portrait"). It reuses `SceneFrame.label`, which already exists for `aria-label`.
- **[Proposed] Contextual frame toolbar.** With a frame selected, a compact floating toolbar sits
  just above it with: Replace photo, Rotate (toggle orientation), Remove photo. All three dispatch
  existing actions (`frames/setPhoto`, `frames/update {orientation}`). It is hidden in fullscreen and
  on touch screens below md, where the inspector sheet does this job. Implement this in Phase 3,
  after the core layout ships.
- **[Existing] Keyboard:** frames stay `tabIndex=0` with Enter/Space to select. **[Proposed]**
  `[` and `]` select the previous and next frame when focus is on the stage. The same handler drives
  the `‹ ›` in the inspector.

### 5.2 Layout generation

- **Generate Layout** stays the only red button in the workspace. Its loading state ("Finding the
  best layout…", 450 ms, existing) adds a **shimmer sweep** over the wall (CSS gradient, disabled
  under reduced motion). Frames then animate with the existing 480 ms transition.
- The result toast stays (existing, with Undo). It also briefly shows the chosen style in the
  toolbar segmented control, because the existing action changes `layout.style`.
- **Regenerate / Redesign** get tooltips that carry today's subtitles ("Same style, new order" and
  "Try a different composition"). Copy fix for P11: "Shuffle photos & arrangement".
- **AI presets**: hovering a preset tile shows a mini live preview badge ("Fits your wall" or "Too
  wide") using the same `buildScene` check TemplatesDialog already runs. This is [Proposed] and
  cheap, because `buildScene` takes under 1 ms.

### 5.3 Fit and warnings

- The fit chip in the header (`● Fits wall` / `▲ Check fit · 2`) is a button. It opens a popover
  that lists `scene.warnings` with each message and, where it helps, a **quick fix** that runs an
  existing action:
  - TOO_WIDE / TOO_TALL → "Try Generate Layout" (existing `onGenerate`), "Hide sofa" (existing
    `preview/toggle sofa`) when the sofa is on.
  - LOW_COVERAGE → "Add frames" (focuses the Frames stepper).
- Warnings never shift the layout. The chip pulses once when its state changes, and the polite
  `aria-live` summary also announces the change.

### 5.4 Photo workflow

- The whole Photo tab is a drop target (existing drag-and-drop, larger target), with an inset
  dashed champagne border while dragging.
- **[Proposed]** Dropping a file directly onto a frame on the canvas uploads into that frame. It
  uses the existing `usePhotoUpload` and `frames/setPhoto` by frame id, which is already safe
  against reordering.
- Upload progress ("Reading…", existing) shows on the navigator thumbnail too.
- DPI quality is shown as a coloured dot plus text (existing tones) and is also visible on the
  thumbnail as a tiny warning dot when quality is low.

### 5.5 Actions and workflow

| Group     | Actions                                                                      | Location                   |
| --------- | ---------------------------------------------------------------------------- | -------------------------- |
| Project   | Templates, My Designs, Save, Request a Quote, Profile (My Designs, Sign out) | Header                     |
| View      | Layout style, Sofa, Badges, Guides, Fullscreen, Download, Reset              | Stage toolbar (+ overflow) |
| Generate  | Generate (+ Variations), Regenerate, Redesign                                | Stage footer               |
| Edit      | Wall, Arrangement, AI presets                                                | Left rail                  |
| Customise | Frame navigator, Photo / Frame / Mount, Apply to all                         | Inspector                  |

- **Fullscreen + Download** form one preview experience: the stage's ⤢ opens the existing gallery
  dialog, which already contains Download. Download is also in the stage overflow menu for speed,
  using the page's existing `svgRef` and `downloadWallPng`.
- **Save** shows a check-mark morph on success, next to the existing toast with "View".

### 5.6 Micro-interactions (purposeful only)

| Interaction       | Spec                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------- |
| Segmented thumb   | Slides 150 ms `ease-out`                                                                                      |
| Swatch select     | Ring scales in 120 ms; the name in the aside cross-fades                                                      |
| Frame selection   | Outline + glow 160 ms; navigator thumbnail scrolls with `scrollIntoView({block:'nearest', inline:'nearest'})` |
| Layout change     | Existing 480 ms frame transition (keep)                                                                       |
| Generate          | Shimmer over the wall during the 450 ms beat                                                                  |
| Buttons           | 120 ms background/colour; primary hover lifts 1 px with a deeper shadow; active scale 0.98                    |
| Popovers / sheets | 160 ms fade-rise / 220 ms slide-up                                                                            |
| All of the above  | Off under `prefers-reduced-motion` (the global rule already exists)                                           |

### 5.7 Tooltips

Add one small `Tooltip` primitive (no dependency): it appears on hover after a 400 ms delay and
immediately on keyboard focus, Esc dismisses it, it uses `role="tooltip"` and `aria-describedby`,
and it is positioned with CSS (top/bottom placement, flips near edges). Every icon-only control
uses it.

---

## 6. Pagination Removal

### 6.1 What it is

`VariantCarousel` (`features/memory-wall/components/CanvasPanel.tsx` lines ~167–216) renders
`‹ ● ○ ○ ›` and dispatches `layout/setVariant`. `VARIANT_COUNT = 3` (`constants.ts`).
A **variant** is an alternative output of the same layout algorithm:

| Style  | What `variant` changes (`lib/geometry/layouts.ts`)                       |
| ------ | ------------------------------------------------------------------------ |
| Grid   | 1st / 2nd / 3rd best column count                                        |
| Row    | Vertical alignment centre / top / bottom (higher values: shuffled order) |
| Centre | Shuffled satellite order + whether columns hug the focal frame           |
| Salon  | Packing order shuffle + more jitter                                      |

### 6.2 Where variant is used (dependency map)

| Location                                                                                     | Use                                                                                    | Action after removal                                                                                                                                   |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `CanvasPanel.tsx` `VariantCarousel` + `const variant`                                        | UI to change variant                                                                   | **Remove** the component, its usage, and the imports that become unused (`ChevronLeft`, `ChevronRight`, `IconButton`, `VARIANT_COUNT`, possibly `cn`). |
| `dialogs/FullscreenPreviewDialog.tsx`                                                        | Imports `VariantCarousel`; ←/→ keyboard handler; hint "Use ← → to browse arrangements" | **Remove** the carousel, the key handler and the hint. Keep "Esc to close" as a hint.                                                                  |
| `lib/plannerState.ts` `layout.variant`, `layout/setVariant`, `layout/apply`, sanitiser       | State + actions                                                                        | **Keep.** Generate writes `variant` through `layout/apply`. Saved designs persist it. `plannerState.test.ts` tests `setVariant`.                       |
| `lib/geometry/scene.ts` `buildScene`, `suggestLayouts`                                       | Reads variant; Generate scores style × variant                                         | **Keep.** This is the core of Generate Layout.                                                                                                         |
| `lib/savedDesigns.ts`                                                                        | Persists the full state                                                                | **Keep.** Old saved designs with variant 1 or 2 still load and render correctly.                                                                       |
| `layout/regenerate`                                                                          | New seed, **variant unchanged**                                                        | Keep.                                                                                                                                                  |
| `layout/redesign`, `layout/setStyle`, `template/apply`                                       | Reset variant to 0                                                                     | Keep.                                                                                                                                                  |
| `docs/DESIGN_SYSTEM.md` (Motion: "canvas carousel"), `docs/ROADMAP.md`, `docs/RESPONSIVE.md` | Mentions                                                                               | Update the docs text.                                                                                                                                  |

### 6.3 Functional consequence

Today the carousel is the **only manual way** to reach variants 1 and 2. Generate can still land on
them automatically, because it searches all styles × variants. If the carousel is removed with no
replacement, a user can no longer pick, for example, the "4 columns" grid instead of the "3 columns"
grid. That would remove a supported workflow, which the brief forbids.

### 6.4 Recommendation

Remove the dots and arrows in both places, and keep the capability in a less prominent place:

- **Generate Layout split button `▾` → "Variations"** menu (`role="menu"`) with three items:
  "Variation A / B / C" (current one checked), each with a one-line hint from the table in §6.1
  (e.g. "3 columns", "4 columns" for grid, using the computed scene's column count where it is cheap to derive, otherwise generic labels).
  Each item dispatches the existing `layout/setVariant`.
- No reducer, geometry or persistence changes. The `layout/setVariant` action remains.
- On mobile, the same menu appears in the Generate sheet.

If you'd rather drop manual variant picking entirely (accept the loss of that workflow), tell me
before implementation. In that case the split button becomes a plain button and nothing else changes.

---

## 7. Responsive Behaviour

### 7.1 Breakpoints and density tiers

Width decides the **structure**. Height decides the **density**. Text sizes never depend on
viewport height (keeps WCAG 1.4.4, as on the auth pages).

| Width                              | Structure                                                                                                                              |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `< 768` (phone)                    | Preview-first, tabbed bottom sheet, bottom action bar                                                                                  |
| `768–1279` (tablet / small laptop) | Two panes: stage + one tabbed side panel ("Set up · Frame")                                                                            |
| `≥ 1280` (desktop)                 | Three panes (§3.1)                                                                                                                     |
| `≥ 1792` (3xl)                     | Three panes. Rails grow to 320/360 px. The stage stays fluid, with the wall capped at about 1100 px wide so it doesn't look stretched. |

| Height tier (custom variants in `index.css`) | Rule                                            | Effect                                                                                                                                                          |
| -------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `comfortable`                                | `min-height: 48rem` (768 px)                    | 40 px controls, full section spacing, AI thumbnails 2×2 at 4:3                                                                                                  |
| `compact` (default ≥ md)                     | `max-height: 47.99rem`                          | 36 px controls, 52 px header (**1536×735**)                                                                                                                     |
| `dense`                                      | `max-height: 40rem` (640 px)                    | 32 px controls, 48 px header, helper text hidden where redundant (e.g. switch descriptions become tooltips), AI thumbnails 4:3 at reduced height (**1280×600**) |
| `tiny`                                       | `max-height: 33.75rem` (540 px) or zoom ≥ 175 % | Fixed shell turned off → normal page scroll (§8.4)                                                                                                              |

Implementation: CSS custom properties set per tier on a `.planner-scope` root
(`--ctl-h`, `--rail-pad`, `--section-gap`, `--header-h`). Primitives read them with fallbacks,
the same proven pattern as `.auth-scope`.

### 7.2 Tablet (768–1279)

```
┌───────────────────────────────────────────────────────────┐
│ ☾  Living Room Gallery Wall  ● Fits   Templates  Designs  [Save] [Quote] ◉ │
├─────────────────────────────────────────┬─────────────────┤
│ Grid·Salon·Centre·Row        👁 # 📏 ⤢ ⋯│ [Set up][Frame] │
│                                         │                 │
│               WALL                      │  (tab content,  │
│                                         │   scrolls       │
│                                         │   internally)   │
│ 60×72 in · 9 frames   [⇄][✎][✦ Generate▾]│                 │
└─────────────────────────────────────────┴─────────────────┘
                fluid                           320 px
```

- The side panel holds two tabs: **Set up** (Wall, Arrangement, AI Layouts) and **Frame** (the
  inspector). Selecting a frame on the canvas switches to the Frame tab automatically.
- At 768–1023 wide the header collapses Templates / Designs into a `⋯` menu. Save and Quote stay visible.
- Portrait tablets (e.g. 820×1180): stacked layout, with the stage on top (≈ 55 % height) and the
  tabbed panel below as a fixed-height region with internal scrolling. Same component as the phone sheet, docked.

### 7.3 Phone portrait (< 768)

```
┌─────────────────────────┐
│ ☾  Living Room Wall  ● ◉│ 48px
├─────────────────────────┤
│ Grid·Salon·Centre·Row ⋯ │ 36px
│                         │
│         WALL            │ ~42dvh (fits, aspect kept)
│                         │
│ 60×72 in · 9 frames  ⤢  │
├─────────────────────────┤
│ [Wall][Layout][Frame][View] │ sheet tabs (sticky)
│                         │
│  sheet content          │ scrolls internally
│                         │
├─────────────────────────┤
│ [⇄][✎] [✦ Generate] [Quote→] │ bottom bar + safe area
└─────────────────────────┘
```

- **Preview first:** the stage is always visible and the controls live in a **docked sheet** below
  it. The sheet can be dragged up to cover about 85 % of the height ("expanded editing") and back down.
  It uses a native `<button>` handle plus `aria-expanded`, and tapping the handle toggles it, so
  dragging is optional.
- **Sheet tabs:** Wall · Layout (Arrangement + AI) · Frame (navigator + Photo/Frame/Mount) · View
  (Sofa, Badges, Guides, Fill with samples, with full labels).
- **Bottom bar:** Regenerate and Redesign (icons + tooltips/labels), **Generate** (red primary),
  **Quote** (charcoal). Templates, My Designs, Save and Download sit under the header `⋯` menu.
  This fixes P18: the most important mobile actions are now one tap away.
- Tapping a frame on the canvas opens the sheet on the Frame tab at medium height.

### 7.4 Phone landscape and short screens

- **Landscape phones** (`max-height: 30rem` and landscape): two columns. The stage takes the left
  60 %, and the tabbed panel the right 40 % with internal scroll. The bottom bar becomes a slim
  action column at the bottom of the panel. The header shrinks to 40 px (logo mark only + title).
- **Virtual keyboard:** add `interactive-widget=resizes-content` to the viewport meta
  (`index.html`), so `dvh` shrinks when the keyboard opens. The focused input is scrolled into view
  inside its own scroll container (`scrollIntoView({block:'nearest'})` on focus for inputs in sheets).
  The bottom bar hides while an input has focus on phones, so it doesn't sit on top of the keyboard.

### 7.5 Zoom, large text, accessibility

- Every size is set in `rem`, so 200 % zoom at 1280 wide reflows into the 640 px structure (phone/tablet). This is expected and correct.
- At ≥ 175 % zoom on desktop the `tiny` height tier switches to normal page scrolling instead of
  clipping (§8.4).
- Minimum targets: 24 px (WCAG 2.5.8). 32 px controls exceed it. Touch layouts use 40–44 px.
- Focus order follows visual order: header → left rail → stage toolbar → canvas frames → stage
  footer → inspector. On phones it is header → stage → sheet → bottom bar.
- Forced-colors: keep the existing `forced-colors:` outlines on fields and switches.

---

## 8. No-Scroll Strategy

### 8.1 Rules

1. At ≥ md and height ≥ 540 px, **the document never scrolls.** The shell is `h-dvh overflow-hidden`.
2. **The stage never scrolls.** The wall shrinks to fit (it is vector art, so it stays crisp).
3. **Rails and sheets may scroll internally** (`overflow-y-auto overscroll-contain`) when content,
   zoom or text size requires. They show a 12 px fade at the top or bottom edge when more content
   exists (scroll-driven or IntersectionObserver sentinels), so the scrolling is visible.
4. **Nothing essential is clipped.** Primary actions (Generate, Save, Quote) live in fixed regions
   (header, stage footer, bottom bar) that never scroll away.
5. Dialogs keep their own internal scrolling (already the case: `Dialog lg max-h`).

### 8.2 Shell skeleton (target structure)

```tsx
// MemoryWallPage (structure only; handlers unchanged)
<div className="planner-scope grid h-dvh grid-rows-[var(--header-h)_minmax(0,1fr)] overflow-hidden
                tiny:h-auto tiny:overflow-visible">
  <PlannerHeader … />
  <div className="grid min-h-0 grid-cols-1 md:grid-cols-[minmax(0,1fr)_20rem]
                  xl:grid-cols-[18rem_minmax(0,1fr)_20rem]">
    <SetupRail className="hidden min-h-0 overflow-y-auto xl:block" />   {/* xl only */}
    <Stage className="min-h-0" />                                        {/* grid rows: toolbar / canvas 1fr / footer */}
    <InspectorRail className="min-h-0 overflow-y-auto" />               {/* tabs on md, inspector on xl */}
  </div>
</div>
```

`min-h-0` / `minmax(0,1fr)` on every flex or grid child is what lets inner regions scroll instead of
stretching the page. Its absence is the reason the current layout scrolls (P1).

### 8.3 Fitting the wall in both dimensions

The current `WallCanvas` limits height with `maxHeight` and derives `maxWidth` from it. In the
stage, make the canvas area a **size container** and compute the wall box from both axes:

```css
.stage-canvas {
  container-type: size;
  display: grid;
  place-items: center;
}
.stage-wall {
  width: min(100cqw, 100cqh * var(--wall-ratio));
  aspect-ratio: var(--wall-ratio);
}
```

`--wall-ratio` = `W / H` is set inline, as the aspect ratio already is today. Changing the wall from
12×9 ft to 40×8 ft then reflows instantly without page scroll. The guide and badge overlays already
use `cqi` units and keep working. Keep the `maxHeight` prop for the fullscreen dialog (no change there).

### 8.4 Escape hatch

When the viewport is too short for the minimum shell (`max-height: 33.75rem`), or when the user
zooms heavily, the shell sets `height:auto; overflow:visible`. The page scrolls normally, rails stop
scrolling internally, and the header stays sticky. This is better than a tiny canvas or clipped
controls.

---

## 9. Preservation Checklist

Each item was verified in code. All must work after the redesign.

**Wall configuration**

- [ ] Wall width/height typed in the display unit, stored in inches, commit on blur/Enter, Arrow keys nudge by unit step, range clamp + message (`DimensionInput`, `wall/setSize`, `PLANNER_RULES`)
- [ ] Paint shade (7) → canvas wall colour, also multiplies the room photo (`wall/setPaint`)
- [ ] Display unit ft/in/cm/m → inputs, guides, summary, dialogs (`unit/set`)

**Layout**

- [ ] Layout style Grid/Salon/Centre/Row, resets variant and clears templateId (`layout/setStyle`)
- [ ] Frame gap stepper 0–12 in, displayed in in or cm with correct conversion and step (`layout/setGap`, `layout/setGapUnit`)
- [ ] Number of frames 1–16, new frames copy the last frame's style + sample photo, selection clamped (`frames/setCount`)
- [ ] Generate Layout: 450 ms beat, best of style × variant, toast with fit/coverage, Undo (`suggestLayouts`, `layout/apply`)
- [ ] Regenerate: new seed (`layout/regenerate`)
- [ ] Redesign: next style, variant 0, new seed (`layout/redesign`)
- [ ] Manual variant selection, kept via the Variations menu (`layout/setVariant`), §6.4
- [ ] AI Layout presets apply templates, keep the user's photos per slot, active preset highlighted while `templateId` matches, Undo toast (`template/apply`, `AI_LAYOUT_PRESETS`)

**Frames and photos**

- [ ] Select frame from the navigator, the canvas (click, Enter/Space) and ‹ › (`frames/select`)
- [ ] Upload (JPEG/PNG/WebP ≤ 25 MB, min side check), busy state, errors, drag-and-drop, same file re-selectable, by frame id (`usePhotoUpload`, `frames/setPhoto`)
- [ ] Remove photo, disabled when empty
- [ ] DPI / print-quality feedback for uploads; sample info line
- [ ] Orientation mismatch nudge → switch frame orientation
- [ ] Object URLs revoked on unmount (page-level `usePhotoUpload`)
- [ ] Fill empty frames with samples (`samples/toggle`)
- [ ] Frame size (8), orientation, wood finish (8) (`frames/update`; size/orientation clear templateId)
- [ ] Mount on/off, mount colour (4), mat margin 0–6 in step 0.5; colour and margin disabled when mount off (`frames/updateMount`)
- [ ] Apply to all frames (`frames/applyToAll`)

**Preview**

- [ ] Sofa toggle changes geometry (min bottom clearance), not only visuals (`preview/toggle sofa` → `buildScene`)
- [ ] Index badges toggle; label shows the 1–N count
- [ ] Dimension guides toggle (also affects PNG export)
- [ ] Fit badge + warnings (TOO_WIDE, TOO_TALL, OVERLAP, LOW_COVERAGE)
- [ ] `aria-live` arrangement summary
- [ ] Frame position animation on change
- [ ] Fullscreen gallery dialog with view toggles, Download PNG (busy/done/error states, feedback inside the dialog)

**Project**

- [ ] Save design dialog (title, upload warning), rename state title, toast with "View" (`savedDesignsStore.save`, `design/rename`)
- [ ] My Designs dialog: search, open with Undo, delete with inline confirm, "Save current" (`SavedDesignsDialog`)
- [ ] All Templates dialog: category filter, live per-wall previews, fit status, apply with Undo
- [ ] Reset with Undo (`reset`)
- [ ] Request a Quote: current placeholder toast with "Save design" action
- [ ] Profile menu: keyboard menu pattern, My Designs, Sign out (clears tokens → /login)
- [ ] Toasts reachable (not hidden under modal top layer)

**Non-functional**

- [ ] All existing tests pass (`npm run check`). Note: `plannerState.test.ts` covers `setVariant`
- [ ] PNG export excludes UI layers (`data-export="exclude"`), so new selection and glow layers must carry it
- [ ] Memoised `WallSvg` still skips re-renders on selection/unit/toggle changes (stable `onSelect`)
- [ ] Reduced motion, focus-visible rings, forced-colors, radio/switch semantics

---

## 10. Required Assets

The redesign can ship with **no new assets**. Everything above uses existing images, lucide icons
and the two installed fonts. The following would make a noticeable difference, listed by impact:

| #   | Asset                                                                                                          | Why                                                                                                                                                                                                                                 | Spec                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | **Empty room photo (no furniture)** + **sofa as transparent cut-out** _(already requested as W4 in ASSETS.md)_ | Today the sofa is baked into the room photo, so "Sofa off" shows a flat wall and the room can't be lit consistently. With layers the stage looks like a real interior at any wall ratio, and the sofa can be scaled to exactly 84″. | Room: ≥ 2400 px wide WebP, straight-on, neutral light, floor visible, plain wall. Sofa: transparent PNG/WebP, known width (84″), straight-on, same light direction. |
| A2  | **Optional second room scene** (e.g. dining sideboard or bed headboard)                                        | Not required. Only if you want a "Room: Living / Bedroom" view option later. **Not planned in this redesign** (it would be new functionality).                                                                                      | Same spec as A1                                                                                                                                                     |
| A3  | **Compact logo mark (crescent only) as SVG**                                                                   | The phone and dense headers need a 28–32 px mark. Cropping the lockup isn't crisp.                                                                                                                                                  | Vector SVG, brand-600 on transparent, plus a white variant                                                                                                          |
| A4  | **Higher-resolution AI preset thumbnails**                                                                     | The 2×2 tiles render about 120×90 CSS px (240×180 @2x). The current files are 349×284, which is enough but tight on 3x screens.                                                                                                     | 4 files at 720×540 WebP, same compositions                                                                                                                          |
| A5  | **One or two more landscape sample photos**                                                                    | Only `frame-08` is landscape, so landscape frames repeat the same image.                                                                                                                                                            | ≥ 1448×1086, same grading as the existing set                                                                                                                       |
| A6  | **Brand decision on display type**                                                                             | Playfair Display is a stand-in from the mockup. If Moonlight has an official serif, now is the time to swap `--font-display`.                                                                                                       | Font files (WOFF2) + licence, or confirm Playfair                                                                                                                   |

I'd ask for A1 and A3 before implementation. A4–A6 are optional and can come later.

---

## 11. Implementation Roadmap

Every phase leaves the app working and passes `npm run check`. No business logic, reducer, geometry,
API or auth changes in any phase.

### Phase R1: Foundations (tokens + primitives) · _low risk_

| File                                                                | Change                                                                                                                            |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `styles/theme.css`                                                  | Add `ivory-*`, `champagne-*`, `charcoal-*`, `stage-*` tokens, popover shadow, `--radius-control`.                                 |
| `index.css`                                                         | Add `.planner-scope` density properties; custom variants `compact`, `dense`, `tiny`; scroll-fade utility.                         |
| `components/ui/Button.tsx`                                          | Add `size="sm" \| "compact"`, variant `dark`. Existing variants untouched.                                                        |
| `components/ui/SegmentedControl.tsx`                                | Add `appearance="neutral"` (thumb style) + `tone="onDark"`; size `xs`. Default stays as today until R3 switches the planner over. |
| `components/ui/Switch.tsx`, `NumberStepper.tsx`, `SwatchPicker.tsx` | Add `size="sm"` / `appearance` props reading density variables.                                                                   |
| `components/ui/Tooltip.tsx` _(new)_                                 | Lightweight tooltip (§5.7).                                                                                                       |
| `components/ui/Menu.tsx` _(new)_                                    | Extract the menu-button pattern from `PlannerHeader` ProfileMenu for reuse (overflow, Variations, phone ⋯).                       |
| `components/ui/Tabs.tsx` _(new)_                                    | WAI-ARIA tablist with roving focus (inspector, tablet panel, phone sheet).                                                        |
| `docs/DESIGN_SYSTEM.md`                                             | New palette, red usage rules, type roles, density tiers.                                                                          |

### Phase R2: Shell and no-scroll layout · _medium risk_

| File                                             | Change                                                                                                                               |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| `pages/MemoryWallPage.tsx`                       | New shell grid (§8.2). Same handlers and dialogs. Pass `svgRef` + download handler to the stage overflow.                            |
| `components/PlannerHeader.tsx`                   | 52 px opaque header with title, fit chip, Templates, My Designs, Save, Quote, Profile. New props: `title`, `scene`, `on*` callbacks. |
| `components/Stage.tsx` _(new, from CanvasPanel)_ | Toolbar / canvas / footer grid. Style segmented, view toggles, fullscreen, overflow (Download, Reset).                               |
| `components/WallCanvas.tsx`                      | Add a `fit="container"` mode using a size container (§8.3). Keep the `maxHeight` mode for the dialog.                                |
| `components/ActionBar.tsx`                       | Desktop row removed. Phone bar redesigned (Regenerate, Redesign, Generate, Quote). `RequestQuoteButton` extracted.                   |
| `index.html`                                     | Viewport meta `interactive-widget=resizes-content`.                                                                                  |

### Phase R3: Panels redesign · _medium risk_

| File                                 | Change                                                                                                                                                                                                                                                                             |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `components/RailSection.tsx` _(new)_ | Replaces `StepCard` in the rails (numeral eyebrow, serif title, aside).                                                                                                                                                                                                            |
| `components/ConfigPanels.tsx`        | Wall + Arrangement + AI Layouts restyled. Layout style moved out. 2×2 presets + "All templates" link.                                                                                                                                                                              |
| `components/DimensionInput.tsx`      | Compact height, muted unit suffix.                                                                                                                                                                                                                                                 |
| `components/FramePanels.tsx`         | Split into `InspectorPanel` (header, navigator, tabs, footer), `FrameNavigator` (thumbnail strip, replaces `FrameChips`), `PhotoTab` (wraps the existing `PhotoPicker`), `FrameTab`, `MountTab`. `PreviewSettingsPanel` removed (its toggles now live in Stage + mobile View tab). |
| `components/StepCard.tsx`            | Delete once it has no references.                                                                                                                                                                                                                                                  |

### Phase R4: Pagination removal + generation cluster · _low risk_

| File                                                             | Change                                                                                                                                               |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `components/CanvasPanel.tsx` → `Stage.tsx`                       | Remove `VariantCarousel`. Add the `GenerateCluster` (Regenerate, Redesign, Generate split with the Variations menu dispatching `layout/setVariant`). |
| `components/dialogs/FullscreenPreviewDialog.tsx`                 | Remove the carousel import/usage, the ←/→ handler and its hint. Restyle the header to the new tokens.                                                |
| `docs/DESIGN_SYSTEM.md`, `docs/RESPONSIVE.md`, `docs/ROADMAP.md` | Replace carousel mentions. Rewrite the Memory Wall section of RESPONSIVE.md with §7.                                                                 |

### Phase R5: Mobile, tablet, short screens · _medium risk_

| File                                 | Change                                                                                                          |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `components/MobileSheet.tsx` _(new)_ | Docked, expandable sheet with tabs (Wall, Layout, Frame, View), internal scroll, keyboard-aware.                |
| `pages/MemoryWallPage.tsx`           | Replace `collapsible = !isTabletUp` with breakpoint structures. `useMediaQuery` stays for mount-only decisions. |
| Tablet two-pane                      | `InspectorRail` gains a "Set up / Frame" tab mode below xl. Selecting a frame switches to the Frame tab.        |
| Landscape phone                      | Two-column variant via `@media (max-height:30rem) and (orientation:landscape)`.                                 |

### Phase R6: Canvas polish + interactions · _low–medium risk_

| File                                                   | Change                                                                             |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `components/WallSvg.tsx`                               | Selection glow/lift and champagne hover outline, all with `data-export="exclude"`. |
| `components/WallCanvas.tsx`                            | Lighter guides. Badge emphasis for the selected frame. Generate shimmer overlay.   |
| `components/FitStatus.tsx` _(new)_                     | Header chip + warnings popover with quick fixes (existing actions only).           |
| `components/FrameContextToolbar.tsx` _(new, optional)_ | Floating Replace / Rotate / Remove over the selected frame (desktop).              |
| Canvas drop-to-frame                                   | Wire `onDrop` on frames → existing upload path (by frame id).                      |
| First-visit tip                                        | Dismissible coach mark; `localStorage` in try/catch.                               |

### Phase R7: Verification

- `npm run check` (typecheck, lint, tests, format).
- Add component tests: Variations menu dispatches `setVariant`; inspector tabs keep
  `selectedIndex`; view toggles dispatch `preview/toggle`; shell renders no carousel.
- Browser checks (Playwright via the existing scratchpad setup, Edge channel) at **1536×735,
  1280×600**, 1440×900, 1920×1080, 1024×768, 820×1180, 390×844, 844×390, 360×640, plus 200 % zoom
  at 1280×720. Assert `document.scrollingElement.scrollHeight <= innerHeight` at md+ heights ≥ 540,
  and that Generate, Save and Quote are within the viewport.
- Keyboard-only walkthrough of all workflows in §9. Reduced motion and forced-colors spot checks.

### Effort and order

R1 → R2 → R4 → R3 → R5 → R6 → R7. R4 is small and removes the carousel early. R3 and R5 are the
largest. R6 can be trimmed if time is short without losing anything from the brief.

---

### Open decisions for you (each has a default I'll use if you don't answer)

1. **Variant picking**: keep it in a Generate "Variations" menu (default) or drop it entirely (§6.4).
2. **Request a Quote styling**: charcoal solid in the header (default) or red solid with Generate as
   charcoal. Only one of the two should be red.
3. **Terminology**: rename "My Saved Templates" to **"My Designs"** in the UI copy (default yes,
   copy only, no data change).
4. **Assets A1 + A3**: supply them before R2/R6, or I proceed with the current room photo and a
   cropped lockup.
