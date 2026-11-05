/**
 * Media queries that JS needs to know about. Each one must match the CSS variant of the
 * same name in src/index.css. Change both together.
 */
export const MEDIA = {
  /** `hero-fits:` variant: ≥ lg AND landscape ≥ 4:3 (see docs/ASSETS.md W2). */
  heroFits: '(min-width: 64rem) and (min-aspect-ratio: 4/3)',
} as const
