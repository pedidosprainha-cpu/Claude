"""DataHub: ponto único de acesso a dados com cache, failover e controle de qualidade.

Responsabilidades
- Barras H1 (histórico completo em cache em disco + atualização incremental), M15, M5.
- H4 e D1 derivados de H1 (alinhados ao fechamento de Nova York, 22:00 UTC) — garante
  consistência entre backtest e análise ao vivo e evita ambiguidades de timestamps diários.
- Cotações com failover: OANDA (bid/ask reais, se configurado) -> Yahoo / gold-api.
- Spread estimado por sessão quando o provedor não fornece bid/ask.
- Ajuste de nível das séries proxy de metais para o spot atual.
"""
from __future__ import annotations

import logging
import pickle
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from .. import instruments as I
from ..config import CACHE_DIR, ensure_dirs, load_settings
from .base import ProviderError
from .calendar import CalendarProvider
from .goldapi import GoldApiProvider
from .models import (TF_SECONDS, Quote, clean_ohlc, drop_weekend, repair_level_shifts, resample,
                     session_of, utcnow)
from .oanda import OandaProvider
from .yahoo import YahooProvider

log = logging.getLogger("fxintel.data.hub")

MEM_TTL = {"M5": 45, "M15": 90, "H1": 240}
LIVE_RANGE = {"M5": "5d", "M15": "30d", "H1": "5d"}


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s)


