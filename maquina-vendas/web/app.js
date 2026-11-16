"use strict";

/* ---------- utilidades ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const brl = (v) => (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const pct = (v) => ((v ?? 0) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";
const dec = (v) => (v ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const brlCurto = (v) => (Math.abs(v ?? 0) >= 100
  ? (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })
  : brl(v));
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
const quando = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}` : "");
const diaCurto = (dia) => `${dia.slice(8, 10)}/${dia.slice(5, 7)}`;
const sinal = (v) => (v > 0 ? "positivo" : v < 0 ? "negativo" : "");

const lerLocal = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const gravarLocal = (k, v) => { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* sem armazenamento */ } };

const AUTONOMIAS = {
  limites: ["Automática com limites", "Cria, pausa e escala sozinha dentro do teto. Chama você para aprovar anúncio novo e aumento de teto."],
  total: ["Totalmente automática", "Também publica anúncios novos sozinha (se passarem no pente-fino de política). O teto continua travado."],
  manual: ["Eu aprovo cada campanha", "A máquina prepara tudo e você toca em publicar."],
};
const STATUS_CAMP = { ativa: "No ar", pausada: "Pausada", pausada_teto: "Teto do dia", pausada_geral: "Pausa geral", criando: "Criando" };
const STATUS_PROD = { candidato: "Na fila", testando: "Testando", vencedor: "Lucrativo", reprovado: "Reprovado" };

const estado = {
  token: lerLocal("mv_token"),
  aba: "inicio",
  dados: null,
  filtroCamp: "ativas",
  filtroLeads: "quente",
  leads: null,
  diario: null,
  ultimoAlerta: Number(lerLocal("mv_ultimo_alerta") || 0),
  ultimasAprovacoes: null,
};

/* ---------- comunicação com o servidor ---------- */
async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, {
    ...opcoes,
    headers: { Authorization: "Bearer " + estado.token, "Content-Type": "application/json" },
  });
  if (r.status === 401) { sair(); throw new Error("Token inválido"); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || `Erro ${r.status}`);
  return d;
}
const post = (caminho, corpo) => api(caminho, { method: "POST", body: JSON.stringify(corpo || {}) });

let timerAviso;
function avisoRapido(texto) {
  const el = $("#aviso-rapido");
  el.textContent = texto;
  el.classList.add("visivel");
  clearTimeout(timerAviso);
  timerAviso = setTimeout(() => el.classList.remove("visivel"), 2600);
}

async function atualizar(forcar = false) {
  if (!estado.token) return;
  try {
    estado.dados = await api("/api/painel");
    if (estado.aba === "leads") estado.leads = await api(`/api/leads?filtro=${filtroLeadsApi()}`);
    renderTopo();
    // Na aba "Mais" há formulários: só redesenha quando pedido, para não apagar o que você digita.
    if (forcar || estado.aba !== "mais") renderTela();
    notificarNovidades();
  } catch (e) {
    if (estado.token) avisoRapido(e.message);
  }
}

/* ---------- topo e abas ---------- */
function renderTopo() {
  const d = estado.dados;
  const pil = $("#pilula-modo");
  pil.className = "pilula " + (d.modo === "simulacao" ? "sim" : "real");
  pil.textContent = d.modo === "simulacao" ? "Simulação" : "Dinheiro real";
  $("#topo-sub").textContent = d.modo === "simulacao" ? `Relógio simulado: ${quando(d.agora)}` : `Atualizado ${quando(d.agora)}`;
  const selo = $("#selo-aprovar");
  selo.hidden = !d.aprovacoes.length;
  selo.textContent = d.aprovacoes.length;
}

function trocarAba(aba) {
  estado.aba = aba;
  document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === aba));
  window.scrollTo(0, 0);
  if (aba === "leads") estado.leads = null;
  if (aba === "mais") estado.diario = null;
  renderTela();
  if (aba === "leads") atualizar();
  if (aba === "mais") carregarDiario();
}

function renderTela() {
  if (!estado.dados) return;
  const telas = { inicio: telaInicio, aprovar: telaAprovar, campanhas: telaCampanhas, leads: telaLeads, mais: telaMais };
  $("#tela").innerHTML = telas[estado.aba](estado.dados);
}

