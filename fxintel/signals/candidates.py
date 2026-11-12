"""Geração de oportunidades candidatas (setups) sobre o quadro multi-timeframe H1.

Quatro famílias de setup, todas para execução a mercado no fechamento do candle H1:

1. PULLBACK  — continuação de tendência: H4 em estrutura direcional, D1 não contrário,
               recuo até zona de valor (EMA50 / FVG / Order Block) e gatilho de retomada.
2. BREAKOUT  — rompimento de estrutura (BOS/CHoCH) com deslocamento institucional e FVG,
               sem sobre-extensão em relação à média.
3. SWEEP     — varredura de liquidez (stop hunt): pavio além de um pool de liquidez
               (swing/igualdades/máx-mín do dia anterior) com fechamento de volta — falso
               rompimento — em contexto não contrário.
4. TREND     — momentum de série temporal: BOS de continuação no H1 com D1 e H4 alinhados.

Níveis: Stop Loss estrutural (além do extremo do setup + buffer de ATR), alvos em pools de
liquidez opostos (swings ativos H1/H4, máx/mín do dia/semana anterior) com R mínimo.
A mesma função é usada no backtest e na análise ao vivo (consistência metodológica).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SETUPS = ("PULLBACK", "BREAKOUT", "SWEEP", "TREND")
SETUP_PT = {"PULLBACK": "Pullback em tendência", "BREAKOUT": "Rompimento de estrutura com deslocamento",
            "SWEEP": "Varredura de liquidez / falso rompimento",
            "TREND": "Momentum de série temporal (BOS de continuação alinhado D1/H4/H1)"}

MIN_RISK_ATR = 1.0
MAX_RISK_ATR = 2.5
MIN_TP1_R = 1.3
MAX_TP1_R = 3.0
DEFAULT_TP1_R = 1.5


def _col(F: pd.DataFrame, name: str) -> pd.Series:
    return F[name] if name in F.columns else pd.Series(np.nan, index=F.index)


def _side_cols(d: int) -> dict[str, str]:
    if d == 1:
        return dict(in_fvg="in_fvg_bull", in_ob="in_ob_bull", engulf="bull_engulf", pin="bull_pin",
                    sweep="sweep_lo", sweep_eq="sweep_lo_eq", prev_ext="pdl", near_t="near_hi", near_opp="near_lo",
                    h4_near_t="h4_near_hi", pd_t="pdh", pw_t="pwh", opp_fvg="fvg_bear_bot",
                    opp_ob="ob_bear_bot", h4_in_fvg="h4_in_fvg_bull", h4_in_ob="h4_in_ob_bull",
                    ext="l", fail="fail_dn", h4_sh="h4_last_sh")
    return dict(in_fvg="in_fvg_bear", in_ob="in_ob_bear", engulf="bear_engulf", pin="bear_pin",
                sweep="sweep_hi", sweep_eq="sweep_hi_eq", prev_ext="pdh", near_t="near_lo", near_opp="near_hi",
                h4_near_t="h4_near_lo", pd_t="pdl", pw_t="pwl", opp_fvg="fvg_bull_top",
                opp_ob="ob_bull_top", h4_in_fvg="h4_in_fvg_bear", h4_in_ob="h4_in_ob_bear",
                ext="h", fail="fail_up", h4_sh="h4_last_sl")


def _dir_frame(F: pd.DataFrame, d: int) -> pd.DataFrame:
    s = _side_cols(d)
    c, o, h, lo = F["c"], F["o"], F["h"], F["l"]
    atr = F["atr"]
    d1_dir = np.sign(0.5 * F["d1_trend"].fillna(0) + 0.3 * F["d1_ema_stack"].fillna(0)
                     + 0.2 * F["d1_above_ema200"].fillna(0))
    h4_trend = F["h4_trend"].fillna(0)
    h4_adx = F["h4_adx"].fillna(0)
    d1_adx = F["d1_adx"].fillna(0)
    ext20 = d * (c - F["ema20"]) / atr
    rsi_dir = d * (F["rsi"] - 50)

    in_zone = ((F[s["in_fvg"]].rolling(3, min_periods=1).max() > 0)
               | (F[s["in_ob"]].rolling(3, min_periods=1).max() > 0)
               | (_col(F, s["h4_in_fvg"]).fillna(0) > 0) | (_col(F, s["h4_in_ob"]).fillna(0) > 0))
    if d == 1:
        at_ema = lo.rolling(3, min_periods=1).min() <= F["ema50"] + 0.3 * atr
        momentum_resume = (c > h.shift()) & (F["close_pos"] > 0.6) & (c > o)
        pulled = (F["rsi"].rolling(6, min_periods=1).min() < 45)
        swing_ext = lo.rolling(6, min_periods=1).min()
    else:
        at_ema = h.rolling(3, min_periods=1).max() >= F["ema50"] - 0.3 * atr
        momentum_resume = (c < lo.shift()) & (F["close_pos"] < 0.4) & (c < o)
        pulled = (F["rsi"].rolling(6, min_periods=1).max() > 55)
        swing_ext = h.rolling(6, min_periods=1).max()

    trigger = (F[s["engulf"]] > 0) | (F[s["pin"]] > 0) | momentum_resume | (np.sign(F["event"]) == d)

    pullback = ((h4_trend == d) & (d1_dir != -d) & pulled & (at_ema | in_zone) & trigger
                & (ext20 < 1.5))

    struct_break = np.sign(F["event"]) == d
    disp = (F["displacement"] == d) | (F["displacement"].shift() == d)
    fvg = (F["new_fvg"] == d) | (F["new_fvg"].shift() == d)
    breakout = (struct_break & disp & fvg & (h4_trend != -d) & ~((d1_dir == -d) & (d1_adx > 25))
                & (ext20 < 2.2))

    # varredura apenas de pools de liquidez relevantes: máx/mín do pregão anterior,
    # topos/fundos iguais (stops agrupados) ou swing do H4
    eq_sweep = F[s["sweep"]].notna() & (F[s["sweep_eq"]] > 0)
    if d == 1:
        pd_sweep = (lo < F["pdl"]) & (c > F["pdl"])
        h4_sweep = (lo < F["h4_last_sl"]) & (c > F["h4_last_sl"])
        wick_ok = F["close_pos"] >= 0.55
    else:
        pd_sweep = (h > F["pdh"]) & (c < F["pdh"])
        h4_sweep = (h > F["h4_last_sh"]) & (c < F["h4_last_sh"])
        wick_ok = F["close_pos"] <= 0.45
    sweep = ((eq_sweep | pd_sweep | h4_sweep) & wick_ok
             & ((d1_dir != -d) | (rsi_dir.shift() < -15))
             & ~((h4_trend == -d) & (h4_adx > 30)))

    # momentum de série temporal (Moskowitz, Ooi & Pedersen, 2012): continuação de estrutura
    # no H1 com D1 e H4 alinhados e tendência diária com força mínima
    trend_mom = ((np.sign(F["event"]) == d) & (F["trend"] == d) & (h4_trend == d) & (d1_dir == d)
                 & (d1_adx >= 20) & (ext20 < 1.2))

    # nível de stop por setup (extremo + buffer)
    buf = 0.25 * atr
    stop_pull = swing_ext - d * buf
    stop_brk = (lo.rolling(3, min_periods=1).min() if d == 1 else h.rolling(3, min_periods=1).max()) - d * 0.2 * atr
    stop_swp = (lo if d == 1 else h) - d * buf

    setup = pd.Series("", index=F.index, dtype=object)
    stop = pd.Series(np.nan, index=F.index)
    stop_trd = (F["last_sl"] if d == 1 else F["last_sh"]) - d * buf
    for name, mask, st in (("TREND", trend_mom, stop_trd), ("BREAKOUT", breakout, stop_brk),
                           ("PULLBACK", pullback, stop_pull), ("SWEEP", sweep, stop_swp)):
        m = mask.fillna(False).to_numpy(dtype=bool)
        setup[m] = name   # prioridade crescente: SWEEP sobrescreve PULLBACK que sobrescreve BREAKOUT
        stop[m] = st[m]
    n_setups = (pullback.fillna(False).astype(int) + breakout.fillna(False).astype(int)
                + sweep.fillna(False).astype(int) + trend_mom.fillna(False).astype(int))

    out = pd.DataFrame({
        "dir": d, "setup": setup, "sl": stop, "n_setups": n_setups,
        "d1_dir": d1_dir, "in_zone": in_zone.astype(int), "at_ema": at_ema.astype(int),
        "trigger_engulf": F[s["engulf"]].astype(int), "trigger_pin": F[s["pin"]].astype(int),
        "pd_sweep": pd_sweep.astype(int),
    }, index=F.index)
    return out[out["setup"] != ""]


def _targets(F: pd.DataFrame, cand: pd.DataFrame) -> pd.DataFrame:
    """Calcula risco, TP1/TP2 em pools de liquidez e espaço livre até o obstáculo oposto."""
    rows = []
    for t, r in cand.iterrows():
        d = int(r["dir"])
        f = F.loc[t]
        s = _side_cols(d)
        entry = float(f["c"])
        atr = float(f["atr"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        sl = float(r["sl"])
        risk = d * (entry - sl)
        if risk < MIN_RISK_ATR * atr:
            sl = entry - d * MIN_RISK_ATR * atr
            risk = MIN_RISK_ATR * atr
        if risk > MAX_RISK_ATR * atr or risk <= 0:
            continue
        levels = []
        for key in ("near_t", "h4_near_t", "pd_t", "pw_t", "h4_sh"):
            v = f.get(s[key], np.nan)
            if np.isfinite(v) and d * (v - entry) > 0:
                levels.append(float(v))
        levels.sort(key=lambda v: d * (v - entry))
        obstacles = [float(f.get(s[k], np.nan)) for k in ("opp_fvg", "opp_ob")]
        obstacles = [v for v in obstacles if np.isfinite(v) and d * (v - entry) > 0] + levels[:1]
        room = min((d * (v - entry) for v in obstacles), default=5 * risk) / risk
        tp1 = None
        for v in levels:
            rr = d * (v - entry) / risk
            if MIN_TP1_R <= rr <= MAX_TP1_R:
                # alvo levemente antes do pool de liquidez (ordens limitadas tendem a ser antecipadas)
                tp1 = v - d * 0.05 * atr
                break
        tp1_struct = tp1 is not None
        if tp1 is None:
            tp1 = entry + d * DEFAULT_TP1_R * risk
        rr1 = d * (tp1 - entry) / risk
        tp2 = None
        for v in levels:
            rr = d * (v - entry) / risk
            if rr >= rr1 + 0.8 and rr <= 5.0:
                tp2 = v - d * 0.05 * atr
                break
        if tp2 is None:
            tp2 = entry + d * max(2.5, rr1 + 1.0) * risk
        rows.append({
            "time": t, "dir": d, "setup": r["setup"], "entry_ref": entry, "sl": sl, "tp1": tp1,
            "tp2": tp2, "risk": risk, "risk_atr": risk / atr, "rr1": rr1,
            "rr2": d * (tp2 - entry) / risk, "room_r": min(room, 5.0), "tp1_structural": int(tp1_struct),
            "n_setups": int(r["n_setups"]), "in_zone": int(r["in_zone"]), "at_ema": int(r["at_ema"]),
            "trigger_engulf": int(r["trigger_engulf"]), "trigger_pin": int(r["trigger_pin"]),
            "pd_sweep": int(r["pd_sweep"]), "d1_dir": float(r["d1_dir"]), "atr": atr,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("time")


def generate(F: pd.DataFrame, cooldown: int = 3, last_n: int | None = None) -> pd.DataFrame:
    """Candidatos causais por barra. `last_n` restringe às últimas N barras (modo ao vivo)."""
    G = F.iloc[-(last_n + cooldown + 2):] if last_n else F
    parts = [_dir_frame(G, 1), _dir_frame(G, -1)]
    cand = pd.concat(parts).sort_index()
    if cand.empty:
        return pd.DataFrame()
    # conflito: setups opostos no mesmo candle -> descarta ambos
    dup = cand.index.duplicated(keep=False)
    cand = cand[~dup]
    # cooldown por direção para evitar amostras quase duplicadas
    keep = []
    last_at = {1: -10_000, -1: -10_000}
    pos = {t: i for i, t in enumerate(G.index)}
    for t, r in cand.iterrows():
        i = pos[t]
        if i - last_at[int(r["dir"])] > cooldown:
            keep.append(t)
            last_at[int(r["dir"])] = i
    cand = cand.loc[keep]
    if last_n:
        cand = cand[cand.index >= G.index[-last_n]]
    return _targets(G, cand)