class DataHub:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or load_settings()
        p = self.settings["providers"]
        self.yahoo = YahooProvider(hosts=p.get("yahoo_hosts"), timeout=p.get("timeout_s", 15))
        self.goldapi = GoldApiProvider(timeout=p.get("timeout_s", 15))
        self.oanda = OandaProvider(timeout=p.get("timeout_s", 15))
        self.calendar = CalendarProvider(timeout=p.get("timeout_s", 15))
        self.max_workers = p.get("max_workers", 8)
        self._mem: dict[tuple, tuple[float, pd.DataFrame]] = {}
        self._lock = threading.RLock()
        self._last_quotes: dict[str, Quote] = {}
        self.data_notes: dict[str, list[str]] = {}
        ensure_dirs()

    # ------------------------------------------------------------------ spreads
    def estimate_spread(self, inst: I.Instrument, ts: datetime) -> float:
        overrides = self.settings.get("spread_overrides_pips", {})
        pips = float(overrides.get(inst.symbol, inst.typical_spread_pips))
        mult = self.settings["session_spread_multipliers"].get(session_of(ts), 1.0)
        return pips * inst.pip * mult

    # ------------------------------------------------------------------ barras
    def _proxy_process(self, inst: I.Instrument, df: pd.DataFrame, tf: str) -> pd.DataFrame:
        if inst.symbol == "XAUUSD":
            df = drop_weekend(df)
        elif inst.symbol == "XAGUSD":
            df, n = repair_level_shifts(df, TF_SECONDS[tf])
            if n:
                self.data_notes.setdefault(inst.symbol, []).append(
                    f"{tf}: {n} saltos de rolagem/intercalação de contratos reparados")
        return df

    def _disk_path(self, ysym: str, tf: str):
        return CACHE_DIR / f"{_safe(ysym)}_{tf}.pkl"

    def _load_disk(self, ysym: str, tf: str) -> pd.DataFrame | None:
        p = self._disk_path(ysym, tf)
        if not p.exists():
            return None
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:  # cache corrompido: ignora
            return None

    def _save_disk(self, ysym: str, tf: str, df: pd.DataFrame) -> None:
        p = self._disk_path(ysym, tf)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(df, f)
        tmp.replace(p)

    def raw_bars(self, ysym: str, tf: str, full: bool = False) -> pd.DataFrame:
        """Barras brutas do Yahoo com cache em disco + atualização incremental (H1/M15/M5)."""
        key = (ysym, tf)
        now = time.time()
        with self._lock:
            hit = self._mem.get(key)
            if hit and now - hit[0] < MEM_TTL.get(tf, 120) and not full:
                return hit[1]
        cached = self._load_disk(ysym, tf)
        coverage = {"M5": 4, "M15": 28, "H1": 4}[tf]
        if cached is not None and len(cached) and (
                pd.Timestamp.now(tz="UTC") - cached.index[-1]) > pd.Timedelta(days=coverage):
            cached = None  # cache antigo demais para atualização incremental
        if cached is not None and len(cached) and not full:
            fresh, _ = self.yahoo.bars(ysym, tf, LIVE_RANGE[tf])
            df = pd.concat([cached[~cached.index.isin(fresh.index)], fresh]).sort_index()
            # mantém janela máxima do provedor para não crescer indefinidamente
            limit = {"H1": 1100, "M15": 60, "M5": 60}[tf]
            df = df[df.index >= df.index[-1] - pd.Timedelta(days=limit)]
        else:
            df, _ = self.yahoo.bars(ysym, tf, None)
        df = clean_ohlc(df)
        self._save_disk(ysym, tf, df)
        with self._lock:
            self._mem[key] = (now, df)
        return df

    def bars(self, symbol: str, tf: str, full: bool = False) -> pd.DataFrame:
        """Barras processadas do instrumento (sem ajuste ao spot) para M5, M15, H1, H4, D1."""
        inst = I.get(symbol)
        if tf in ("H4", "D1"):
            h1 = self.bars(symbol, "H1", full=full)
            return derive(h1, tf)
        df = self.raw_bars(inst.yahoo, tf, full=full)
        return self._proxy_process(inst, df, tf)

    def macro_bars(self, name: str, tf: str = "H1") -> pd.DataFrame:
        ysym = I.MACRO_SYMBOLS[name]
        df = self.raw_bars(ysym, "H1")
        if name in ("WTI", "SPX_FUT", "GOLD_FUT"):
            df, _ = repair_level_shifts(df, 3600)
        return derive(df, tf) if tf != "H1" else df

    def multi(self, symbols: list[str], tfs: list[str]) -> dict[str, dict[str, pd.DataFrame]]:
        """Busca paralela de vários instrumentos/timeframes. Falhas ficam registradas em data_notes."""
        out: dict[str, dict[str, pd.DataFrame]] = {s: {} for s in symbols}
        base_tfs = sorted({("H1" if tf in ("H4", "D1") else tf) for tf in tfs})
        jobs = [(s, tf) for s in symbols for tf in base_tfs]
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = {ex.submit(self.bars, s, tf): (s, tf) for s, tf in jobs}
            for fut, (s, tf) in futs.items():
                try:
                    out[s][tf] = fut.result()
                except Exception as exc:  # noqa: BLE001 - qualquer falha de provedor
                    self.data_notes.setdefault(s, []).append(f"{tf}: falha de dados: {exc}")
        for s in symbols:
            if "H1" in out[s]:
                for tf in ("H4", "D1"):
                    if tf in tfs:
                        out[s][tf] = derive(out[s]["H1"], tf)
        return out

    # ------------------------------------------------------------------ cotações
    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        now = utcnow()
        out: dict[str, Quote] = {}
        order = self.settings["providers"].get("quotes_order", ["oanda", "yahoo", "goldapi"])

        if "oanda" in order and self.oanda.configured:
            try:
                t0 = time.perf_counter()
                insts = [I.get(s) for s in symbols]
                px = self.oanda.pricing([i.oanda for i in insts])
                lat = (time.perf_counter() - t0) * 1000
                for i in insts:
                    p = px.get(i.oanda)
                    if p:
                        out[i.symbol] = Quote(i.symbol, p["bid"], p["ask"], p["time"], "oanda",
                                              "provider", latency_ms=lat)
            except ProviderError as exc:
                log.warning("OANDA indisponível, usando fallback: %s", exc)

        missing = [s for s in symbols if s not in out]
        fx = [s for s in missing if I.get(s).kind == "fx"]
        metals = [s for s in missing if I.get(s).kind == "metal"]

        if fx:
            try:
                t0 = time.perf_counter()
                lp = self.yahoo.last_prices([I.get(s).yahoo for s in fx])
                lat = (time.perf_counter() - t0) * 1000
                for s in fx:
                    inst = I.get(s)
                    p = lp.get(inst.yahoo)
                    if not p:
                        continue
                    sp = self.estimate_spread(inst, now)
                    out[s] = Quote(s, p["price"] - sp / 2, p["price"] + sp / 2, p["time"], "yahoo",
                                   "estimated", prev_close=p.get("prev_close"), latency_ms=lat)
            except ProviderError as exc:
                log.warning("Yahoo cotações indisponível: %s", exc)

        for s in metals:
            inst = I.get(s)
            try:
                t0 = time.perf_counter()
                p = self.goldapi.spot(s)
                lat = (time.perf_counter() - t0) * 1000
                sp = self.estimate_spread(inst, now)
                prev = self._metal_prev_close(s, p["price"])
                out[s] = Quote(s, p["price"] - sp / 2, p["price"] + sp / 2, p["time"], "goldapi",
                               "estimated", prev_close=prev, latency_ms=lat)
            except ProviderError as exc:
                log.warning("gold-api indisponível para %s: %s", s, exc)
                try:  # fallback: último preço do proxy (sem ajuste de base)
                    lp = self.yahoo.last_prices([inst.yahoo]).get(inst.yahoo)
                    if lp:
                        sp = self.estimate_spread(inst, now) * 1.5
                        out[s] = Quote(s, lp["price"] - sp / 2, lp["price"] + sp / 2, lp["time"],
                                       "yahoo-proxy", "estimated", prev_close=lp.get("prev_close"))
                except ProviderError:
                    pass
        with self._lock:
            self._last_quotes.update(out)
        return out

    def _metal_prev_close(self, symbol: str, spot: float) -> float | None:
        """Fechamento anterior aproximado do metal (D1 do proxy ajustado ao spot)."""
        try:
            h1 = self.bars(symbol, "H1")
            if len(h1) < 30:
                return None
            d1 = derive(h1, "D1")
            if len(d1) < 2:
                return None
            adj = spot_adjust(I.get(symbol), d1, spot)[0]
            return float(adj["c"].iloc[-2])
        except Exception:  # noqa: BLE001
            return None

    @property
    def last_quotes(self) -> dict[str, Quote]:
        with self._lock:
            return dict(self._last_quotes)

    def health(self) -> dict:
        return {
            "providers": [p.health.to_dict() for p in (self.oanda, self.yahoo, self.goldapi,
                                                       self.calendar)],
            "oanda_configured": self.oanda.configured,
            "calendar_fetched_at": self.calendar.fetched_at.isoformat() if self.calendar.fetched_at else None,
        }


