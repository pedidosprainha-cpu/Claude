#!/usr/bin/env python3
"""Turns <snapshot>/scan.json into the Portuguese market-scan table (Markdown).

Usage: python3 fx_report_table.py <snapshot_dir>

Qualitative labels are derived mechanically from the scanner metrics so every
pair is judged by the same rules:
  * Tendência CP  : H1 + M15 EMA stack (8/20/50) and M15 swing structure
  * Momentum      : M15 MACD-histogram sign/slope + ADX(M15) + M5 confirmation
  * Situação      : stretch vs EMA20-M15 (ATR units) + room to next obstacle
  * Risco correção: RSI H1/M15 extremes, day move vs ADR, room
  * Classificação : score bands, capped by the hard exclusion filters (section 6)
"""
import json, sys


def trend(r):
    h, m, b = r["S"]["h1"]["stack"], r["S"]["m15"]["stack"], r["st15"]["bias"]
    s = h + m + b
    return {3: "Alta", 2: "Alta", 1: "Alta fraca", 0: "Lateral", -1: "Baixa fraca", -2: "Baixa", -3: "Baixa"}[s]


def momentum(r):
    s15, s5 = r["S"]["m15"], r["S"]["m5"]
    d = 1 if s15["mh"] > 0 else -1
    rising = (s15["mh"] - s15["mh_prev"]) * d > 0
    same5 = s5["mh"] * d > 0
    arrow = "↑" if d > 0 else "↓"
    if s15["adx"] >= 25 and rising and same5:
        return f"Forte {arrow}"
    if s15["adx"] >= 18 and (rising or same5):
        return f"Moderado {arrow}"
    if not rising and not same5:
        return f"Perdendo força {arrow}"
    return "Fraco/neutro"


def hard_filters(r, side):
    b = r[side]
    flags = []
    if b["room_atr15"] < 0.8:
        flags.append("obstáculo < 0,8 ATR")
    if b["z15"] > 2.0:
        flags.append("esticado > 2 ATR")
    if b["day_move_adr"] > 1.0:
        flags.append("dia > 1 ADR")
    if (b["rsi_h1"] > 72 and side == "BUY") or (b["rsi_h1"] < 28 and side == "SELL"):
        flags.append("RSI H1 extremo")
    if r["spread_p"] * 1.0 > 0.35 * r["atr5_p"]:
        flags.append("spread alto vs ATR M5")
    sgn = 1 if side == "BUY" else -1
    if r["S"]["h1"]["stack"] != sgn:
        flags.append("H1 não alinhado")
    if r["S"]["m15"]["mh"] * sgn < 0 and (r["S"]["m15"]["mh"] - r["S"]["m15"]["mh_prev"]) * sgn < 0:
        flags.append("momentum M15 contrário")
    return flags


def situation(r, side):
    b = r[side]
    z, room = b["z15"], b["room_atr15"]
    if room < 0.8:
        where = "colado em resistência" if side == "BUY" else "colado em suporte"
    elif z > 2.0:
        where = "esticado"
    elif z < -0.5:
        where = "contra a média"
    elif z <= 1.2:
        where = "no valor"
    else:
        where = "levemente esticado"
    return f"{side} {where} (z={z:+.1f}, espaço {room:.1f} ATR)"


def risk(r, side):
    b = r[side]
    pts = 0
    pts += b["room_atr15"] < 0.8
    pts += b["day_move_adr"] > 0.9
    rh = b["rsi_h1"] if side == "BUY" else 100 - b["rsi_h1"]
    r15 = b["rsi_m15"] if side == "BUY" else 100 - b["rsi_m15"]
    pts += rh > 68
    pts += r15 > 68
    pts += b["z15"] > 1.6
    return "Alto" if pts >= 3 else ("Médio" if pts >= 1 else "Baixo")


def grade(r, side):
    sc = r[side]["score"]
    flags = hard_filters(r, side)
    g = "A" if sc >= 75 else ("B" if sc >= 65 else ("C" if sc >= 55 else "D"))
    if flags and g in ("A", "B"):
        g = "C"
    return g, flags


def fmt(p, x):
    d = 3 if p.endswith("JPY") else 5
    return f"{x:.{d}f}"


def main(snap):
    scan = json.load(open(f"{snap}/scan.json"))
    rows = []
    for r in scan:
        side = r["best"]
        g, flags = grade(r, side)
        rows.append((r, side, g, flags))
    order = {"A": 0, "B": 1, "C": 2, "D": 3}
    rows.sort(key=lambda t: (order[t[2]], -t[0][t[1]]["score"]))
    print("| # | Par | Bid / Ask (prime) | Spread | Cotação (UTC) | Tendência CP | Momentum | Situação da entrada | Risco correção | Score | Classe | Filtros violados |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, (r, side, g, flags) in enumerate(rows, 1):
        p = r["pair"]
        print(f"| {i} | {p[:3]}/{p[3:]} | {fmt(p, r['bid'])} / {fmt(p, r['ask'])} | {r['spread_p']:.1f} | {r['q_time']} | "
              f"{trend(r)} | {momentum(r)} | {situation(r, side)} | {risk(r, side)} | {r[side]['score']:.0f} | {g} | "
              f"{'; '.join(flags) if flags else '—'} |")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")