/* ---------- Início ---------- */
function telaInicio(d) {
  const noAr = d.campanhas.filter((c) => c.status === "ativa").length;
  const uso = d.teto ? Math.min(100, (d.gasto_hoje / d.teto) * 100) : 0;
  const decisoes = d.aprovacoes.length
    ? `<div class="cartao" style="margin-top:10px;border-color:var(--alerta)">
         <div class="estado"><div><b>${plural(d.aprovacoes.length, "decisão esperando", "decisões esperando")} você</b>
         <div class="suave pequeno">Anúncios novos ou aumento de teto.</div></div>
         <button class="botao primario" data-ir="aprovar">Ver</button></div></div>`
    : "";
  const linhasDias = d.dias.slice().reverse().map((x) => `
      <tr><td>${diaCurto(x.dia)}</td><td>${brl(x.gasto)}</td><td>${x.vendas}</td>
      <td>${brl(x.comissao)}</td><td class="${sinal(x.lucro)}">${brl(x.lucro)}</td></tr>`).join("");
  const alertas = d.alertas.slice(0, 10).map((a) => `
      <li class="alerta-item"><span class="alerta-icone ${esc(a.nivel)}"></span>
      <div style="min-width:0"><div class="alerta-titulo">${esc(a.titulo)}</div>
      ${a.mensagem ? `<div class="suave pequeno">${esc(a.mensagem)}</div>` : ""}
      <div class="suave pequeno">${quando(a.criado_em)}</div></div></li>`).join("");
  return `
    <div class="cartao estado">
      <div>
        <div class="estado-titulo"><span class="ponto ${d.pausado ? "parado" : ""}"></span>${d.pausado ? "Máquina pausada" : "Máquina trabalhando"}</div>
        <div class="suave pequeno">${esc(AUTONOMIAS[d.autonomia][0])} · ${plural(noAr, "campanha", "campanhas")} no ar</div>
      </div>
      ${d.pausado
        ? `<button class="botao primario" data-acao="retomar">Retomar</button>`
        : `<button class="botao perigo" data-acao="pausar">Pausar tudo</button>`}
    </div>
    <div class="cartao" style="margin-top:10px">
      <div class="estado">
        <div><div class="suave pequeno">Gasto hoje</div>
          <div class="kpi"><span class="valor">${brl(d.gasto_hoje)}</span> <span class="suave">de ${brl(d.teto)}</span></div></div>
        <div class="suave pequeno" style="text-align:right">Verba reservada<br><b class="num">${brl(d.comprometido)}</b>/dia</div>
      </div>
      <div class="barra ${uso >= 99 ? "cheia" : ""}"><div style="width:${uso}%"></div></div>
    </div>
    <div class="grade">
      <div class="cartao kpi"><div class="rotulo">Comissão hoje</div><div class="valor">${brl(d.hoje.comissao)}</div><div class="suave pequeno">${plural(d.hoje.vendas, "venda", "vendas")}</div></div>
      <div class="cartao kpi"><div class="rotulo">Lucro hoje</div><div class="valor ${sinal(d.hoje.lucro)}">${brl(d.hoje.lucro)}</div><div class="suave pequeno">comissão − anúncios</div></div>
      <div class="cartao kpi"><div class="rotulo">Lucro acumulado</div><div class="valor ${sinal(d.total.lucro)}">${brl(d.total.lucro)}</div><div class="suave pequeno">${plural(d.total.vendas, "venda", "vendas")} no total</div></div>
      <div class="cartao kpi"><div class="rotulo">Retorno (ROAS)</div><div class="valor">${dec(d.total.roas)}</div><div class="suave pequeno">por R$ 1 em anúncio</div></div>
    </div>
    ${decisoes}
    <h2>Últimos 7 dias</h2>
    <div class="cartao"><table>
      <thead><tr><th>Dia</th><th>Gasto</th><th>Vendas</th><th>Comissão</th><th>Lucro</th></tr></thead>
      <tbody>${linhasDias}</tbody></table></div>
    <h2>Avisos</h2>
    <div class="cartao">${alertas ? `<ul class="lista">${alertas}</ul>` : `<p class="suave">Nenhum aviso ainda.</p>`}</div>`;
}

