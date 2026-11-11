"""Deterministic PRNG matching the frontend TypeScript mulberry32 and mixSeed.

Ensures that (seed, variant) pairs produce identical layouts across frontend and backend.
"""

from collections.abc import Callable, Sequence


def _imul(a: int, b: int) -> int:
    """32-bit signed integer multiplication (matching JavaScript Math.imul)."""
    a = a & 0xFFFFFFFF
    b = b & 0xFFFFFFFF
    res = (a * b) & 0xFFFFFFFF
    if res >= 0x80000000:
        res -= 0x100000000
    return res


def create_rng(seed: int) -> Callable[[], float]:
    """mulberry32 PRNG. Returns floats uniformly distributed in [0, 1)."""
    a = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = _imul(t ^ ((t & 0xFFFFFFFF) >> 15), t | 1)
        t = (t ^ (t + _imul(t ^ ((t & 0xFFFFFFFF) >> 7), t | 61))) & 0xFFFFFFFF
        return float((t ^ ((t & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def mix_seed(*parts: int) -> int:
    """Combine numbers into a 32-bit unsigned seed (FNV-1a style)."""
    h = 0x811C9DC5
    for p in parts:
        h = (h ^ (p & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = _imul(h, 0x01000193) & 0xFFFFFFFF
    return h


def shuffle[T](items: Sequence[T], rng: Callable[[], float]) -> list[T]:
    """Fisher–Yates shuffle returning a new list, driven by the provided PRNG."""
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = int(rng() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out


def new_seed() -> int:
    """Generate a random 32-bit unsigned seed."""
    import secrets

    return secrets.randbits(32)
