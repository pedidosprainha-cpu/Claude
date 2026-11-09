"""Command line: `python -m fxengine [scan|analisar] [opções]`."""
from __future__ import annotations

import argparse
import os
import sys
import time

from .config import Settings
from .engine import Engine
from .report import render_markdown, render_text, to_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fxengine",
        description="Motor de análise gráfica, quantitativa e fundamentalista de Forex e metais "
                    "— encontra a melhor entrada a mercado agora.")
    p.add_argument("cmd", nargs="?", default="scan", choices=["scan", "analisar", "analyze", "rompimentos"],
                   help="scan/analisar = varrer o universo (padrão); analyze = detalhar ativos (use --ativos); "
                        "rompimentos = detector de rompimentos em tempo real")
    p.add_argument("--monitorar", type=int, metavar="SEG", default=0,
                   help="com 'rompimentos': repetir a varredura a cada SEG segundos e avisar os novos")
    p.add_argument("--min-nota", default="B", choices=["A+", "A", "B", "C", "D"],
                   help="com 'rompimentos': nota mínima exibida (padrão B)")
    p.add_argument("--ativos", "-a", default=None,
                   help="'all' (padrão), 'fx', 'metais' ou lista: EURUSD,XAUUSD")
    p.add_argument("--saldo", type=float, default=10_000.0, help="saldo da conta em USD (padrão 10000)")
    p.add_argument("--risco", type=float, default=1.0, help="%% do saldo arriscado por trade (padrão 1.0)")
    p.add_argument("--top", type=int, default=10, help="linhas no ranking")
    p.add_argument("--min-score", type=float, default=None, help="score mínimo para recomendar execução")
    p.add_argument("--tz", default="America/Sao_Paulo", help="fuso para exibir horários")
    p.add_argument("--detalhe", action="store_true", help="tabela multi-timeframe do ativo escolhido")
    p.add_argument("--json", metavar="ARQ", help="salvar resultado em JSON ('-' = stdout)")
    p.add_argument("--md", metavar="ARQ", help="salvar relatório Markdown")
    p.add_argument("--salvar", action="store_true", help="salvar relatório em reports/AAAA-MM-DD_HHMM.{md,json}")
    p.add_argument("--offline", action="store_true", help="dados sintéticos (demonstração/testes)")
    p.add_argument("--sem-edge", action="store_true", help="desligar o estudo de edge histórico")
    p.add_argument("--sem-noticias", action="store_true", help="não buscar manchetes")
    p.add_argument("--sem-cot", action="store_true", help="não buscar COT da CFTC")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    s = Settings(balance=a.saldo, risk_pct=a.risco, top_n=a.top, offline=a.offline,
                 use_edge=not a.sem_edge, use_news=not a.sem_noticias, use_cot=not a.sem_cot)
    if a.min_score is not None:
        s.min_score = a.min_score
    if a.cmd == "rompimentos":
        return run_breakouts(s, a)
    t0 = time.time()
    res = Engine(s).scan(a.ativos)
    if not res.opportunities:
        print("Nenhum ativo pôde ser analisado. Falhas:", res.errors or res.ctx.status, file=sys.stderr)
        return 2
    detail = a.detalhe or a.cmd == "analyze"
    txt = render_text(res, a.tz, detail=detail)
    if a.json != "-":
        print(txt)
        print(f" (varredura concluída em {time.time() - t0:.1f}s)")
    if a.json:
        js = to_json(res)
        if a.json == "-":
            print(js)
        else:
            with open(a.json, "w", encoding="utf-8") as f:
                f.write(js)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(render_markdown(res, a.tz))
    if a.salvar:
        os.makedirs(s.reports_dir, exist_ok=True)
        stem = os.path.join(s.reports_dir, f"{res.now:%Y-%m-%d_%H%M}")
        with open(stem + ".md", "w", encoding="utf-8") as f:
            f.write(render_markdown(res, a.tz))
        with open(stem + ".json", "w", encoding="utf-8") as f:
            f.write(to_json(res))
        print(f" relatório salvo em {stem}.md / .json")
    return 0



GRADE_ORDER = ["D", "C", "B", "A", "A+"]


def render_breakouts(r, min_grade: str = "B", only_new: bool = False) -> str:
    from .breakouts import STATUS_LABEL
    keep = [b for b in r.breakouts if GRADE_ORDER.index(b.grade) >= GRADE_ORDER.index(min_grade)
            and (b.is_new or not only_new)]
    head = (f"ROMPIMENTOS · {r.now:%d/%m %H:%M:%S} UTC · {r.session.label} · {r.scanned} ativos · "
            f"{len(r.breakouts)} eventos ({r.new_count} novos)")
    lines = [head, "★ = melhores do modelo (A/A+) · x = bloqueado (esticado, spread alto, evento ou pré-alerta)",
             "-" * len(head)]
    if not keep:
        lines.append(f"  nenhum rompimento com nota ≥ {min_grade}" + (" novo" if only_new else ""))
    for b in keep:
        p, i = b.plan, b.inst
        flag = "NOVO " if b.is_new else "     "
        act = "★" if b.actionable else ("·" if not b.blocked else "x")
        score = (f"P(alvo1) {b.prob * 100:3.0f}% · {b.ev_r:+.2f}R" if b.prob is not None
                 else f"nota ({b.quality:4.0f})")
        lines.append(f" {act} {flag}{b.symbol:<7} {b.tf:<3} {b.side:<6} {STATUS_LABEL[b.status]:<17} "
                     f"{b.grade:<2} {score}  nível {i.fmt(b.level.price)} [{b.level.label[:44]}]")
        lines.append(f"         entrada {i.fmt(p.entry)}  stop {i.fmt(p.sl)}  alvo1 {i.fmt(p.tp1)} ({p.rr1:.1f}R)  "
                     f"alvo2 {i.fmt(p.tp2)} ({p.rr2:.1f}R)  lote {p.lots:.2f}")
        if b.cons:
            lines.append(f"         atenção: {'; '.join(b.cons[:2])}")
    return "\n".join(lines)


def run_breakouts(s: Settings, a) -> int:
    import os
    from datetime import datetime, timezone
    from . import breakouts as bk

    eng = Engine(s)
    os.makedirs(s.cache_dir, exist_ok=True)
    state = os.path.join(s.cache_dir, "breakouts_state.json")
    first = True
    while True:
        r = bk.scan(eng.provider, s, a.ativos, eng.now() if s.offline else datetime.now(timezone.utc), state)
        print(render_breakouts(r, a.min_nota, only_new=not first), flush=True)
        if any(b.is_new and b.actionable for b in r.breakouts) and not first:
            print("\a", end="", flush=True)
        if not a.monitorar:
            return 0
        first = False
        time.sleep(max(a.monitorar, 30))


if __name__ == "__main__":
    raise SystemExit(main())