/* ---------- Aprovar ---------- */
function previaAnuncio(cr) {
  return `
    <div class="anuncio" aria-label="Prévia do anúncio">
      <div class="anuncio-topo"><div class="anuncio-avatar"></div>
        <div><div class="anuncio-pagina">Sua página</div><div class="anuncio-pat">Patrocinado</div></div></div>
      <div class="anuncio-texto">${esc(cr.texto)}</div>
      <div class="anuncio-imagem">${esc(cr.titulo)}</div>
      <div class="anuncio-rodape">
        <div style="min-width:0"><div class="tit">${esc(cr.titulo)}</div><div class="desc">${esc(cr.descricao || "")}</div></div>
        <span class="anuncio-cta">${esc(cr.cta_texto)}</span></div>
    </div>`;
}

function telaAprovar(d) {
  if (!d.aprovacoes.length) {
    return `<div class="vazio"><b>Nada esperando por você</b>A máquina só chama aqui quando precisa de uma decisão sua.</div>`;
  }
  return `<p class="suave pequeno">A máquina já fez o trabalho. Aqui você só decide.</p>` + d.aprovacoes.map((a) => {
    const botoes = (nao, sim) => `<div class="botoes">
        <button class="botao" data-decidir="${a.id}" data-aprovar="0">${nao}</button>
        <button class="botao primario" data-decidir="${a.id}" data-aprovar="1">${sim}</button></div>`;
    if (a.tipo === "criativo" || a.tipo === "campanha") {
      const cr = a.criativo;
      const avisos = (cr.avisos || []).map((x) => `<div class="aviso-politica">${esc(x.motivo)}${x.trecho ? `: “${esc(x.trecho)}”` : ""}</div>`).join("");
      return `<div class="cartao">
          <div class="camp-topo"><div style="min-width:0">
            <div class="camp-nome">${a.tipo === "criativo" ? "Anúncio novo" : "Publicar campanha"}</div>
            <div class="suave pequeno">${esc(a.produto.nome)} · ${esc(a.produto.plataforma)} · comissão ${brl(a.produto.comissao)}</div></div>
            <span class="st st-candidato">${esc(cr.angulo || "")}</span></div>
          ${previaAnuncio(cr)}
          <p class="suave pequeno" style="margin:8px 0 0">${cr.origem === "ia" ? "Escrito pelo Claude" : "Modelo pronto"} · passou no pente-fino de política${avisos ? " com observações:" : ""}</p>
          ${avisos}
          ${a.tipo === "criativo" ? botoes("Rejeitar", "Aprovar") : botoes("Não publicar", `Publicar (${brl(a.detalhe.orcamento)}/dia)`)}
        </div>`;
    }
    if (a.tipo === "aumento_teto") {
      const x = a.detalhe;
      return `<div class="cartao">
          <div class="camp-nome">${esc(a.titulo)}</div>
          <p class="suave" style="margin-top:6px">A campanha #${x.campanha_id} de <b>${esc(x.produto)}</b> está dando lucro:
          ROAS ${dec(x.roas)}, ${plural(x.vendas, "venda", "vendas")} e ${brl(x.lucro)} de lucro no período recente. Ela quer mais verba, mas o teto atual não deixa.</p>
          <p class="suave pequeno">Limite máximo do servidor: ${brl(d.teto_absoluto)}/dia.</p>
          ${botoes("Agora não", "Liberar")}
        </div>`;
    }
    return "";
  }).join("");
}

