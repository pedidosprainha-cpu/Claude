"""Relatório de backtest/walk-forward em Markdown com gráficos (matplotlib)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ..config import ROOT  # noqa: E402
from .engine import simulate_portfolio  # noqa: E402

REPORT_DIR = ROOT / "reports"

# Paleta de referência validada (skill dataviz): slots categóricos 1–3, superfície e textos.
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"


def _style(ax, title: str, ylabel: str):
    ax.set_facecolor(SURF)
    ax.figure.set_facecolor(SURF)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=12, loc="left", pad=12)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def equity_chart(curves: dict[str, tuple], path: Path, title: str):
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    colors = [S1, S2, S3]
    for (name, (series, initial)), col in zip(curves.items(), colors):
        if series is None or len(series) == 0:
            continue
        y = (series.to_numpy() / initial - 1) * 100
        ax.plot(series.index, y, color=col, linewidth=2, label=name)
        ax.annotate(f"{name}: {y[-1]:+.1f}%", (series.index[-1], y[-1]), xytext=(6, 0),
                    textcoords="offset points", color=INK2, fontsize=8, va="center")
    ax.axhline(0, color=INK2, linewidth=0.8)
    _style(ax, title, "Retorno acumulado (%)")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF)
    plt.close(fig)


def calibration_chart(table: list[dict], path: Path, title: str):
    fig, ax = plt.subplots(figsize=(5.4, 5.0), dpi=150)
    ax.plot([0, 1], [0, 1], color=INK2, linewidth=1, linestyle="--", label="Calibração perfeita")
    x = np.array([r["mean_p"] for r in table])
    y = np.array([r["observed"] for r in table])
    lo = np.array([r["ci90"][0] for r in table])
    hi = np.array([r["ci90"][1] for r in table])
    n = np.array([r["n"] for r in table])
    ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt="o", color=S1, ecolor=S1, elinewidth=1.5,
                capsize=3, markersize=7, label="Frequência observada (IC 90%)")
    for xi, yi, ni in zip(x, y, n):
        ax.annotate(f"n={ni}", (xi, yi), xytext=(6, -10), textcoords="offset points", color=INK2, fontsize=7)
    lim = max(0.8, float(max(x.max(), hi.max())) + 0.05) if len(x) else 1
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    _style(ax, title, "Frequência observada de TP1 antes do stop")
    ax.set_xlabel("Probabilidade prevista (fora da amostra)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF)
    plt.close(fig)


def _f(v, fmt="{:.3f}"):
    if v is None:
        return "—"
    try:
        if isinstance(v, float) and not np.isfinite(v):
            return "—"
        return fmt.format(v)
    except (ValueError, TypeError):
        return str(v)


def write_markdown(report: dict, results: dict, primary: str) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    img = REPORT_DIR / "img"
    img.mkdir(exist_ok=True)
    day = datetime.fromisoformat(report["generated_at"]).strftime("%Y-%m-%d")
    prim = results[primary]
    initial = float(report["settings"]["account"]["equity"])

    curves = {}
    full = prim.get("completo", {})
    if full.get("_port"):
        curves["Selecionados pelo modelo"] = (full["_port"]["daily_equity"], initial)
    allp = simulate_portfolio(prim["oos"], {"risk": report["settings"]["risk"], "account": {"equity": initial}})
    curves["Todos os candidatos"] = (allp["daily_equity"], initial)
    eq_png = img / f"equity-{day}.png"
    equity_chart(curves, eq_png, "Curva de capital fora da amostra (walk-forward, custos incluídos)")
    cal_png = img / f"calibracao-{day}.png"
    calibration_chart(full["calibration"]["table"], cal_png,
                      f"Confiabilidade das probabilidades ({primary}, OOS)")

    wf = report["walk_forward"]
    L = []
    a = L.append
    a(f"# Relatório de Backtest e Validação Walk-Forward — {day}\n")
    a("> **Resultados históricos simulados não constituem desempenho comprovado nem garantem resultados futuros.** "
      "Todos os números abaixo vêm de dados reais de mercado (Yahoo Finance / proxies documentados), com custos "
      "estimados, e foram produzidos pelo próprio código deste repositório (`python -m fxintel train`).\n")
    a("## 1. Conclusão executiva\n")
    m = full["calibration"]["metrics"]
    ho = prim.get("holdout_2026", {})
    hm = ho.get("calibration", {}).get("metrics", {}) if ho else {}
    verdict = ("**O modelo NÃO demonstrou vantagem estatística e econômica robusta fora da amostra.** "
               f"Regra de validação: {report.get('validation_rule', '')}." if not report["model_validated"]
               else "**O modelo superou a climatologia fora da amostra** (ver ressalvas).")
    a(verdict + "\n")
    a(f"- Candidatos avaliados: **{report['dataset']['n_candidates']}** em {len(report['universe'])} instrumentos "
      f"({report['dataset']['start'][:10]} a {report['dataset']['end'][:10]}).")
    dn = report["dataset"]["all_candidates_net"]
    dg = report["dataset"]["all_candidates_gross"]
    a(f"- Expectativa de todos os candidatos: **{_f(dn.get('avg_r'), '{:+.3f}')} R líquido** "
      f"(IC90% {_f(dn['expectancy_ci90'][0], '{:+.3f}')} a {_f(dn['expectancy_ci90'][1], '{:+.3f}')}); "
      f"**{_f(dg.get('avg_r'), '{:+.3f}')} R bruto** (sem spread/slippage).")
    a(f"- Modelo primário ({primary}), OOS completo: Brier {_f(m.get('brier'), '{:.4f}')} vs climatologia "
      f"{_f(m.get('brier_climatology'), '{:.4f}')} → **BSS {_f(m.get('bss'), '{:+.4f}')}**, AUC {_f(m.get('auc'))}.")
    if hm:
        a(f"- Holdout 2026 (nunca usado para decisões de desenho): BSS {_f(hm.get('bss'), '{:+.4f}')}, "
          f"AUC {_f(hm.get('auc'))}, n={hm.get('n')}.")
    hsel = (ho or {}).get("selected_trades", {}) if ho else {}
    hport = ((ho or {}).get("portfolio_selected") or {}) if ho else {}
    if hsel.get("n"):
        htm, hem = hport.get("trade_metrics", {}), hport.get("equity_metrics", {})
        hrb = (ho.get("random_selection_baseline") or {})
        a(f"- Holdout 2026, trades selecionados: n={hsel.get('n')}, R médio {_f(hsel.get('avg_r'), '{:+.3f}')} "
          f"(p-valor média>0 = {_f(hsel.get('p_value_mean_gt0'))}); portfólio {htm.get('n', 0)} trades, "
          f"retorno {_f(hem.get('total_return_pct'), '{:+.1f}%')}, PF {_f(htm.get('profit_factor'), '{:.2f}')}; "
          f"vs. seleção aleatória p={_f(hrb.get('p_value'))}. Sinal positivo, porém amostra pequena, não "
          "significativo na média e contrário ao período de desenvolvimento — insuficiente para validar o modelo.")
    sel = full.get("selected_trades", {})
    a(f"- Trades selecionados pelo portão de EV: n={sel.get('n', 0)}, R médio {_f(sel.get('avg_r'), '{:+.3f}')}, "
      f"p-valor (média>0) {_f(sel.get('p_value_mean_gt0'))}.")
    rb = full.get("random_selection_baseline") or {}
    if rb:
        a(f"- Seleção aleatória com o mesmo nº de trades/mês: R médio {_f(rb.get('random_mean_avg_r'), '{:+.3f}')} "
          f"→ p-valor do filtro do modelo = {_f(rb.get('p_value'))} (valores altos = filtro não agrega valor).")
    ds = report.get("deflated_sharpe_selected") or {}
    if ds.get("dsr") is not None:
        a(f"- Deflated Sharpe Ratio ({ds['trials']} configurações testadas): {_f(ds['dsr'])} "
          f"(PSR vs 0: {_f(ds['psr_vs_0'])}).")
    a("\n**Consequência operacional:** com a configuração padrão (`gates.require_model = true`), o motor só emite "
      "sinal quando o modelo está validado fora da amostra *e* o EV calibrado supera o mínimo. Enquanto essas "
      "condições não forem atendidas, o comando *ANALISAR MERCADO AGORA* responde **\"Nenhuma oportunidade "
      "qualificada\"** e mostra os melhores candidatos apenas como observação, com os motivos do bloqueio. "
      "Esse é o comportamento correto diante da evidência — não um defeito.\n")

    a("## 2. Dados e protocolo\n")
    a("- Barras H1 (H4 e D1 derivadas de H1, alinhadas ao fechamento de NY 22:00 UTC).")
    a("- Ouro: PAXG-USD (proxy 24/7, fins de semana removidos). Prata: futuro SI=F com reparo de rolagem.")
    a("- Spread estimado por instrumento × multiplicador de sessão; slippage = "
      f"{report['settings']['slippage']['base_pips']} pip + {report['settings']['slippage']['atr_fraction']}×ATR(H1).")
    a("- Entrada na abertura do candle seguinte ao sinal; stop executa no pior entre nível e abertura (gaps); "
      "stop e alvo no mesmo candle ⇒ stop primeiro; 50% no TP1, restante com stop no preço de entrada até TP2; "
      f"horizonte máximo de {report['settings']['horizon_bars']} horas.")
    a("- Walk-forward mensal, treino expansivo, *purging* de rótulos não resolvidos + embargo de 24h.")
    a("- Climatologia do BSS = taxa-base do conjunto de treino de cada mês (não do teste).")
    a("- Portfólio: risco de " f"{report['settings']['risk']['risk_per_trade_pct']}% por trade, máx. "
      f"{report['settings']['risk']['max_open_positions']} posições, 1 por instrumento, limite de "
      f"{report['settings']['risk']['max_risk_per_currency_pct']}% por moeda/direção, limites de perda diária "
      f"({report['settings']['risk']['max_daily_loss_pct']}%) e semanal ({report['settings']['risk']['max_weekly_loss_pct']}%).\n")

    a("## 3. Candidatos por setup (amostra completa)\n")
    a("| Setup | n | Acerto TP1 | R médio líquido | R médio bruto | Custo médio (R) |")
    a("|---|---:|---:|---:|---:|---:|")
    for k, v in report["dataset"]["by_setup"].items():
        a(f"| {k} | {v['n']} | {_f(v['hit_rate'], '{:.1%}')} | {_f(v['avg_r'], '{:+.3f}')} | "
          f"{_f(v['avg_r_gross'], '{:+.3f}')} | {_f(v['avg_cost_r'], '{:.3f}')} |")
    a("\n## 4. Candidatos por instrumento\n")
    a("| Instrumento | n | Acerto TP1 | R médio líquido | R médio bruto | Custo médio (R) |")
    a("|---|---:|---:|---:|---:|---:|")
    for k, v in report["dataset"]["by_symbol"].items():
        a(f"| {k} | {v['n']} | {_f(v['hit_rate'], '{:.1%}')} | {_f(v['avg_r'], '{:+.3f}')} | "
          f"{_f(v['avg_r_gross'], '{:+.3f}')} | {_f(v['avg_cost_r'], '{:.3f}')} |")

    a("\n## 5. Calibração e discriminação fora da amostra\n")
    a("| Modelo | Período | n | Brier | Brier climatologia | BSS | AUC | Log-loss |")
    a("|---|---|---:|---:|---:|---:|---:|---:|")
    for kind, res in wf.items():
        for per in ("desenvolvimento", "holdout_2026", "completo"):
            if per not in res:
                continue
            mm = res[per]["calibration"]["metrics"]
            a(f"| {kind} | {per} | {mm.get('n')} | {_f(mm.get('brier'), '{:.4f}')} | "
              f"{_f(mm.get('brier_climatology'), '{:.4f}')} | {_f(mm.get('bss'), '{:+.4f}')} | "
              f"{_f(mm.get('auc'))} | {_f(mm.get('log_loss'), '{:.4f}')} |")
    a(f"\n![Calibração]({cal_png.relative_to(REPORT_DIR).as_posix()})\n")
    a("Tabela de confiabilidade (modelo primário, OOS completo):\n")
    a("| Faixa prevista | n | p médio previsto | Frequência observada | IC 90% (Wilson) |")
    a("|---|---:|---:|---:|---|")
    for r in full["calibration"]["table"]:
        a(f"| {r['bin'][0]:.2f}–{r['bin'][1]:.2f} | {r['n']} | {r['mean_p']:.3f} | {r['observed']:.3f} | "
          f"{r['ci90'][0]:.3f}–{r['ci90'][1]:.3f} |")

    a("\n## 6. Desempenho de portfólio fora da amostra\n")
    a(f"![Curva de capital]({eq_png.relative_to(REPORT_DIR).as_posix()})\n")
    a("| Modelo | Período | Conjunto | Trades | Acerto | R médio | Profit Factor | Retorno | Máx. DD | Sharpe | Meses positivos |")
    a("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for kind, res in wf.items():
        for per in ("desenvolvimento", "holdout_2026", "completo"):
            if per not in res:
                continue
            for label, key in (("selecionados", "portfolio_selected"), ("todos", "portfolio_all_candidates")):
                pp = res[per].get(key)
                if not pp:
                    a(f"| {kind} | {per} | {label} | 0 | — | — | — | — | — | — | — |")
                    continue
                tm, em = pp["trade_metrics"], pp["equity_metrics"]
                a(f"| {kind} | {per} | {label} | {tm.get('n', 0)} | {_f(tm.get('win_rate'), '{:.1%}')} | "
                  f"{_f(tm.get('avg_r'), '{:+.3f}')} | {_f(tm.get('profit_factor'), '{:.2f}')} | "
                  f"{_f(em.get('total_return_pct'), '{:+.1f}%')} | {_f(em.get('max_drawdown_pct'), '{:.1f}%')} | "
                  f"{_f(em.get('sharpe'), '{:.2f}')} | {_f(em.get('pct_profitable_months'), '{:.0f}%')} |")

    a("\n## 7. Registro do processo de pesquisa (controle de viés de seleção)\n")
    for it in report["research_log"]:
        a(f"- **Iteração {it['iteration']}** — {it['change']}. {it['note']}")
    a(f"\nTotal de configurações avaliadas: {len(report['research_log'])} desenhos × 2 modelos = "
      f"{len(report['research_log']) * 2}. Nenhum parâmetro foi otimizado em dados fora da amostra.\n")

    a("## 8. Limitações conhecidas\n")
    for t in (
        "Dados gratuitos sem bid/ask histórico: spread e slippage são *estimados*; spreads reais em notícias podem ser muito maiores.",
        "Ouro via PAXG-USD e prata via futuro SI=F são proxies do spot; diferenças de base e microestrutura existem.",
        "O calendário econômico não tem histórico point-in-time disponível — o bloqueio por eventos não está no backtest "
        "(no ao vivo ele está ativo, o que tende a reduzir a amostra mas não foi medido).",
        "Swap/rolagem overnight não modelado (posições até 36h).",
        "≈2,8 anos de H1 (≈1,8 ano de teste OOS): poder estatístico limitado para detectar vantagens pequenas.",
        "Taxas de juros dos bancos centrais são uma tabela manual atual (sem histórico) e por isso não entram no modelo.",
        "Componentes M15/M5 da análise ao vivo (tempo de entrada) não fazem parte do modelo validado.",
    ):
        a(f"- {t}")
    a("\n## 9. Reprodutibilidade\n")
    a("```bash\npython -m fxintel train      # recria dataset, walk-forward, modelo e este relatório\n```\n")
    a(f"Arquivo de dados completo: `reports/backtest-{day}.json`.\n")

    md = REPORT_DIR / f"RELATORIO-BACKTEST-{day}.md"
    md.write_text("\n".join(L), encoding="utf-8")
    js = REPORT_DIR / f"backtest-{day}.json"
    js.write_text(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=1, ensure_ascii=False,
                             default=str), encoding="utf-8")
    return {"markdown": str(md), "json": str(js), "equity_png": str(eq_png), "calibration_png": str(cal_png)}
