# Assets

## Rules

1. **Images and SVGs used by components → `frontend/src/assets/`.** Vite fingerprints them for
   long-term caching, and a broken path fails the build instead of production.
2. **Components never import image files directly.** They import from the area manifest:
   [`brand.ts`](../frontend/src/assets/brand.ts), [`auth.ts`](../frontend/src/assets/auth.ts) or
   [`memoryWall.ts`](../frontend/src/assets/memoryWall.ts). Each records the asset's size,
   alt text, and responsive variants:
   ```tsx
   import { authAssets } from '@/assets/auth'
   const { hero } = authAssets.login
   <img src={hero.src} srcSet={hero.srcSet} sizes="(min-width:1024px) 50vw, 0px"
        width={hero.width} height={hero.height} alt={hero.alt} fetchPriority="high" />
   ```
3. **Raster images go through `vite-imagetools`** at build time (query string in the manifest).
   Sources are never modified. Drop in a bigger or better source and the build output improves automatically.
4. **`frontend/public/`** is only for files that need a fixed URL: favicon, apple-touch-icon,
   OG image, robots.txt.
5. **Naming:** `kebab-case`, descriptive. Decorative ornaments use `alt=""` + `aria-hidden`.

## Folder layout (as delivered and kept)

The delivered assets are grouped by screen rather than by the type-based layout proposed in
Phase 0. We kept that layout as-is: it maps 1:1 to the reference designs, and the manifest hides
the paths from components anyway.

```
frontend/src/assets/
├── types.ts                     ← ImageAsset / HeroImageAsset / SamplePhotoAsset
├── brand.ts  auth.ts  memoryWall.ts   ← manifests (the only importers of image files;
│                                  split per area so pages don't bundle each other's assets)
├── icons/
│   └── google-g.svg             added in Phase 1 (official Google "G")
└── images/
    ├── logo.svg
    ├── login/                   hero + login ornaments
    ├── register/                hero + register ornaments
    └── memory_wall/
        ├── background-wall-plain.webp
        ├── frames/              sample photos frame-01 … frame-10
        └── layouts/             AI Layout Assistant thumbnails
```

New assets: put them in the folder of the screen that uses them. Anything used by 2+ screens
goes in `images/` (like `logo.svg`) or `icons/`, then gets added to the matching manifest (`brand.ts` for shared).

## Inventory & verification (Phase 1)

Checked against the reference designs at 1×/2× and against the original ASSETS.md checklist.

| Asset                                      | Source                         | Verdict            | Notes                                                                                                                                                                                                                     |
| ------------------------------------------ | ------------------------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `images/logo.svg`                          | 353×132 SVG, 8 KB              | 🟡 Usable          | **Auto-traced from a raster:** stair-stepped edges are visible at ≥2× on the auth screens. Fine at header size. It also omits the thin rule before "PHOTO STUDIO". → **W1**                                               |
| `login/background-frames.webp`             | 928×941, lossless, 865 KB      | 🟡 Usable          | Tagline **baked into the image**. Resolution is too low for a crisp ½-screen hero on 2× displays (needs ~1600 px). Re-encoded to 34–87 KB WebP at build. → **W2**                                                         |
| `register/background-living-room.webp`     | 935×937, lossless, 962 KB      | 🟡 Usable          | Same as the login hero (baked tagline, low resolution). → **W2**                                                                                                                                                          |
| `login/leaf-top-right.svg`                 | 133×133 SVG                    | 🟡 Usable          | Traced, with slightly jagged edges. Acceptable as a faint ornament.                                                                                                                                                       |
| `login/leaf-bottom-center.svg`             | 88×121 SVG                     | 🟡 Usable          | Traced. Acceptable as an ornament.                                                                                                                                                                                        |
| `login/wave-red-bottom-right.svg`          | 421×118 SVG                    | 🔴 **Unusable**    | The trace **captured UI text**: part of the "Create an account" link and a stray dot are inside the file. → **W3**                                                                                                        |
| `register/wave-red-top-right.svg`          | 210×181 SVG                    | ✅ Good            | Clean vector with gradients.                                                                                                                                                                                              |
| `register/wave-red-bottom-right.svg`       | 164×142 SVG                    | ✅ Good            | Clean vector. Also used on Login (W3).                                                                                                                                                                                    |
| `register/leaf-top-left.svg`               | 237×191 SVG                    | ✅ Good            | Fine line ornament.                                                                                                                                                                                                       |
| `register/wave-subtle-bottom-left.svg`     | 384×151 SVG                    | ✅ Good            | Fine line ornament.                                                                                                                                                                                                       |
| `memory_wall/background-wall-plain.webp`   | 1466×667, 128 KB               | 🟡 Usable          | Sofa, plant, and lamp are **baked in**, so the "84″ Reference Scale Sofa" toggle can't hide the sofa. A photo can't be repainted for **Paint Shade**, and its 2.2:1 ratio doesn't match a 12×9 ft wall (1.33:1). → **W4** |
| `memory_wall/frames/frame-01…05.webp`      | 768×1024, 69–135 KB            | ✅ Good            | Sample photos (portrait).                                                                                                                                                                                                 |
| `memory_wall/frames/frame-06,07,09,10.png` | 1086×1448, **2.2–2.5 MB each** | ✅ Good (heavy)    | Re-encoded to ≤640 px WebP at build (22–66 KB). Sources untouched.                                                                                                                                                        |
| `memory_wall/frames/frame-08.png`          | 1448×1086                      | ✅ Good            | The only **landscape** sample. Useful for the Portrait/Landscape toggle.                                                                                                                                                  |
| `memory_wall/layouts/ai-*.webp` (4)        | ≈349×284, 15–24 KB             | ✅ Good            | Balanced Grid, Creative Salon, Centre Focus, Minimal Row. Crisp at 2× for the ~84 px tiles.                                                                                                                               |
| `public/favicon.svg`                       | —                              | 🔴 **Was missing** | Still the Vite default. → **W5**                                                                                                                                                                                          |

