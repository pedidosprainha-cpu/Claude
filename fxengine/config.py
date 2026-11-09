"""Engine settings. Every knob that changes a decision lives here."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_cache() -> str:
    return os.environ.get("FXENGINE_CACHE", os.path.join(os.getcwd(), ".cache", "fxengine"))


GRADES = ((65, "A+"), (55, "A"), (45, "B"), (35, "C"), (0, "D"))


def grade(score: float) -> str:
    return next(g for t, g in GRADES if score >= t)


@dataclass
class Settings:
    # --- account / risk ---------------------------------------------------
    balance: float = 10_000.0
    account_ccy: str = "USD"
    risk_pct: float = 1.0              # % of balance risked per trade

    # --- scoring ------------------------------------------------------------
    weights: dict = field(default_factory=lambda: {
        "technical": 0.40, "quant": 0.20, "strength": 0.20, "fundamental": 0.20,
    })
    tf_weights: dict = field(default_factory=lambda: {
        "M5": 0.10, "M15": 0.25, "H1": 0.30, "H4": 0.20, "D1": 0.15,
    })
    min_score: float = 45.0            # below this: "sem trade" (grade C/D)

    # --- execution gates ------------------------------------------------------
    event_block_before_min: int = 45   # high-impact event this close ahead -> block
    event_block_after_min: int = 20    # ... or this recently released -> block
    max_spread_to_sl: float = 0.25     # spread / stop distance hard limit
    max_quote_age_s: int = 600         # older quote => market treated as closed
    min_rr_tp1: float = 1.0

    # --- edge study -------------------------------------------------------------
    use_edge: bool = True
    edge_max_hold_bars: int = 48       # H1 bars
    edge_prior_strength: float = 12.0  # Beta-prior pseudo trades toward break-even

    # --- data -------------------------------------------------------------------
    use_news: bool = True
    use_cot: bool = True
    offline: bool = False              # synthetic data (demo / tests)
    seed: int = 7
    workers: int = 8
    timeout: float = 20.0
    cache_dir: str = field(default_factory=_default_cache)

    # --- output -----------------------------------------------------------------
    top_n: int = 10
    reports_dir: str = field(default_factory=lambda: os.path.join(os.getcwd(), "reports"))
