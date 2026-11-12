"""Estruturas de dados de mercado e utilidades de tempo/sessão."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}
TF_YAHOO = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "1h", "D1": "1d"}
TF_OANDA = {"M1": "M1", "M5": "M5", "M15": "M15", "H1": "H1", "H4": "H4", "D1": "D"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    time: datetime              # horário da cotação no provedor (UTC)
    source: str
    spread_source: str          # "provider" (bid/ask reais) | "estimated"
    received_at: datetime = field(default_factory=utcnow)
    prev_close: float | None = None
    latency_ms: float | None = None
    check: dict | None = None   # divergência vs. outras fontes (pips), p.ex. {"truefx_pips": 0.2}

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def age_seconds(self, now: datetime | None = None) -> float:
        now = now or utcnow()
        return max(0.0, (now - self.time).total_seconds())

    @property
    def change_pct(self) -> float | None:
        if not self.prev_close:
            return None
        return (self.mid / self.prev_close - 1.0) * 100.0

    def to_dict(self, pip: float | None = None) -> dict:
        d = asdict(self)
        d["time"] = self.time.isoformat()
        d["received_at"] = self.received_at.isoformat()
        d["mid"] = self.mid
        d["spread"] = self.spread
        d["age_s"] = round(self.age_seconds(), 1)
        d["change_pct"] = self.change_pct
        if pip:
            d["spread_pips"] = round(self.spread / pip, 2)
        return d


def session_of(ts: datetime | pd.Timestamp) -> str:
    """Classificação aproximada de sessão (UTC). Não corrige horário de verão local."""
    h = ts.hour
    wd = ts.weekday()
    if wd == 4 and h >= 19:
        return "late"
    if 21 <= h < 23:
        return "rollover"
    if h >= 23 or h < 7:
        return "asia"
    if 7 <= h < 12:
        return "london"
    if 12 <= h < 16:
        return "overlap"
    return "newyork"


def market_open(ts: datetime, kind: str = "fx") -> bool:
    """Janela semanal do mercado de balcão: domingo ~21h UTC a sexta ~21h UTC."""
    wd, h = ts.weekday(), ts.hour
    if wd == 5:
        return False
    if wd == 4 and h >= 21:
        return False
    if wd == 6 and h < 21:
        return False
    if kind == "metal" and h == 21:  # pausa diária aproximada dos metais
        return False
    return True


def clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["o", "h", "l", "c"])
    df = df[(df[["o", "h", "l", "c"]] > 0).all(axis=1)]
    hi = df[["o", "h", "c"]].max(axis=1)
    lo = df[["o", "l", "c"]].min(axis=1)
    df = df.assign(h=hi, l=lo)
    if "v" not in df:
        df["v"] = 0.0
    df["v"] = df["v"].fillna(0.0)
    return df


def drop_weekend(df: pd.DataFrame) -> pd.DataFrame:
    """Remove barras fora da janela de negociação de balcão (para proxies 24/7)."""
    if df.empty:
        return df
    idx = df.index
    wd = idx.weekday
    h = idx.hour
    closed = (wd == 5) | ((wd == 4) & (h >= 21)) | ((wd == 6) & (h < 22))
    return df[~closed]


def repair_level_shifts(df: pd.DataFrame, tf_seconds: int, rel_threshold: float = 0.004) -> tuple[pd.DataFrame, int]:
    """Repara saltos artificiais de séries de futuros contínuos (rolagem/intercalação de contratos).

    Em barras contíguas (sem pausa de mercado), a abertura deveria ser ~igual ao fechamento
    anterior. Saltos maiores que `rel_threshold` são tratados como mudança de contrato e
    removidos via ajuste retroativo (back-adjustment) aditivo. Retorna (df_ajustado, n_ajustes).
    """
    if len(df) < 3:
        return df, 0
    df = df.copy()
    o = df["o"].to_numpy(dtype=float)
    c = df["c"].to_numpy(dtype=float)
    t = df.index.asi8 // 1_000_000_000
    dt = np.diff(t, prepend=t[0])
    gap = np.zeros(len(df))
    gap[1:] = o[1:] - c[:-1]
    contiguous = dt <= tf_seconds * 1.5
    rel = np.abs(gap) / np.maximum(c, 1e-12)
    # um salto em barra contígua > limiar é considerado artificial
    shift_idx = np.where(contiguous & (rel > rel_threshold))[0]
    if len(shift_idx) == 0:
        return df, 0
    offset = np.zeros(len(df))
    # ajuste retroativo: preços anteriores ao salto recebem +gap
    for i in shift_idx:
        offset[:i] += gap[i]
    for col in ("o", "h", "l", "c"):
        df[col] = df[col].to_numpy(dtype=float) + offset
    # barras com faixa absurda (mistura de contratos dentro da barra) são aparadas
    rng = (df["h"] - df["l"]).to_numpy()
    med = np.nanmedian(rng[rng > 0]) if np.any(rng > 0) else 0
    if med > 0:
        cap = 8 * med
        body_hi = df[["o", "c"]].max(axis=1).to_numpy()
        body_lo = df[["o", "c"]].min(axis=1).to_numpy()
        df["h"] = np.minimum(df["h"].to_numpy(), body_hi + cap)
        df["l"] = np.maximum(df["l"].to_numpy(), body_lo - cap)
    df = df[(df[["o", "h", "l", "c"]] > 0).all(axis=1)]
    return df, int(len(shift_idx))


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.resample(rule, label="left", closed="left").agg(
        {"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}
    )
    return out.dropna(subset=["o", "h", "l", "c"])


def completed_bars(df: pd.DataFrame, tf: str, now: datetime | None = None) -> pd.DataFrame:
    """Retorna apenas barras fechadas (remove a barra em formação)."""
    if df.empty:
        return df
    now = now or utcnow()
    end = df.index + pd.Timedelta(seconds=TF_SECONDS[tf])
    return df[end <= pd.Timestamp(now)]


def bar_age_minutes(df: pd.DataFrame, now: datetime | None = None) -> float:
    if df.empty:
        return float("inf")
    now = now or utcnow()
    return (pd.Timestamp(now) - df.index[-1]).total_seconds() / 60.0


def to_iso(ts) -> str:
    if isinstance(ts, (pd.Timestamp, datetime)):
        return ts.isoformat()
    return str(ts)


__all__ = [
    "Quote", "TF_SECONDS", "TF_YAHOO", "TF_OANDA", "utcnow", "session_of", "market_open",
    "clean_ohlc", "drop_weekend", "repair_level_shifts", "resample", "completed_bars",
    "bar_age_minutes", "to_iso", "timedelta",
]