> "frames/" contains **photos**, not frame graphics. Frame mouldings are drawn in CSS (border +
> wood colour from `WOOD_FINISHES`), which keeps every finish/size combination free.

### Missing items

| Item                                                                                              | Needed for                   | Status / workaround                                                                                           |
| ------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Google "G" icon                                                                                   | "Continue with Google"       | ✅ Added `icons/google-g.svg` (official four-colour mark)                                                     |
| UI icons (user, lock, mail, eye-off, grid, bookmark, reset, download, expand, sparkles, chevrons) | All screens                  | ✅ `lucide-react` installed. Import per icon: `import { Lock } from 'lucide-react'`                           |
| Favicon / apple-touch-icon                                                                        | Browser tab, iOS home screen | 🟡 Temporary favicon added (W5). apple-touch-icon still missing.                                              |
| OG / share image (1200×630)                                                                       | Link previews                | ⚪ Not blocking. Needed before launch.                                                                        |
| Profile avatar placeholder                                                                        | Planner header               | ✅ Not an asset: use a lucide `CircleUserRound` icon, or the user's initials                                  |
| Paint / wood / mount swatch colours                                                               | Planner                      | ✅ Sampled from the mockup into `features/memory-wall/constants.ts` (wood is temporary, see API_ALIGNMENT M8) |
| Wall without furniture + transparent sofa cut-out                                                 | Planner canvas (W4)          | 🟡 Requested                                                                                                  |

## Workarounds (so Phases 2–4 aren't blocked)

**W1 — Traced logo.** Use `logo.svg` as-is via `brandAssets.logo`. Cap its rendered width at
~240 px on auth screens to keep the stair-stepping subtle. Render "— EST. 1985 —" as HTML text
(it isn't in the file anyway). _Ask:_ the original vector logo (AI/EPS/PDF/SVG from the designer).

**W2 — Baked-in hero taglines.** Show the photos as delivered and **don't** overlay the same
text in HTML (it would double up). The tagline is in each asset's `alt`, so screen readers still
get it. Measured text bounds: login spans x 24–66%, register spans x 24–89% (y ≈ 51–63% for both). So:

- render with `object-cover` and the per-asset `objectPosition` from the manifest (login
  `40% 40%`, register `75% 40%`);
- show the hero only under the `hero-fits` variant (`hidden hero-fits:block`): **≥ lg and a
  landscape viewport ≥ 4:3**. That keeps the 50%-width panel at ≥ 0.66:1, the narrowest ratio
  where the register tagline survives. Portrait tablets and near-square windows get the
  form-only layout, like phones, and never download the image.
  _Ask:_ the same two photos **without text**, at ≥ 1920 px on the long edge. The tagline then
  becomes live text (responsive, translatable, crisp), and the manifest/srcset picks up the new
  size by editing two numbers.

**W3 — Broken login wave.** Login uses the clean `register/wave-red-bottom-right.svg` instead.
The manifest already points `authAssets.decorations.waveRedBottomRight` at it.
`login/wave-red-bottom-right.svg` is left in place but referenced nowhere. _Ask:_ a clean
re-export, or confirm the shared wave is fine (the two screens look near-identical there).

**W4 — Planner room photo.** The canvas is drawn in layers:

1. a CSS wall: `background-color` = selected paint shade, plus a soft radial-gradient "light
   from window" overlay so it isn't flat;
2. the frames, positioned in inches → % of wall size;
3. when "Reference Scale Sofa" is ON, `background-wall-plain.webp` sits at the bottom with
   `mix-blend-mode: multiply` over the paint colour. This tints the room to the chosen shade
   and keeps the sofa, lamp, and plant as context.

With the toggle OFF, only the clean painted wall shows. _Ask:_ (a) the same room with
**no furniture**, and (b) the sofa as a **transparent PNG/WebP** with its real width
(84″) so it can be scaled to the wall accurately.

**W5 — Favicon.** Temporary `public/favicon.svg`: a brand-crimson rounded tile with a cream
crescent, echoing the logo mark. _Ask:_ the favicon/app icon from the vector logo (also a
180×180 apple-touch-icon).

## Requests for the designer (summary)

1. Vector source of the logo (W1). This unblocks a crisp logo, favicon, and app icons.
2. Both auth hero photos **without** baked text, ≥ 1920 px (W2).
3. Clean export of the login bottom-right wave, or OK to reuse the register one (W3).
4. Empty room/wall image + standalone sofa cut-out with known real-world width (W4).
5. OG share image 1200×630 (pre-launch).
