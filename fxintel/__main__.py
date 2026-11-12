"""CLI: python -m fxintel {analyze|train|quotes|serve}"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings


def main(argv: list[str] | None = None) -> int:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    ap = argparse.ArgumentParser(prog="fxintel", description="Motor de inteligência de mercado FX/metais")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="ANALISAR MERCADO AGORA (imprime JSON ou resumo)")
    a.add_argument("--json", action="store_true")
    sub.add_parser("train", help="dataset + walk-forward + modelo de produção + relatório")
    sub.add_parser("quotes", help="cotações atuais")
    s = sub.add_parser("serve", help="inicia o backend HTTP")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    from .logging_setup import setup_logging
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    if args.cmd == "train":
        from .training import train
        rep = train()
        print(json.dumps({"model_validated": rep["model_validated"], "files": rep.get("files")}, indent=1))
        return 0
    if args.cmd == "quotes":
        from .config import load_settings
        from .data import DataHub
        from . import instruments as I
        st = load_settings()
        hub = DataHub(st)
        for sym, q in hub.quotes(st["universe"]).items():
            print(f"{sym:7s} bid {q.bid:<12.5f} ask {q.ask:<12.5f} {q.source:8s} {q.spread_source:9s} "
                  f"idade {q.age_seconds():5.0f}s  spread {q.spread / I.get(sym).pip:4.1f} pips")
        return 0
    if args.cmd == "analyze":
        from .engine import AnalysisEngine
        from .report_text import render_text
        res = AnalysisEngine().analyze_now()
        print(json.dumps(res, indent=1, ensure_ascii=False, default=str) if args.json else render_text(res))
        return 0
    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("backend.app.main:app", host=args.host, port=args.port, log_level="info")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