/* ---------- Campanhas ---------- */
function telaCampanhas(d) {
  const lista = estado.filtroCamp === "ativas" ? d.campanhas.filter((c) => c.status === "ativa") : d.campanhas;
  const chips = `<div class="chips">
      <button class="chip ${estado.filtroCamp === "ativas" ? "ativo" : ""}" data-filtro-camp="ativas">No ar</button>
      <button class="chip ${estado.filtroCamp === "todas" ? "ativo" : ""}" data-filtro-camp="todas">Todas</button></div>`;
  if (!lista.length) {
    return chips + `<div class="vazio"><b>Nenhuma campanha ${estado.filtroCamp === "ativas" ? "no ar" : "ainda"}</b>
      ${d.aprovacoes.length ? "Aprove os anúncios na aba Aprovar para a máquina publicar." : "A máquina cria campanhas quando há verba livre no teto."}</div>`;
  }
  return chips + lista.map((c) => {
    const s = c.stats;
    return `<div class="cartao">
        <div class="camp-topo"><div style="min-width:0">
          <div class="camp-nome">${esc(c.produto)}</div>
          <div class="suave pequeno">#${c.id} · “${esc(c.titulo)}”</div></div>
          <span class="st st-${esc(c.status)}">${STATUS_CAMP[c.status] || esc(c.status)}</span></div>
        <div class="metricas">
          <div><span>Verba/dia</span><b>${brlCurto(c.orcamento_diario)}</b></div>
          <div><span>Gasto</span><b>${brlCurto(s.gasto)}</b></div>
          <div><span>Vendas</span><b>${s.vendas}</b></div>
          <div><span>Comissão</span><b>${brlCurto(s.comissao)}</b></div>
          <div><span>ROAS</span><b class="${s.gasto ? (s.roas >= 1 ? "positivo" : "negativo") : ""}">${dec(s.roas)}</b></div>
        </div>
        <p class="suave pequeno" style="margin:8px 0 0">${esc(c.motivo || "")} · CTR ${pct(s.ctr)} ·
          <a class="link" href="/p/${c.id}" target="_blank" rel="noopener">ver página</a></p>
      </div>`;
  }).join("");
}

/* ---------- Leads ---------- */
function filtroLeadsApi() { return estado.filtroLeads === "todos" ? "" : estado.filtroLeads; }

function linkWhats(numero) {
  const n = String(numero || "").replace(/\D/g, "");
  return n.length <= 11 ? "55" + n : n;
}

function telaLeads(d) {
  const c = d.leads;
  const chips = [["quente", "Quentes"], ["morno", "Mornos"], ["cliente", "Clientes"], ["todos", "Todos"]]
    .map(([k, r]) => `<button class="chip ${estado.filtroLeads === k ? "ativo" : ""}" data-filtro-leads="${k}">${r}</button>`).join("");
  const lista = estado.leads;
  let corpo;
  if (lista === null) corpo = `<p class="suave">Carregando…</p>`;
  else if (!lista.length) corpo = `<div class="vazio"><b>Nenhum lead aqui ainda</b>Eles aparecem quando alguém deixa o contato na página de captura.</div>`;
  else corpo = `<div class="cartao"><ul class="lista">${lista.map((l) => `
      <li class="lead"><div style="min-width:0">
        <div class="camp-nome">${esc(l.nome || "Sem nome")}</div>
        <div class="suave pequeno">${esc(l.produto || "")}
          ${l.whatsapp ? ` · <a class="link" href="https://wa.me/${linkWhats(l.whatsapp)}" target="_blank" rel="noopener">WhatsApp</a>` : ""}
          ${l.email ? ` · <a class="link" href="mailto:${esc(l.email)}">${esc(l.email)}</a>` : ""}</div>
        <div class="tags">${l.acoes.map((a) => `<span class="tag">${esc(a)}</span>`).join("")}</div></div>
        <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
          <span class="lead-pontos ${l.cliente ? "cliente" : esc(l.temperatura)}">${l.cliente ? "cliente" : l.pontuacao}</span>
          <button class="chip" data-apagar-lead="${l.id}" aria-label="Apagar dados de ${esc(l.nome || "lead")}">Apagar</button></div>
      </li>`).join("")}</ul></div>`;
  return `
    <div class="grade" style="margin-top:0">
      <div class="cartao kpi"><div class="rotulo">Quentes</div><div class="valor">${c.quentes}</div></div>
      <div class="cartao kpi"><div class="rotulo">Mornos</div><div class="valor">${c.mornos}</div></div>
      <div class="cartao kpi"><div class="rotulo">Viraram clientes</div><div class="valor">${c.clientes}</div></div>
      <div class="cartao kpi"><div class="rotulo">Total com contato</div><div class="valor">${c.total}</div></div>
    </div>
    <p class="suave pequeno" style="margin-top:12px">Cada ação na página soma pontos na hora (leu, voltou, clicou na oferta, abandonou o checkout).
      Acima de 60 pontos o lead é quente: está perto de comprar.</p>
    <div class="chips">${chips}</div>${corpo}`;
}

