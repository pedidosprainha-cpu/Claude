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
    p.add_argument("cmd", nargs="?", default="scan", choices=["scan", "analisar", "analyze"],
                   help="scan/analisar = varrer o universo (padrão); analyze = detalhar ativos (use --ativos)")
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


if __name__ == "__main__":
    raise SystemExit(main())
