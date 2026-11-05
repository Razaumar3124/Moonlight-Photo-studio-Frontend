/**
 * Deterministic randomness so a (seed, variant) pair always yields the same arrangement:
 * saved designs reopen identically and "Regenerate" only changes what it should.
 */

/** mulberry32: tiny, fast, good-enough PRNG. Returns floats in [0, 1). */
export function createRng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Combine numbers into a 32-bit seed (FNV-1a style). */
export function mixSeed(...parts: number[]): number {
  let h = 0x811c9dc5
  for (const p of parts) {
    h ^= p >>> 0
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** Fisher–Yates shuffle (returns a new array). */
export function shuffle<T>(items: readonly T[], rng: () => number): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    const a = out[i] as T
    out[i] = out[j] as T
    out[j] = a
  }
  return out
}

export function newSeed(): number {
  return Math.floor(Math.random() * 0xffffffff) >>> 0
}