/* ---------- Mais ---------- */
async function carregarDiario() {
  try {
    estado.diario = await api("/api/diario?limite=120");
    if (estado.aba === "mais") renderTela();
  } catch (e) { avisoRapido(e.message); }
}

function telaMais(d) {
  const opcoes = Object.entries(AUTONOMIAS).map(([k, [t, desc]]) => `
      <label class="opcao"><input type="radio" name="autonomia" value="${k}" ${d.autonomia === k ? "checked" : ""}>
      <span><b>${t}</b><span class="suave pequeno">${desc}</span></span></label>`).join("");
  const prods = d.produtos.map((p) => `
      <li><div class="camp-topo"><div style="min-width:0"><div class="camp-nome">${esc(p.nome)}</div>
        <div class="suave pequeno">${esc(p.plataforma)} · nota ${Math.round(p.pontuacao)} · comissão ${brl(p.comissao)}
        ${p.gasto ? ` · gasto ${brl(p.gasto)} · ${plural(p.vendas, "venda", "vendas")} · <span class="${sinal(p.lucro)}">${brl(p.lucro)}</span>` : ""}</div></div>
        <span class="st st-${esc(p.status)}">${STATUS_PROD[p.status] || esc(p.status)}</span></div></li>`).join("");
  const diario = estado.diario === null ? `<p class="suave">Carregando…</p>` : `<ul class="lista">${estado.diario.map((x) => `
      <li class="diario-item"><time>${quando(x.quando)}</time> <b>${esc(x.acao)}</b><div class="suave">${esc(x.detalhe || "")}</div></li>`).join("")}</ul>`;
  const sim = d.modo === "simulacao" ? `
    <h2>Simulação</h2>
    <div class="cartao">
      <p class="suave pequeno">Nada aqui gasta dinheiro de verdade. O tempo corre rápido para você ver semanas de operação em minutos.</p>
      <label class="alternar"><span>Avançar sozinha (1 hora simulada a cada poucos segundos)</span>
        <input type="checkbox" data-ajuste="sim_auto" ${d.sim_auto ? "checked" : ""}></label>
      <div class="botoes"><button class="botao" data-acao="avancar" data-horas="24">+1 dia</button>
        <button class="botao" data-acao="avancar" data-horas="168">+7 dias</button></div>
    </div>` : "";
  return `
    <h2 style="margin-top:4px">Ajustes</h2>
    <div class="cartao">
      <form id="form-teto">
        <label for="teto">Teto de gasto por dia (R$)</label>
        <div class="form-linha"><input id="teto" type="number" min="5" max="${d.teto}" step="1" value="${d.teto}">
          <button class="botao" type="submit">Salvar</button></div>
        <p class="suave pequeno" style="margin-top:6px">Pelo app você só pode reduzir. Para aumentar, a máquina pede sua aprovação quando
          tiver campanha lucrativa. Limite do servidor: ${brl(d.teto_absoluto)}/dia.</p>
      </form>
      <label>Autonomia</label>${opcoes}
      <label class="alternar" style="margin-top:10px"><span>Avisar cada venda no celular</span>
        <input type="checkbox" data-ajuste="notificar_vendas" ${d.notificar_vendas ? "checked" : ""}></label>
      <p class="suave pequeno">Telegram: ${d.telegram ? "conectado" : "não configurado (veja o LEIA-ME)"} ·
        Textos dos anúncios: ${d.ia ? "escritos pelo Claude" : "modelos prontos (sem chave da API da Anthropic)"}</p>
      <button class="botao largo" data-acao="notificacoes">Ativar notificações neste aparelho</button>
    </div>
    ${sim}
    <h2>Produtos</h2>
    <div class="cartao">
      <p class="suave pequeno">Cadastre os produtos em que você já é afiliado. A máquina dá uma nota, testa os melhores e descarta os que não se pagam.</p>
      <ul class="lista">${prods}</ul>
      <details style="margin-top:8px"><summary>Adicionar produto</summary>
        <form id="form-produto">
          <label for="p-plat">Plataforma</label>
          <select id="p-plat" name="plataforma"><option value="hotmart">Hotmart</option><option value="kiwify">Kiwify</option><option value="eduzz">Eduzz</option></select>
          <label for="p-nome">Nome do produto</label><input id="p-nome" name="nome" type="text" required minlength="3">
          <div class="form-linha">
            <div><label for="p-preco">Preço (R$)</label><input id="p-preco" name="preco" type="number" step="0.01" min="1" required></div>
            <div><label for="p-com">Comissão (%)</label><input id="p-com" name="comissao_pct" type="number" step="0.1" min="1" max="100" required></div>
          </div>
          <label for="p-link">Seu link de afiliado</label><input id="p-link" name="link_afiliado" type="url" required placeholder="https://">
          <label for="p-pag">Página de vendas</label><input id="p-pag" name="pagina_vendas" type="url" placeholder="https://">
          <label for="p-ben">O que a pessoa aprende ou consegue fazer</label><input id="p-ben" name="beneficio" type="text">
          <label for="p-pub">Para quem é</label><input id="p-pub" name="publico" type="text">
          <div class="form-linha">
            <div><label for="p-temp">Temperatura (0 a 100)</label><input id="p-temp" name="temperatura" type="number" min="0" max="100" value="50"></div>
            <div><label for="p-reemb">Reembolso (%)</label><input id="p-reemb" name="reembolso_pct" type="number" min="0" max="100" value="0"></div>
          </div>
          <label for="p-id">Código do produto na plataforma (opcional)</label><input id="p-id" name="id_externo" type="text">
          <button class="botao primario largo" type="submit" style="margin-top:12px">Cadastrar</button>
        </form>
      </details>
    </div>
    <h2>Diário de bordo</h2>
    <div class="cartao"><p class="suave pequeno">Tudo o que a máquina fez, em ordem.</p>${diario}</div>
    <button class="botao largo" data-acao="sair" style="margin-top:18px">Sair deste aparelho</button>`;
}

