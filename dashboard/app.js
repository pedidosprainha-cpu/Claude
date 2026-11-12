/* FXIntel — painel web (vanilla JS). */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const pct = (v, d = 1) => (v === null || v === undefined ? "—" : (v * 100).toFixed(d) + "%");
const KEY = "fxi_key";
let key = null; try { key = localStorage.getItem(KEY); } catch (e) { key = null; }
let state = { analysis: null, selected: null, tf: "H1", symbol: "EURUSD", chart: null, series: null, lines: [], lastAlertId: 0, digits: {} };

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-API-Key": key || "", ...(opts.headers || {}) } });
  if (r.status === 401) { askKey(); throw new Error("Chave de API inválida"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(m); }
  return r.json();
}

function askKey() { $("#key-modal").classList.remove("hidden"); $("#key-input").focus(); }
$("#key-save").onclick = () => { key = $("#key-input").value.trim(); try { localStorage.setItem(KEY, key); } catch (e) {} $("#key-modal").classList.add("hidden"); boot(); };
$("#btn-key").onclick = askKey;

/* ---------------- abas */
$$("#tabs button").forEach((b) => (b.onclick = () => {
  $$("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  $$(".tab").forEach((t) => t.classList.toggle("on", t.id === "tab-" + b.dataset.tab));
  const t = b.dataset.tab;
  if (t === "historico") loadHistory();
  if (t === "alertas") { loadAlerts(); $("#alert-badge").classList.add("hidden"); $("#alert-badge").textContent = "0"; }
  if (t === "modelo") loadModel();
  if (t === "config") loadSettings();
  if (t === "sistema") loadSystem();
  if (t === "painel" && state.chart) state.chart.timeScale().fitContent();
}));

/* ---------------- WebSocket */
let ws, wsRetry = 1000;
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/api/v1/ws?api_key=${encodeURIComponent(key || "")}`);
  ws.onopen = () => { wsRetry = 1000; pill("#st-ws", "ok", "● ao vivo"); };
  ws.onclose = () => { pill("#st-ws", "bad", "● desconectado"); setTimeout(connectWS, wsRetry); wsRetry = Math.min(wsRetry * 2, 30000); };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "quotes" || m.type === "hello") renderQuotes(m.quotes || m.data, m.at);
    if (m.type === "alert") onAlert(m.data);
    if (m.type === "analysis" && (!state.analysis || state.analysis.id !== m.data.id)) $("#analyze-msg").textContent = "Nova análise: " + m.data.headline;
  };
  setInterval(() => { try { ws.readyState === 1 && ws.send("ping"); } catch (e) {} }, 25000);
}
function pill(sel, cls, text) { const el = $(sel); el.className = "pill " + cls; el.textContent = text; }

/* ---------------- cotações */
function renderQuotes(q, at) {
  if (!q) return;
  $("#quotes-at").textContent = at ? "atualizado " + at.slice(11, 19) + " UTC" : "";
  const rows = Object.values(q).sort((a, b) => a.symbol.localeCompare(b.symbol)).map((x) => {
    const d = state.digits[x.symbol] ?? 5;
    const ch = x.change_pct;
    return `<tr class="click" data-s="${x.symbol}"><td><b>${x.symbol}</b></td><td>${fmt(x.bid, d)}</td><td>${fmt(x.ask, d)}</td>
      <td>${fmt(x.spread_pips, 1)}${x.spread_source === "estimated" ? "<span class=muted>*</span>" : ""}</td>
      <td class="${ch > 0 ? "up" : ch < 0 ? "down" : "flat"}">${ch === null ? "—" : (ch > 0 ? "+" : "") + fmt(ch, 2) + "%"}</td>
      <td class="${x.age_s > 180 ? "down" : ""}">${fmt(x.age_s, 0)}s</td><td class="muted">${esc(x.source)}</td></tr>`;
  });
  $("#quotes tbody").innerHTML = rows.join("") + `<tr><td colspan=7 class=muted>* spread estimado (provedor sem bid/ask real)</td></tr>`;
  $$("#quotes tr.click").forEach((tr) => (tr.onclick = () => { state.selected = null; loadChart(tr.dataset.s); }));
}

/* ---------------- análise */
$("#btn-analyze").onclick = async () => {
  const b = $("#btn-analyze"); b.disabled = true; b.textContent = "ANALISANDO…";
  $("#analyze-msg").textContent = "Coletando cotações, barras multi-timeframe, intermercados, calendário e executando os modelos…";
  const t0 = performance.now();
  try { const r = await api("/api/v1/analyze", { method: "POST" }); renderAnalysis(r);
    $("#analyze-msg").textContent = `Concluído em ${((performance.now() - t0) / 1000).toFixed(1)} s (motor: ${r.elapsed_ms} ms)`;
  } catch (e) { $("#analyze-msg").textContent = "Falha: " + e.message; }
  b.disabled = false; b.textContent = "ANALISAR MERCADO AGORA";
};

function probBar(p) {
  if (!p || p.calibrated_p === null) return "<span class=muted>não disponível</span>";
  const ci = p.ci90 || [p.calibrated_p, p.calibrated_p];
  return `<div class="prob"><div class="probbar"><div class="ci" style="left:${ci[0] * 100}%;width:${Math.max(1, (ci[1] - ci[0]) * 100)}%"></div>
    <div class="pt" style="left:calc(${p.calibrated_p * 100}% - 2px)"></div></div>
    <b>${pct(p.calibrated_p)}</b><span class="muted">IC90% ${pct(ci[0])}–${pct(ci[1])} · n=${p.n_oos_bin} · modelo ${fmt(p.model_p, 3)}</span></div>`;
}

function candHTML(s, isSignal) {
  const d = state.digits[s.instrument] ?? 5;
  const q = s.reference_quote;
  const tps = s.take_profit.map((t) => `${esc(t.label)}: <b>${fmt(t.price, d)}</b> (${fmt(t.pips, 1)} pips, ${fmt(t.rr, 2)}R)`).join("<br>");
  const gates = s.gates.map((g) => `<div class="gate ${g.passed ? "pass" : "fail"}"><b>${g.passed ? "✔" : "✖"} ${esc(g.gate.replace(/_/g, " "))}</b>${esc(g.detail)}</div>`).join("");
  const sz = (s.risk || {}).sizing || {};
  const li = (arr) => `<ul class="just">${(arr || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  return `
  <div class="sig-head"><span class="dir ${s.direction}">${s.direction}</span><span class="headline">${s.instrument}</span>
    <span class="pill">${esc(s.setup_name)}</span><span class="pill">score ${fmt(s.score, 0)}</span>
    ${isSignal ? "" : '<span class="pill bad">observação — não recomendada</span>'}</div>
  <div class="kv">
    <div>Instrumento</div><div>${s.instrument}</div>
    <div>Direção</div><div>${s.direction === "BUY" ? "Compra (BUY)" : "Venda (SELL)"}</div>
    <div>Tipo de execução</div><div>${esc(s.execution_type)}</div>
    <div>Cotação de referência</div><div>bid ${fmt(q.bid, d)} / ask ${fmt(q.ask, d)} · spread ${fmt(q.spread_pips, 1)} pips${q.spread_source === "estimated" ? " (estimado)" : ""} · ${q.time.slice(11, 19)} UTC · ${esc(q.source)} · idade ${fmt(q.age_s, 0)}s</div>
    <div>Entrada</div><div><b>${fmt(s.entry.price, d)}</b> (${s.entry.side})</div>
    <div>Stop Loss</div><div><b>${fmt(s.stop_loss.price, d)}</b> (${fmt(s.stop_loss.pips, 1)} pips) — <span class=muted>${esc(s.stop_loss.basis)}</span></div>
    <div>Take Profit</div><div>${tps}</div>
    <div>Risco-retorno</div><div>TP1 ${fmt(s.risk_reward.rr_tp1)}R · líquido ${fmt(s.risk_reward.rr_net_tp1)}R · custo ${fmt(s.risk_reward.cost_r, 3)}R</div>
    <div>Probabilidade</div><div>${probBar(s.probability)}<span class=muted>${esc(s.probability.event)}</span></div>
    <div>Valor esperado</div><div>${fmt(s.expected_value_r, 3)} R ${s.expected_value_r_ci_low !== null ? `<span class=muted>(limite inferior IC: ${fmt(s.expected_value_r_ci_low, 3)} R)</span>` : ""}</div>
    <div>Confiança do modelo</div><div><b>${esc(s.confidence.level)}</b>${li(s.confidence.limitations)}</div>
    <div>Validade</div><div>até ${s.validity.valid_until.slice(11, 16)} UTC (${s.validity.minutes} min)</div>
    ${sz.ok ? `<div>Tamanho sugerido</div><div>${sz.lots} lote(s) · risco ${sz.risk_amount} ${sz.account_currency} (${sz.risk_pct}%) · margem ${sz.margin}</div>` : ""}
  </div>
  <h4>Justificativa técnica</h4>${li(s.justification.technical)}
  <h4>Justificativa fundamentalista</h4>${li(s.justification.fundamental)}
  <h4>Justificativa quantitativa</h4>${li(s.justification.quantitative)}
  <h4>Invalidação</h4>${li(s.invalidation)}
  <h4>Cenários</h4><ul class="just"><li><b>Principal:</b> ${esc(s.scenarios.principal)}</li><li><b>Alternativo:</b> ${esc(s.scenarios.alternativo)}</li>${(s.scenarios.riscos || []).map((r) => `<li>Risco: ${esc(r)}</li>`).join("")}</ul>
  <h4>Portões de validação</h4><div class="gates">${gates}</div>
  ${isSignal ? `<div class="actions" style="margin-top:12px"><button class="primary" id="btn-paper">Executar em conta demo</button><span class="muted">${esc(s.execution_note || "")}</span></div>` : ""}`;
}

function renderAnalysis(r) {
  state.analysis = r;
  const el = $("#result"); el.classList.remove("hidden");
  let html = `<div class="card-h"><h3>Resultado — ${r.created_at.slice(0, 19).replace("T", " ")} UTC</h3><span class="muted">${r.elapsed_ms} ms · ${esc(r.trigger || "")}</span></div>`;
  if (r.signal) html += candHTML(r.signal, true);
  else html += `<div class="nosig"><div class="headline">${esc(r.headline)}</div><ul class="just">${r.no_signal_reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <div class="muted">O motor não emite recomendação quando dados, condições de mercado ou evidência estatística são insuficientes.</div></div>`;
  if (r.observations && r.observations.length) {
    html += `<h4>Observações (não passaram em todos os portões)</h4>` + r.observations.map((c, i) =>
      `<div class="obs" data-i="${i}"><b>${c.direction} ${c.instrument}</b> · ${esc(c.setup_name)} · score ${fmt(c.score, 0)} · EV ${fmt(c.expected_value_r, 3)}R ·
      <span class="muted">bloqueado por: ${c.gates.filter((g) => !g.passed).map((g) => g.gate).join(", ")}</span><div class="obs-body hidden"></div></div>`).join("");
  }
  el.innerHTML = html;
  $$(".obs", el).forEach((o) => (o.onclick = (ev) => {
    if (ev.target.closest(".obs-body")) return;
    const c = r.observations[+o.dataset.i]; const b = $(".obs-body", o);
    if (b.classList.contains("hidden")) { b.innerHTML = candHTML(c, false); b.classList.remove("hidden"); state.selected = c; loadChart(c.instrument); }
    else b.classList.add("hidden");
  }));
  const bp = $("#btn-paper");
  if (bp) bp.onclick = async () => { try { const x = await api("/api/v1/paper/execute", { method: "POST", body: JSON.stringify({ signal_id: r.signal.id }) }); bp.textContent = "Executado (demo) @ " + x.fill_price; bp.disabled = true; } catch (e) { alert(e.message); } };
  state.selected = r.signal || null;
  loadChart(r.signal ? r.signal.instrument : (r.observations?.[0]?.instrument || state.symbol));
  renderMarket(r);
}

const arrow = (v) => (v > 0 ? '<span class="up">▲</span>' : v < 0 ? '<span class="down">▼</span>' : '<span class="flat">■</span>');
function renderMarket(r) {
  $("#market tbody").innerHTML = r.market.map((m) => `<tr class="click" data-s="${m.symbol}"><td><b>${m.symbol}</b></td>
    <td>${arrow(m.trend?.D1)}</td><td>${arrow(m.trend?.H4)}</td><td>${arrow(m.trend?.H1)}</td><td>${arrow(m.trend?.M15)}</td>
    <td>${fmt(m.alignment, 2)}</td><td>${esc(m.regime || m.error || "")}</td>
    <td class="${m.fundamental_score > 0.1 ? "up" : m.fundamental_score < -0.1 ? "down" : "flat"}">${fmt(m.fundamental_score, 2)}</td>
    <td class="${m.event_block ? "down" : "muted"}">${m.event_block ? "bloqueio" : m.next_event ? esc(m.next_event.currency + " " + m.next_event.time.slice(11, 16)) : "—"}</td><td>${m.candidates}</td></tr>`).join("");
  $$("#market tr.click").forEach((tr) => (tr.onclick = () => { state.selected = null; loadChart(tr.dataset.s); }));
  const s5 = r.fundamentals?.strength_5d || {};
  const mx = Math.max(0.5, ...Object.values(s5).map(Math.abs));
  $("#strength").innerHTML = `<div class="bars-h">${Object.entries(s5).map(([c, v]) => {
    const w = Math.abs(v) / mx * 50; const left = v >= 0 ? 50 : 50 - w;
    return `<div class="row"><b>${c}</b><div class="track"><div class="mid"></div><div class="fill" style="left:${left}%;width:${w}%;background:${v >= 0 ? "var(--buy)" : "var(--sell)"}"></div></div><span>${v > 0 ? "+" : ""}${fmt(v, 2)}</span></div>`;
  }).join("")}</div><div class="muted">z-score relativo do retorno de 5 dias (centrado no cruzamento das moedas)</div>`;
  const ev = r.fundamentals?.upcoming_events || [];
  $("#events").innerHTML = ev.length ? `<table><tbody>${ev.map((e) => `<tr><td>${e.time.slice(5, 16).replace("T", " ")}</td><td><b>${e.currency}</b></td><td>${esc(e.title)}</td><td class="${e.impact === "High" ? "down" : "muted"}">${e.impact}</td></tr>`).join("")}</tbody></table>`
    : `<div class="muted">${r.fundamentals?.calendar_ok ? "Sem eventos de impacto nas próximas 36 h." : "Calendário indisponível: " + esc(r.fundamentals?.calendar_error)}</div>`;
}

/* ---------------- gráfico */
$$("#tf-seg button").forEach((b) => (b.onclick = () => { $$("#tf-seg button").forEach((x) => x.classList.toggle("on", x === b)); state.tf = b.dataset.tf; loadChart(state.symbol); }));
function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function ensureChart() {
  if (state.chart || !window.LightweightCharts) return;
  const el = $("#chart");
  state.chart = LightweightCharts.createChart(el, { autoSize: true, layout: { background: { color: css("--surface") }, textColor: css("--text-2") },
    grid: { vertLines: { color: css("--border") }, horzLines: { color: css("--border") } }, timeScale: { timeVisible: true, borderColor: css("--border") },
    rightPriceScale: { borderColor: css("--border") }, crosshair: { mode: 0 } });
  state.series = state.chart.addCandlestickSeries({ upColor: css("--buy"), downColor: css("--sell"), borderVisible: false, wickUpColor: css("--buy"), wickDownColor: css("--sell") });
}
async function loadChart(sym) {
  state.symbol = sym; ensureChart(); if (!state.series) return;
  $("#chart-title").textContent = `${sym} · ${state.tf}`;
  try {
    const d = await api(`/api/v1/chart/${sym}?tf=${state.tf}&bars=200`);
    state.digits[sym] = d.digits;
    state.series.applyOptions({ priceFormat: { type: "price", precision: d.digits, minMove: Math.pow(10, -d.digits) } });
    state.series.setData(d.bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    state.lines.forEach((l) => state.series.removePriceLine(l)); state.lines = [];
    const s = state.selected && state.selected.instrument === sym ? state.selected : null;
    const leg = [];
    if (s) {
      const add = (price, color, title, style) => { state.lines.push(state.series.createPriceLine({ price, color, lineWidth: 2, lineStyle: style, axisLabelVisible: true, title })); leg.push(`<span><i style="background:${color}"></i>${title} ${fmt(price, d.digits)}</span>`); };
      add(s.entry.price, css("--entry"), "Entrada", 0);
      add(s.stop_loss.price, css("--sl"), "Stop", 2);
      s.take_profit.forEach((t, i) => add(t.price, css("--tp"), i ? "TP2" : "TP1", i ? 1 : 0));
    }
    $("#chart-legend").innerHTML = leg.join("") || '<span class="muted">Selecione um sinal ou observação para ver os níveis.</span>';
    state.chart.timeScale().fitContent();
  } catch (e) { $("#chart-legend").textContent = "Gráfico indisponível: " + e.message; }
}

/* ---------------- histórico */
async function loadHistory() {
  try {
    const s = await api("/api/v1/signals?limit=200");
    const st = s.stats; $("#sig-stats").textContent = `${st.total} sinais · ${st.active} ativos · ${st.closed} encerrados · R médio ${fmt(st.avg_r, 2)}`;
    $("#signals tbody").innerHTML = s.items.map((x) => `<tr><td>${x.created_at.slice(0, 16).replace("T", " ")}</td><td><b>${x.symbol}</b></td><td class="${x.direction === "BUY" ? "up" : "down"}">${x.direction}</td>
      <td>${x.entry}</td><td>${x.sl}</td><td>${x.tp1}</td><td>${x.tp2 ?? "—"}</td><td>${esc(x.status)}</td><td>${fmt(x.outcome_r, 2)}</td></tr>`).join("") || `<tr><td colspan=9 class=muted>Nenhum sinal emitido ainda.</td></tr>`;
    const a = await api("/api/v1/analyses?limit=100");
    $("#analyses tbody").innerHTML = a.map((x) => `<tr class="click" data-id="${x.id}"><td>${x.created_at.slice(0, 19).replace("T", " ")}</td><td>${esc(x.status)}</td><td>${x.symbol || "—"}</td><td>${x.direction || "—"}</td><td>${fmt(x.score, 0)}</td><td>${fmt(x.elapsed_ms / 1000, 1)} s</td></tr>`).join("");
    $$("#analyses tr.click").forEach((tr) => (tr.onclick = async () => { renderAnalysis(await api("/api/v1/analyses/" + tr.dataset.id)); $('#tabs button[data-tab="painel"]').click(); }));
    const p = await api("/api/v1/paper/positions");
    $("#paper tbody").innerHTML = p.all.map((x) => `<tr><td>${x.opened_at.slice(0, 16).replace("T", " ")}</td><td>${x.symbol}</td><td>${x.direction > 0 ? "BUY" : "SELL"}</td><td>${x.entry}</td><td>${x.sl}</td><td>${x.tp1}</td><td>${x.status}</td><td>${fmt(x.r ?? x.realized, 2)}</td></tr>`).join("") || `<tr><td colspan=8 class=muted>Sem posições demo.</td></tr>`;
  } catch (e) { console.error(e); }
}

/* ---------------- alertas */
function alertHTML(a) { return `<div class="alert ${a.severity}"><b>${esc(a.kind)}</b> · <span class=muted>${a.ts.slice(0, 19).replace("T", " ")} UTC</span><div>${esc(a.message)}</div></div>`; }
async function loadAlerts() { const a = await api("/api/v1/alerts?limit=200"); $("#alerts").innerHTML = a.map(alertHTML).join("") || "<div class=muted>Sem alertas.</div>"; }
function onAlert(a) {
  const b = $("#alert-badge"); b.textContent = String(+b.textContent + 1); b.classList.remove("hidden");
  if ($("#tab-alertas").classList.contains("on")) $("#alerts").insertAdjacentHTML("afterbegin", alertHTML(a));
  if (window.Notification && Notification.permission === "granted") new Notification("FXIntel — " + a.kind, { body: a.message });
}
$("#btn-notify").onclick = () => window.Notification && Notification.requestPermission();

/* ---------------- modelo e relatório */
async function loadModel() {
  try {
    const m = await api("/api/v1/model"); const o = m.oos_metrics || {}; const h = m.oos_holdout_metrics || {};
    $("#model-card").innerHTML = `<div class="card-h"><h3>Modelo probabilístico</h3><span class="pill ${m.validated ? "ok" : "bad"}">${m.validated ? "validado" : "NÃO validado"}</span></div>
      <div class="metrics">
        <div class="metric"><div class="v">${fmt(o.bss, 4)}</div><div class="l">Brier Skill Score OOS</div></div>
        <div class="metric"><div class="v">${fmt(o.auc, 3)}</div><div class="l">AUC OOS</div></div>
        <div class="metric"><div class="v">${fmt(h.bss, 4)}</div><div class="l">BSS holdout 2026</div></div>
        <div class="metric"><div class="v">${o.n ?? "—"}</div><div class="l">Previsões fora da amostra</div></div>
        <div class="metric"><div class="v">${fmt(m.age_hours, 1)} h</div><div class="l">Idade do modelo</div></div></div>
      <p class="muted">Regra de validação: ${esc(m.validation_rule || "")}. Treinado em ${esc((m.trained_at || "").slice(0, 16))} com ${m.n_train ?? "—"} amostras (${esc((m.data_start || "").slice(0, 10))} a ${esc((m.data_end || "").slice(0, 10))}).</p>
      <h4>Tabela de confiabilidade (OOS)</h4><table><thead><tr><th>Faixa</th><th>n</th><th>p previsto</th><th>Observado</th><th>IC 90%</th></tr></thead><tbody>
      ${(m.calibration_table || []).map((r) => `<tr><td>${r.bin[0]}–${r.bin[1]}</td><td>${r.n}</td><td>${fmt(r.mean_p, 3)}</td><td>${fmt(r.observed, 3)}</td><td>${fmt(r.ci90[0], 3)}–${fmt(r.ci90[1], 3)}</td></tr>`).join("")}</tbody></table>
      <div class="actions" style="margin-top:10px"><button class="ghost" id="btn-train">Retreinar agora</button><span class="muted">${m.training ? "treino em andamento…" : ""}</span></div>`;
    $("#btn-train").onclick = async () => { const x = await api("/api/v1/model/train", { method: "POST" }); alert(x.message); };
    const r = await api("/api/v1/report"); const wf = r.walk_forward[r.primary_model] || {}; const c = wf.completo || {};
    const ps = c.portfolio_selected || {}; const em = ps.equity_metrics || {}; const tm = ps.trade_metrics || {};
    const day = r.generated_at.slice(0, 10);
    $("#report-card").innerHTML = `<div class="card-h"><h3>Backtest walk-forward (fora da amostra, com custos)</h3><span class="muted">${esc(r.generated_at.slice(0, 16))}</span></div>
      <div class="metrics">
        <div class="metric"><div class="v">${tm.n ?? 0}</div><div class="l">Trades selecionados</div></div>
        <div class="metric"><div class="v">${fmt(tm.avg_r, 3)}</div><div class="l">R médio por trade</div></div>
        <div class="metric"><div class="v">${fmt(tm.profit_factor, 2)}</div><div class="l">Profit Factor</div></div>
        <div class="metric"><div class="v">${fmt(em.total_return_pct, 1)}%</div><div class="l">Retorno total</div></div>
        <div class="metric"><div class="v">${fmt(em.max_drawdown_pct, 1)}%</div><div class="l">Drawdown máximo</div></div>
        <div class="metric"><div class="v">${fmt(em.sharpe, 2)}</div><div class="l">Sharpe (diário, anual.)</div></div></div>
      <p><b>${r.model_validated ? "Modelo superou a climatologia fora da amostra." : "Sem vantagem estatística comprovada fora da amostra — o motor bloqueia sinais."}</b>
      Expectativa bruta dos candidatos: ${fmt(r.dataset.all_candidates_gross.avg_r, 3)} R; líquida: ${fmt(r.dataset.all_candidates_net.avg_r, 3)} R.</p>
      <img class="report" src="/reports/img/equity-${day}.png" alt="Curva de capital OOS: selecionados pelo modelo e todos os candidatos">
      <img class="report" src="/reports/img/calibracao-${day}.png" alt="Diagrama de confiabilidade das probabilidades OOS" style="max-width:520px">`;
  } catch (e) { $("#report-card").innerHTML = `<div class=muted>${esc(e.message)}</div>`; }
}

/* ---------------- configurações */
let cfg = null;
async function loadSettings() {
  cfg = await api("/api/v1/settings"); const inst = await api("/api/v1/instruments");
  $("#cfg-universe").innerHTML = inst.map((i) => `<span class="chip ${cfg.universe.includes(i.symbol) ? "on" : ""}" data-s="${i.symbol}">${i.symbol}</span>`).join("");
  $$("#cfg-universe .chip").forEach((c) => (c.onclick = () => c.classList.toggle("on")));
  const f = (path, label, step = "any") => { const v = path.split(".").reduce((o, k) => o[k], cfg); return `<label>${label}<input data-p="${path}" type="number" step="${step}" value="${v}"></label>`; };
  $("#cfg-risk").innerHTML = [f("account.equity", "Capital da conta"), f("risk.risk_per_trade_pct", "Risco por trade (%)"), f("risk.max_daily_loss_pct", "Perda máx. diária (%)"),
    f("risk.max_weekly_loss_pct", "Perda máx. semanal (%)"), f("risk.max_session_loss_pct", "Perda máx. por sessão (%)"), f("risk.max_open_positions", "Máx. posições abertas", 1),
    f("risk.max_risk_per_currency_pct", "Risco máx. por moeda (%)"), f("risk.correlation_threshold", "Limiar de correlação")].join("");
  $("#cfg-gates").innerHTML = [f("gates.min_ev_r", "EV mínimo (R)"), f("gates.min_rr_net", "R:R líquido mínimo"), f("gates.max_cost_r", "Custo máximo (R)"),
    f("gates.max_spread_to_atr", "Spread máx. / ATR"), f("gates.max_quote_age_s", "Idade máx. da cotação (s)", 1), f("gates.event_blackout_before_min", "Bloqueio antes de evento (min)", 1),
    f("gates.event_blackout_after_min", "Bloqueio após evento (min)", 1), f("gates.signal_validity_min", "Validade do sinal (min)", 1),
    `<label>Exigir modelo validado<select data-p="gates.require_model"><option value="true" ${cfg.gates.require_model ? "selected" : ""}>sim (recomendado)</option><option value="false" ${cfg.gates.require_model ? "" : "selected"}>não (modo pesquisa)</option></select></label>`].join("");
}
$("#btn-save").onclick = async () => {
  const patch = { universe: $$("#cfg-universe .chip.on").map((c) => c.dataset.s) };
  $$("#tab-config [data-p]").forEach((i) => { const [a, b] = i.dataset.p.split("."); patch[a] = patch[a] || {}; patch[a][b] = i.tagName === "SELECT" ? i.value === "true" : Number(i.value); });
  try { await api("/api/v1/settings", { method: "PUT", body: JSON.stringify(patch) }); $("#cfg-msg").textContent = "Salvo."; } catch (e) { $("#cfg-msg").textContent = "Erro: " + e.message; }
};

/* ---------------- sistema */
async function loadSystem() {
  const h = await fetch("/api/v1/health").then((r) => r.json());
  $("#health-card").innerHTML = `<div class="card-h"><h3>Integridade dos serviços</h3><span class="pill ${h.status === "ok" ? "ok" : "warn"}">${h.status}</span></div>
    <div class="metrics"><div class="metric"><div class="v">${Math.round(h.uptime_s / 60)} min</div><div class="l">Uptime</div></div>
    <div class="metric"><div class="v">${h.market_open ? "aberto" : "fechado"}</div><div class="l">Mercado</div></div>
    <div class="metric"><div class="v">${h.database ? "ok" : "falha"}</div><div class="l">Banco de dados</div></div>
    <div class="metric"><div class="v">${h.version}</div><div class="l">Versão</div></div></div>
    <table style="margin-top:10px"><thead><tr><th>Provedor</th><th>Status</th><th>Latência</th><th>Requisições</th><th>Falhas</th><th>Último erro</th></tr></thead><tbody>
    ${h.providers.providers.map((p) => `<tr><td>${p.name}</td><td class="${p.ok ? "up" : "down"}">${p.name === "oanda" && !h.providers.oanda_configured ? "não configurado" : p.ok ? "ok" : "falha"}</td><td>${fmt(p.last_latency_ms, 0)} ms</td><td>${p.requests}</td><td>${p.failures}</td><td class=muted>${esc(p.last_error || "")}</td></tr>`).join("")}</tbody></table>
    <p class="muted">Heartbeats (s): ${esc(JSON.stringify(h.heartbeat_age_s))}</p>`;
  const ev = await api("/api/v1/events?limit=100");
  $("#events-log tbody").innerHTML = ev.map((e) => `<tr><td>${e.ts.slice(0, 19).replace("T", " ")}</td><td>${esc(e.kind)}</td><td style="white-space:normal">${esc(e.message)}</td></tr>`).join("");
}

async function refreshStatus() {
  try {
    const h = await fetch("/api/v1/health").then((r) => r.json());
    pill("#st-market", h.market_open ? "ok" : "warn", h.market_open ? "mercado aberto" : "mercado fechado");
    pill("#st-data", h.status === "ok" ? "ok" : "warn", h.status === "ok" ? "dados ok" : "dados: " + h.degraded.join(","));
    pill("#st-model", h.model.validated ? "ok" : "bad", h.model.available ? (h.model.validated ? "modelo validado" : "modelo não validado") : "sem modelo");
  } catch (e) { pill("#st-data", "bad", "servidor offline"); }
}

async function boot() {
  if (!key) { askKey(); return; }
  try {
    const inst = await api("/api/v1/instruments"); inst.forEach((i) => (state.digits[i.symbol] = i.digits));
    const q = await api("/api/v1/quotes"); renderQuotes(q.data, q.at);
    try { renderAnalysis(await api("/api/v1/analysis/latest")); } catch (e) { loadChart("XAUUSD"); }
    connectWS(); refreshStatus(); setInterval(refreshStatus, 30000);
  } catch (e) { console.error(e); }
}
boot();
