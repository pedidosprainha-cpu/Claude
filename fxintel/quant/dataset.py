"""Construção do conjunto de dados de candidatos (features + rótulos) para treino e backtest."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from .. import instruments as I
from ..data.hub import DataHub, derive
from ..fundamental.macro import currency_strength, macro_features, strength_diff
from ..signals import candidates as C
from ..technical.mtf import build_frame
from .features import build_features
from .labeling import label_candidates

log = logging.getLogger("fxintel.quant.dataset")


def load_history(hub: DataHub, symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {s: ex.submit(hub.bars, s, "H1") for s in symbols}
        for s, fu in futs.items():
            try:
                out[s] = fu.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("histórico indisponível para %s: %s", s, exc)
    return out


def load_macro(hub: DataHub) -> dict[str, pd.DataFrame]:
    out = {}
    for name in ("DXY", "US10Y", "US5Y", "US3M", "VIX", "SPX_FUT", "WTI"):
        try:
            out[name] = hub.macro_bars(name, "H1")
        except Exception as exc:  # noqa: BLE001
            log.warning("série macro %s indisponível: %s", name, exc)
    return out


def instrument_dataset(sym: str, h1: pd.DataFrame, macro: dict, strength: dict, settings: dict,
                       label: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Retorna (candidatos com features e rótulos, quadro F, features macro/força)."""
    inst = I.get(sym)
    F, _ = build_frame(h1, derive(h1, "H4"), derive(h1, "D1"))
    cand = C.generate(F)
    mf = macro_features(macro, F.index) if macro else pd.DataFrame(index=F.index)
    sd = strength_diff(strength, inst, F.index) if strength else pd.DataFrame(index=F.index)
    if cand.empty:
        return cand, F, pd.concat([mf, sd], axis=1)
    X = build_features(inst, F, cand, mf, sd)
    out = pd.concat([cand, X.add_prefix("x_")], axis=1)
    if label:
        sl = settings["slippage"]
        ov = settings.get("spread_overrides_pips", {}).get(sym)
        hz = settings["model"]["horizon_bars"]
        out = label_candidates(inst, h1, out, hz, settings["session_spread_multipliers"],
                               sl["base_pips"], sl["atr_fraction"], ov)
        # análise de sensibilidade a custos: mesmo trade sem spread nem slippage
        zero = {k: 0.0 for k in settings["session_spread_multipliers"]}
        gross = label_candidates(inst, h1, cand.assign(**{c: out[c] for c in ("atr",)}), hz, zero, 0.0, 0.0, 0.0)
        out["r_gross"] = gross["r"].reindex(out.index)
    out["symbol"] = sym
    out["decision_time"] = out.index + pd.Timedelta(hours=1)
    return out, F, pd.concat([mf, sd], axis=1)


def build_dataset(hub: DataHub, symbols: list[str], settings: dict) -> pd.DataFrame:
    hist = load_history(hub, symbols)
    macro = load_macro(hub)
    strength = currency_strength({s: df["c"] for s, df in hist.items()})
    parts = []
    for s, h1 in hist.items():
        if len(h1) < 1500:
            log.warning("%s: histórico curto (%d barras), ignorado", s, len(h1))
            continue
        ds, _, _ = instrument_dataset(s, h1, macro, strength, settings)
        if not ds.empty:
            parts.append(ds)
        log.info("%s: %d candidatos", s, len(ds))
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts).sort_values("decision_time")
    df = df[np.isfinite(df["r"])]
    return df


def feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("x_")]