/* ---------- ações ---------- */
async function executar(fn, ok) {
  try { await fn(); if (ok) avisoRapido(ok); await atualizar(true); }
  catch (e) { avisoRapido(e.message); }
}

document.addEventListener("click", async (ev) => {
  const alvo = ev.target.closest("button, [data-ir]");
  if (!alvo) return;
  if (alvo.dataset.aba) return trocarAba(alvo.dataset.aba);
  if (alvo.dataset.ir) return trocarAba(alvo.dataset.ir);
  if (alvo.dataset.filtroCamp) { estado.filtroCamp = alvo.dataset.filtroCamp; return renderTela(); }
  if (alvo.dataset.filtroLeads) { estado.filtroLeads = alvo.dataset.filtroLeads; estado.leads = null; renderTela(); return atualizar(true); }
  if (alvo.dataset.decidir) {
    alvo.disabled = true;
    const aprovar = alvo.dataset.aprovar === "1";
    return executar(async () => {
      const r = await post(`/api/aprovacoes/${alvo.dataset.decidir}`, { aprovar });
      if (r.resultado && r.resultado !== "ok") avisoRapido(r.resultado);
    }, aprovar ? "Aprovado" : "Rejeitado");
  }
  if (alvo.dataset.apagarLead) {
    if (!confirm("Apagar os dados deste lead? Não dá para desfazer.")) return;
    return executar(async () => {
      await api(`/api/leads/${alvo.dataset.apagarLead}`, { method: "DELETE" });
      estado.leads = null;
    }, "Lead apagado");
  }
  switch (alvo.dataset.acao) {
    case "pausar":
      if (confirm("Pausar todas as campanhas agora?")) executar(() => post("/api/pausar"), "Tudo pausado");
      break;
    case "retomar":
      executar(() => post("/api/retomar"), "Máquina retomada");
      break;
    case "avancar":
      alvo.disabled = true;
      executar(async () => { await post("/api/simulacao/avancar", { horas: Number(alvo.dataset.horas) }); estado.diario = null; carregarDiario(); }, "Simulação avançou");
      break;
    case "notificacoes":
      if (!("Notification" in window)) return avisoRapido("Este navegador não tem notificações");
      Notification.requestPermission().then((p) => avisoRapido(p === "granted" ? "Notificações ativadas" : "Notificações recusadas"));
      break;
    case "sair":
      sair();
      break;
  }
});

