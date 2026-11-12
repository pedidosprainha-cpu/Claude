"""Configuração central (arquivo JSON + variáveis de ambiente).

Ordem de precedência: valores padrão < config/settings.json < variáveis de ambiente FXI_*.
Segredos (tokens de API) só são lidos de variáveis de ambiente, nunca do JSON versionado.
"""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("FXI_CONFIG_DIR", ROOT / "config"))
DATA_DIR = Path(os.environ.get("FXI_DATA_DIR", ROOT / "var"))
CACHE_DIR = DATA_DIR / "cache"
MODEL_DIR = DATA_DIR / "models"
LOG_DIR = DATA_DIR / "logs"
DB_PATH = Path(os.environ.get("FXI_DB_PATH", DATA_DIR / "fxintel.db"))

DEFAULTS: dict[str, Any] = {
    "universe": [
        "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD",
        "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "CADJPY", "EURCHF", "EURAUD",
    ],
    "timeframes": {"trend": "D1", "context": "H4", "setup": "H1", "trigger": "M15", "micro": "M5"},
    "account": {"currency": "USD", "equity": 10_000.0, "leverage": 30},
    "risk": {
        "risk_per_trade_pct": 0.5,
        "max_daily_loss_pct": 2.0,
        "max_weekly_loss_pct": 4.0,
        "max_session_loss_pct": 1.5,
        "max_open_positions": 3,
        "max_risk_per_currency_pct": 1.0,
        "max_correlated_positions": 2,
        "correlation_threshold": 0.7,
        "min_lot": 0.01,
        "lot_step": 0.01,
        "max_lot": 50.0,
    },
    "gates": {
        "max_quote_age_s": 180,
        "max_bar_age_min": 90,
        "max_spread_to_atr": 0.12,
        "max_cost_r": 0.15,
        "min_rr_net": 1.2,
        "min_ev_r": 0.05,
        "min_model_bss": 0.0,
        "min_model_auc": 0.52,
        "require_model": True,
        "event_blackout_before_min": 60,
        "event_blackout_after_min": 30,
        "max_entry_drift_atr": 0.35,
        "max_vol_zscore": 5.0,
        "block_on_anomaly": True,
        "signal_validity_min": 240,
    },
    "slippage": {"base_pips": 0.2, "atr_fraction": 0.02},
    "session_spread_multipliers": {
        "rollover": 3.0, "asia": 1.3, "london": 1.0, "overlap": 1.0, "newyork": 1.1, "late": 1.6,
    },
    "spread_overrides_pips": {},
    "model": {
        "horizon_bars": 36,
        "min_train_samples": 400,
        "retrain_hours": 24,
        "calibration": "sigmoid",
        "kind": "logistic",
    },
    "scoring_weights": {
        "ev": 0.45, "technical": 0.20, "fundamental": 0.15, "regime": 0.10, "cost": 0.10,
    },
    "providers": {
        # Todas as fontes padrão são públicas e dispensam chave de API.
        "quotes_order": ["swissquote", "yahoo", "goldapi"],
        "swissquote_profile": "premium",
        "yahoo_hosts": ["query1.finance.yahoo.com", "query2.finance.yahoo.com"],
        "timeout_s": 15,
        "max_workers": 8,
    },
    "alerts": {
        "vol_shock_ratio": 2.5,
        "event_lead_min": 30,
        "check_interval_s": 60,
    },
    "server": {"quote_refresh_s": 10, "auto_analyze_min": 0},
}

_lock = threading.Lock()
_settings: dict[str, Any] | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def settings_path() -> Path:
    return CONFIG_DIR / "settings.json"


def load_settings(reload: bool = False) -> dict[str, Any]:
    global _settings
    with _lock:
        if _settings is not None and not reload:
            return _settings
        s = copy.deepcopy(DEFAULTS)
        p = settings_path()
        if p.exists():
            try:
                s = _deep_merge(s, json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                raise ValueError(f"settings.json inválido: {exc}") from exc
        if os.environ.get("FXI_EQUITY"):
            s["account"]["equity"] = float(os.environ["FXI_EQUITY"])
        if os.environ.get("FXI_UNIVERSE"):
            s["universe"] = [x.strip().upper() for x in os.environ["FXI_UNIVERSE"].split(",") if x.strip()]
        _settings = s
        return s


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """Aplica um patch parcial e persiste em config/settings.json (sem segredos)."""
    global _settings
    current = load_settings()
    merged = _deep_merge(current, patch)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Persiste apenas as diferenças em relação ao padrão, para manter o arquivo legível.
    settings_path().write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    with _lock:
        _settings = merged
    return merged


def secret(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v else None


def ensure_dirs() -> None:
    for d in (DATA_DIR, CACHE_DIR, MODEL_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
