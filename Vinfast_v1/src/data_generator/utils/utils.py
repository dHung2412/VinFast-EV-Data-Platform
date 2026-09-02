from __future__ import annotations

import hashlib
import numpy as np


def make_rng(*seeds) -> np.random.Generator:
    """Deterministic RNG from arbitrary seed parts."""
    h = hashlib.sha256("|".join(str(s) for s in seeds).encode()).digest()
    seed = int.from_bytes(h[:8], "big")
    return np.random.default_rng(seed)


def stable_id(prefix: str, *parts: str) -> str:
    """Stable short id from parts."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return f"{prefix}-{h}"
