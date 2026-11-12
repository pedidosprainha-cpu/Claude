"""Exporta um fixture "golden" para verificar que o motor Kotlin (app Android) reproduz o Python.

Entradas: barras H1 reais (cache local) de alguns instrumentos, séries macro e fechamentos do
cesto de moedas. Saídas esperadas: colunas do quadro MTF, candidatos, features e probabilidades.

Uso: python scripts/export_golden.py  -> android/app/src/test/resources/golden.json
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fxintel import instruments as I  # noqa: E402
from fxintel.data import DataHub  # noqa: E402
from fxintel.data.hub import derive  # noqa: E402
from fxintel.fundamental.macro import currency_strength, macro_features, strength_diff  # noqa: E402
from fxintel.quant.features import build_features  # noqa: E402
from fxintel.signals import candidates as C  # noqa: E402
from fxintel.technical.mtf import build_frame  # noqa: E402
from fxintel.training import EXPORT_PATH  # noqa: E402

N = 3000
SYMBOLS = ["EURUSD", "USDJPY", "XAUUSD", "XAGUSD"]
COLS = ["atr", "rsi", "adx", "pdi", "macd_hist", "ema50", "ema200", "er", "bb_width", "stoch_k", "trend", "event",
        "since_event", "last_sh", "last_sl", "near_hi", "near_lo", "near_hi_eq", "sweep_hi", "sweep_lo_eq",
        "swing_bias", "fvg_bull_top", "fvg_bear_bot", "ob_bull_top", "ob_bear_bot", "in_fvg_bull", "in_ob_bear",
        "new_fvg", "displacement", "bull_engulf", "bear_pin", "inside", "compression", "close_pos", "fail_up",
        "don_hi", "rsi_div", "ema_stack", "above_ema200", "atr_pct", "pdh", "pdl", "pwh", "asia_h", "day_l",
        "day_open", "h4_trend", "h4_adx", "h4_rsi", "h4_last_sh", "h4_near_lo", "h4_in_fvg_bull", "d1_trend",
        "d1_ema_stack", "d1_above_ema200", "d1_adx", "d1_rsi", "d1_atr", "d1_ema50"]


def enc(a, nd=None):
    out = []
    for v in a:
        if v is None or (isinstance(v, float) and not np.isfinite(v)) or (hasattr(v, "dtype") and not np.isfinite(v)):
            out.append(None)
        else:
            out.append(round(float(v), nd) if nd else float(v))
    return out


def bars_json(df):
    return {"t": [int(x.timestamp()) for x in df.index], "o": enc(df["o"], 6), "h": enc(df["h"], 6),
            "l": enc(df["l"], 6), "c": enc(df["c"], 6)}


def main():
    hub = DataHub()
    fx_all = [s for s in I.DEFAULT_UNIVERSE if I.get(s).kind == "fx"]
    # entradas arredondadas a 6 casas (o motor Python é executado sobre os mesmos valores arredondados)
    hist = {s: hub.bars(s, "H1").iloc[-N:].round(6) for s in set(SYMBOLS) | set(fx_all)}
    macro = {}
    for name in ("DXY", "US10Y", "US5Y", "US3M", "VIX", "SPX_FUT", "WTI"):
        m = hub.macro_bars(name, "H1")
        macro[name] = m[m.index >= hist["EURUSD"].index[0] - np.timedelta64(30, "D")].round(6)
    strength = currency_strength({s: hist[s]["c"] for s in fx_all})
    model = json.loads(EXPORT_PATH.read_text())
    out = {"symbols": {}, "macro": {k: {"t": [int(x.timestamp()) for x in v.index], "c": enc(v["c"], 6)}
                                    for k, v in macro.items()},
           "basket": {s: {"t": [int(x.timestamp()) for x in hist[s].index], "c": enc(hist[s]["c"], 6)} for s in fx_all},
           "model": model}
    from fxintel.quant.model import ProbabilityModel
    from fxintel.training import MODEL_PATH
    pm = ProbabilityModel.load(MODEL_PATH)
    for s in SYMBOLS:
        h1 = hist[s]
        F, _ = build_frame(h1, derive(h1, "H4"), derive(h1, "D1"))
        cand = C.generate(F)
        mf = macro_features(macro, F.index)
        sd = strength_diff(strength, I.get(s), F.index)
        X = build_features(I.get(s), F, cand, mf, sd) if not cand.empty else None
        p = pm.predict(X.add_prefix("x_")) if X is not None else []
        tail = F.iloc[-400:]
        out["symbols"][s] = {
            "bars": bars_json(h1),
            "frame_tail": {"t": [int(x.timestamp()) for x in tail.index], **{c: enc(tail[c]) for c in COLS}},
            "candidates": [{"t": int(t.timestamp()), "dir": int(r["dir"]), "setup": r["setup"], "sl": float(r["sl"]),
                            "tp1": float(r["tp1"]), "tp2": float(r["tp2"]), "rr1": float(r["rr1"]),
                            "room_r": float(r["room_r"])} for t, r in cand.iterrows()],
            "features": {str(int(t.timestamp())): enc(X.loc[t].to_numpy()) for t in X.index} if X is not None else {},
            "feature_names": list(X.columns) if X is not None else [],
            "p": [float(v) for v in p],
            "macro_tail": {c: enc(mf[c].iloc[-400:]) for c in mf.columns},
            "strength_tail": {c: enc(sd[c].iloc[-400:]) for c in sd.columns},
        }
        print(s, len(h1), "candidatos", len(cand))
    dst = ROOT / "android" / "app" / "src" / "test" / "resources" / "golden.json"
    dst.write_text(json.dumps(out, separators=(",", ":")))
    print("ok", dst, round(dst.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