def derive(h1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """H4/D1 a partir de H1, alinhados ao fechamento de Nova York (22:00 UTC)."""
    if h1.empty:
        return h1
    if tf == "H4":
        return resample_offset(h1, "4h", "2h")
    if tf == "D1":
        d = resample_offset(h1, "24h", "22h")
        d.index = d.index + pd.Timedelta(hours=2)  # rótulo = data do pregão (00:00 UTC)
        return d[d.index.weekday < 5]  # barras iniciadas sexta 22h (sábado) não são pregão
    raise ValueError(tf)


def resample_offset(df: pd.DataFrame, rule: str, offset: str) -> pd.DataFrame:
    out = df.resample(rule, label="left", closed="left", offset=offset).agg(
        {"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"})
    return out.dropna(subset=["o", "h", "l", "c"])


def spot_adjust(inst: I.Instrument, df: pd.DataFrame, spot: float) -> tuple[pd.DataFrame, dict]:
    """Ajusta o nível da série proxy de um metal para o spot atual.

    XAU (PAXG): ajuste multiplicativo (token ~ proporcional ao spot).
    XAG (futuro): ajuste aditivo de base (futuro = spot + carrego).
    """
    if inst.kind != "metal" or df.empty or not spot:
        return df, {"method": "none"}
    last = float(df["c"].iloc[-1])
    out = df.copy()
    if inst.symbol == "XAUUSD":
        ratio = spot / last
        for c in ("o", "h", "l", "c"):
            out[c] = out[c] * ratio
        info = {"method": "multiplicativo", "ratio": ratio, "basis_pct": (last / spot - 1) * 100}
    else:
        basis = last - spot
        for c in ("o", "h", "l", "c"):
            out[c] = out[c] - basis
        info = {"method": "aditivo", "basis": basis, "basis_pct": (basis / spot) * 100}
    return out, info


__all__ = ["DataHub", "derive", "spot_adjust", "resample", "resample_offset"]