document.addEventListener("change", (ev) => {
  const el = ev.target;
  if (el.name === "autonomia") executar(() => post("/api/ajustes", { autonomia: el.value }), "Autonomia alterada");
  if (el.dataset.ajuste) executar(() => post("/api/ajustes", { [el.dataset.ajuste]: el.checked }), "Salvo");
});

document.addEventListener("submit", (ev) => {
  if (ev.target.id === "form-teto") {
    ev.preventDefault();
    executar(() => post("/api/ajustes", { teto_diario: Number($("#teto").value) }), "Teto salvo");
  }
  if (ev.target.id === "form-produto") {
    ev.preventDefault();
    const dados = Object.fromEntries(new FormData(ev.target).entries());
    ["preco", "comissao_pct", "temperatura", "reembolso_pct"].forEach((k) => { dados[k] = Number(dados[k] || 0); });
    executar(() => post("/api/produtos", dados), "Produto cadastrado");
  }
  if (ev.target.id === "form-entrar") {
    ev.preventDefault();
    estado.token = $("#token").value.trim();
    entrar();
  }
});

/* ---------- notificações (com o app aberto ou em segundo plano) ---------- */
function notificarNovidades() {
  const d = estado.dados;
  const novos = d.alertas.filter((a) => a.id > estado.ultimoAlerta && (a.nivel === "urgente" || a.titulo.startsWith("Venda")));
  const maior = d.alertas.reduce((m, a) => Math.max(m, a.id), estado.ultimoAlerta);
  const aprov = d.aprovacoes.length;
  const aumentouAprov = estado.ultimasAprovacoes !== null && aprov > estado.ultimasAprovacoes;
  estado.ultimasAprovacoes = aprov;
  if (maior !== estado.ultimoAlerta) { estado.ultimoAlerta = maior; gravarLocal("mv_ultimo_alerta", String(maior)); }
  if (!document.hidden || !("Notification" in window) || Notification.permission !== "granted" || !navigator.serviceWorker) return;
  const mensagens = novos.slice(0, 3).map((a) => [a.titulo, a.mensagem || ""]);
  if (aumentouAprov) mensagens.push(["Preciso da sua decisão", `${aprov} item(ns) na aba Aprovar`]);
  navigator.serviceWorker.ready.then((reg) => mensagens.forEach(([t, m]) => reg.showNotification(t, { body: m, icon: "/static/icone-192.png", tag: t })));
}

/* ---------- entrada ---------- */
async function entrar() {
  $("#erro-entrar").textContent = "";
  try {
    estado.dados = await api("/api/painel");
    gravarLocal("mv_token", estado.token);
    $("#entrar").hidden = true;
    $("#app").hidden = false;
    renderTopo();
    renderTela();
    estado.ultimasAprovacoes = estado.dados.aprovacoes.length;
  } catch (e) {
    $("#entrar").hidden = false;
    $("#app").hidden = true;
    $("#erro-entrar").textContent = e.message;
  }
}

function sair() {
  estado.token = null;
  gravarLocal("mv_token", null);
  $("#app").hidden = true;
  $("#entrar").hidden = false;
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
if (estado.token) entrar(); else $("#entrar").hidden = false;
setInterval(() => { if (estado.token && !$("#app").hidden) atualizar(); }, 4000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) atualizar(); });
