"""Configuration: defaults, risk profiles, hard safety caps, load/save.

The user's config.json only stores overrides. Defaults live here so upgrades
pick up new settings automatically. HARD_CAPS are enforced in code: a config
file (or an over-eager operator) cannot push risk beyond them.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

FX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]
FX_CROSSES = [
    "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD", "CADJPY", "CADCHF", "CHFJPY",
]
METALS = ["XAUUSD", "XAGUSD"]
OPTIONAL_METALS = ["XPTUSD", "XPDUSD"]   # traded only if the broker offers them

# Broker naming differs (GOLD, XAUUSDm, EURUSD.pro ...). Aliases help the resolver.
ALIASES = {"XAUUSD": ["GOLD"], "XAGUSD": ["SILVER"], "XPTUSD": ["PLATINUM"], "XPDUSD": ["PALLADIUM"]}

DEFAULTS = {
    "version": 1,
    "magic": 26111501,                 # tags the bot's own orders; it never touches others
    "symbols": FX_MAJORS + FX_CROSSES + METALS + OPTIONAL_METALS,
    "symbol_map": {},                  # manual override: {"XAUUSD": "GOLD.a"}
    "timeframe": "H1",                 # entry timeframe; trend=H4 and bias=D1 are derived from it
    "history_bars": 4000,
    "poll_seconds": 20,
    "terminal_path": None,             # only needed with several MT5 terminals installed
    "strategy": {
        "trend_tf": "H4", "bias_tf": "D1",
        "ema_fast": 20, "ema_mid": 50, "ema_slow": 200,
        "adx_min": 18.0,
        "enable_reversion": True, "enable_pullback": False, "enable_breakout": False,
        "reversion_classes": ["cross"],
        "mr_lookback": 20, "mr_z": 1.0, "mr_sl_atr": 3.0, "mr_tp_r": 0.0, "mr_cooldown_bars": 24,
        "cooldown_bars": 6,
        "pullback_lookback": 8, "rsi_pullback": 50.0, "max_ext_atr": 1.0,
        "breakout_lookback": 24, "box_bars": 12, "box_atr_max": 4.5,
        "sl_buffer_atr": 0.2, "sl_atr_min": 1.0, "sl_atr_max": 2.5, "breakout_sl_atr": 1.5,
        "tp_r": 2.0,
        "strength_fast": 24, "strength_slow": 120,
        "min_score": 70.0,
    },
    "management": {
        # trail_start_r = 0 disables trailing; breakeven_at_r = 0 disables break-even
        "trend": {"breakeven_at_r": 1.0, "breakeven_lock_r": 0.1, "trail_start_r": 0.0, "trail_dist_r": 1.0,
                  "max_hold_bars": 72, "flat_before_weekend": True},
        "reversion": {"breakeven_at_r": 0.0, "breakeven_lock_r": 0.0, "trail_start_r": 0.0, "trail_dist_r": 1.0,
                      "max_hold_bars": 240, "flat_before_weekend": False},
    },
    "risk": {
        "risk_per_trade_pct": 0.5,
        "max_open_positions": 4,
        "max_total_risk_pct": 2.0,
        "max_per_currency": 2,
        "daily_loss_limit_pct": 2.0,
        "max_drawdown_pct": 8.0,
        "max_consecutive_losses": 4,
        "cooldown_hours": 12,
        "max_trades_per_day": 8,
        "max_spread_frac_of_sl": 0.12,
        "min_lot_risk_tolerance": 1.5,
        "min_margin_level_pct": 300.0,
    },
    "session": {
        "rollover_block_before_min": 30,
        "rollover_block_after_min": 75,
        "friday_last_entry_hour_ny": 12.0,
        "friday_flat_hour_ny": 16.5,
    },
    "news": {
        "enabled": True,
        "url": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "impacts": ["High"],
        "block_before_min": 30,
        "block_after_min": 30,
        "refresh_hours": 4,
        "fail_mode": "allow",          # "allow" or "block" when the calendar is unreachable
    },
    "execution": {"deviation_points": 20, "max_signal_age_sec": 420, "retries": 3},
    "live": {"enabled": False, "login": None, "authorized_at": None},
}

PROFILES = {
    "conservative": {},
    "moderate": {"risk": {"risk_per_trade_pct": 1.0, "max_open_positions": 5, "max_total_risk_pct": 4.0,
                          "daily_loss_limit_pct": 3.0, "max_drawdown_pct": 12.0}},
}

# Absolute ceilings. Values above these are clamped and reported by `doctor`.
HARD_CAPS = {
    "risk_per_trade_pct": 2.0,
    "max_total_risk_pct": 6.0,
    "daily_loss_limit_pct": 5.0,
    "max_drawdown_pct": 20.0,
    "max_open_positions": 10,
    "max_trades_per_day": 20,
    "max_spread_frac_of_sl": 0.25,
    "min_lot_risk_tolerance": 2.0,
}


def home_dir() -> Path:
    """Runtime data lives outside the skill folder so skill upgrades never wipe it."""
    p = Path(os.environ.get("FXBOT_HOME") or (Path.home() / ".mt5-autotrader"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def apply_caps(cfg: dict) -> list[str]:
    """Clamp risk settings to HARD_CAPS in place. Returns human-readable notes."""
    notes = []
    risk = cfg["risk"]
    for key, cap in HARD_CAPS.items():
        val = risk.get(key)
        if isinstance(val, (int, float)) and val > cap:
            notes.append(f"risk.{key}={val} exceeds the hard cap {cap}; using {cap}")
            risk[key] = cap
    for key in ("risk_per_trade_pct", "max_total_risk_pct", "daily_loss_limit_pct", "max_drawdown_pct"):
        if not isinstance(risk.get(key), (int, float)) or risk[key] <= 0:
            notes.append(f"risk.{key} must be a positive number; restoring default")
            risk[key] = DEFAULTS["risk"][key]
    if cfg["strategy"]["tp_r"] < 1.0:
        notes.append("strategy.tp_r below 1.0 makes the reward smaller than the risk; using 1.0")
        cfg["strategy"]["tp_r"] = 1.0
    return notes


def config_path(home: Path | None = None) -> Path:
    return (home or home_dir()) / "config.json"


def load_overrides(home: Path | None = None) -> dict:
    p = config_path(home)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(home: Path | None = None, overrides: dict | None = None) -> dict:
    """Defaults <- profile <- config.json overrides, then hard caps."""
    over = overrides if overrides is not None else load_overrides(home)
    profile = over.get("profile", "conservative")
    cfg = deep_merge(DEFAULTS, PROFILES.get(profile, {}))
    cfg = deep_merge(cfg, over)
    cfg["profile"] = profile
    cfg["_cap_notes"] = apply_caps(cfg)
    return cfg


def save_overrides(over: dict, home: Path | None = None) -> Path:
    p = config_path(home)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(over, f, indent=2, sort_keys=True)
    os.replace(tmp, p)
    return p


def set_override(path: str, value, home: Path | None = None) -> dict:
    """Set one dotted key (e.g. 'risk.risk_per_trade_pct') in config.json."""
    over = load_overrides(home)
    node = over
    parts = path.split(".")
    for k in parts[:-1]:
        node = node.setdefault(k, {})
    node[parts[-1]] = value
    save_overrides(over, home)
    return over


def currencies_of(symbol: str) -> tuple[str, str]:
    """Canonical 6-letter symbol -> (base, quote). Metals count as their own currency."""
    s = symbol.upper()
    return s[:3], s[3:6]


def asset_class(symbol: str) -> str:
    s = symbol.upper()
    if s[:3] in ("XAU", "XAG", "XPT", "XPD"):
        return "metal"
    return "major" if s in FX_MAJORS else "cross"
