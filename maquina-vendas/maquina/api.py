"""Servidor: painel (PWA), API do app, páginas de captura e webhooks de venda.

Rodar:  uvicorn maquina.api:app --host 0.0.0.0 --port 8000
"""
import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import (afiliados, avisos, campanhas, config, criativos, db, leads, motor,
               paginas, politica, produtos, relogio, trava)

_token = {"valor": ""}


def _carregar_token():
    if config.PAINEL_TOKEN:
        return config.PAINEL_TOKEN
    arquivo = config.DADOS / "painel_token.txt"
    if arquivo.exists():
        return arquivo.read_text().strip()
    if config.MODO == "real":
        raise SystemExit("Defina PAINEL_TOKEN (uma senha longa) antes de usar o modo real.")
    config.DADOS.mkdir(parents=True, exist_ok=True)
    novo = secrets.token_urlsafe(12)
    arquivo.write_text(novo)
    return novo


async def _laco():
    """Faz a máquina andar sozinha."""
    while True:
        await asyncio.sleep(config.SIM_SEGUNDOS_POR_HORA)
        if config.MODO == "simulacao" and db.cfg("sim_auto"):
            try:
                await run_in_threadpool(motor.ciclo, 1)
            except Exception as erro:  # o laço nunca pode morrer
                avisos.diario("Erro no motor", repr(erro))


@asynccontextmanager
async def ciclo_de_vida(app):
    motor.iniciar()
    _token["valor"] = _carregar_token()
    print(f"\n  Máquina de Vendas ({config.MODO})\n  Token do painel: {_token['valor']}\n", flush=True)
    tarefa = asyncio.create_task(_laco())
    yield
    tarefa.cancel()


app = FastAPI(title="Máquina de Vendas", lifespan=ciclo_de_vida, docs_url=None, redoc_url=None)


def autenticar(authorization: str = Header(default="")):
    if not _token["valor"] or not secrets.compare_digest(authorization, f"Bearer {_token['valor']}"):
        raise HTTPException(401, "Token inválido")


# --- Painel -------------------------------------------------------------------

def _aprovacoes():
    saida = []
    for a in db.todos("SELECT * FROM aprovacoes WHERE status = 'pendente' ORDER BY id"):
        a["detalhe"] = json.loads(a["detalhe"] or "{}")
        if a["tipo"] in ("criativo", "campanha"):
            cr = db.um("SELECT * FROM criativos WHERE id = ?", (a["ref_id"],))
            p = produtos.obter(cr["produto_id"])
            cr["avisos"] = json.loads(cr["avisos"] or "[]")
            cr["cta_texto"] = criativos.CTAS.get(cr["cta"], "Saiba mais")
            a["criativo"] = {k: v for k, v in cr.items() if not k.startswith("sim_")}
            a["produto"] = {"nome": p["nome"], "plataforma": p["plataforma"],
                            "comissao": produtos.comissao_valor(p)}
        saida.append(a)
    return saida


def _produtos():
    saida = []
    for p in db.todos("SELECT * FROM produtos ORDER BY CASE status WHEN 'vencedor' THEN 0 WHEN 'testando' THEN 1 "
                      "WHEN 'candidato' THEN 2 ELSE 3 END, pontuacao DESC"):
        s = campanhas.stats(produto_id=p["id"])
        saida.append({"id": p["id"], "nome": p["nome"], "plataforma": p["plataforma"], "status": p["status"],
                      "pontuacao": p["pontuacao"], "preco": p["preco"], "comissao": produtos.comissao_valor(p),
                      "gasto": s["gasto"], "vendas": s["vendas"], "lucro": s["lucro"], "roas": s["roas"]})
    return saida


@app.get("/api/painel", dependencies=[Depends(autenticar)])
def painel():
    hoje = relogio.hoje()
    dias = []
    for i in range(6, -1, -1):
        dia = relogio.dia_menos(i)
        dias.append({"dia": dia, **campanhas.stats(dia=dia)})
    return {
        "modo": config.MODO,
        "agora": relogio.agora_iso(),
        "pausado": bool(db.cfg("pausado")),
        "autonomia": db.cfg("autonomia"),
        "teto": trava.teto(),
        "teto_absoluto": config.TETO_ABSOLUTO,
        "gasto_hoje": round(trava.gasto_hoje(), 2),
        "comprometido": round(trava.comprometido(), 2),
        "notificar_vendas": bool(db.cfg("notificar_vendas", True)),
        "sim_auto": bool(db.cfg("sim_auto")),
        "ia": criativos.ia_disponivel(),
        "telegram": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
        "hoje": campanhas.stats(dia=hoje),
        "total": campanhas.stats(),
        "dias": dias,
        "campanhas": campanhas.listar()[:60],
        "aprovacoes": _aprovacoes(),
        "alertas": db.todos("SELECT * FROM alertas ORDER BY id DESC LIMIT 30"),
        "leads": leads.contagens(),
        "quentes": leads.listar("quente", 20),
        "produtos": _produtos(),
    }


@app.get("/api/diario", dependencies=[Depends(autenticar)])
def diario(limite: int = 150):
    return db.todos("SELECT * FROM diario ORDER BY id DESC LIMIT ?", (max(1, min(limite, 1000)),))


@app.get("/api/leads", dependencies=[Depends(autenticar)])
def listar_leads(filtro: Optional[str] = None):
    if filtro not in (None, "", "quente", "morno", "frio", "cliente"):
        raise HTTPException(400, "Filtro inválido")
    return leads.listar(filtro or None, 300)


@app.delete("/api/leads/{lead_id}", dependencies=[Depends(autenticar)])
def apagar_lead(lead_id: int):
    leads.apagar(lead_id)
    return {"ok": True}


class Decisao(BaseModel):
    aprovar: bool


@app.post("/api/aprovacoes/{aprovacao_id}", dependencies=[Depends(autenticar)])
def decidir(aprovacao_id: int, decisao: Decisao):
    try:
        return {"ok": True, "resultado": motor.decidir(aprovacao_id, decisao.aprovar)}
    except ValueError as erro:
        raise HTTPException(409, str(erro))


@app.post("/api/pausar", dependencies=[Depends(autenticar)])
def pausar():
    with db.transacao():
        campanhas.pausar_tudo()
    return {"ok": True}


@app.post("/api/retomar", dependencies=[Depends(autenticar)])
def retomar():
    with db.transacao():
        campanhas.retomar()
        motor.otimizador.executar()
    return {"ok": True}


class Ajustes(BaseModel):
    teto_diario: Optional[float] = None
    autonomia: Optional[str] = None
    notificar_vendas: Optional[bool] = None
    sim_auto: Optional[bool] = None


@app.post("/api/ajustes", dependencies=[Depends(autenticar)])
def ajustar(a: Ajustes):
    try:
        motor.ajustar(a.teto_diario, a.autonomia, a.notificar_vendas, a.sim_auto)
    except ValueError as erro:
        raise HTTPException(400, str(erro))
    return {"ok": True}


class NovoProduto(BaseModel):
    plataforma: str
    nome: str = Field(min_length=3, max_length=120)
    preco: float
    comissao_pct: float
    link_afiliado: str
    pagina_vendas: str = ""
    nicho: str = ""
    beneficio: str = ""
    publico: str = ""
    temperatura: float = 0
    reembolso_pct: float = 0
    id_externo: str = ""


@app.post("/api/produtos", dependencies=[Depends(autenticar)])
def novo_produto(p: NovoProduto):
    try:
        pid = produtos.adicionar(p.model_dump())
    except (ValueError, KeyError) as erro:
        raise HTTPException(400, str(erro))
    return {"ok": True, "id": pid}


class Avanco(BaseModel):
    horas: int = Field(ge=1, le=24 * 30)


@app.post("/api/simulacao/avancar", dependencies=[Depends(autenticar)])
def avancar(a: Avanco):
    if config.MODO != "simulacao":
        raise HTTPException(400, "Só existe no modo simulação")
    motor.ciclo(a.horas)
    return {"ok": True, "agora": relogio.agora_iso()}


@app.post("/api/alertas/lidos", dependencies=[Depends(autenticar)])
def alertas_lidos():
    db.executar("UPDATE alertas SET lido = 1 WHERE lido = 0")
    return {"ok": True}


@app.get("/api/politica", dependencies=[Depends(autenticar)])
def checar_politica(titulo: str = "", texto: str = ""):
    return politica.checar(titulo, texto)


# --- Página de captura (pública) ------------------------------------------------

@app.get("/p/{campanha_id}", response_class=HTMLResponse)
def pagina_captura(campanha_id: int):
    html = paginas.captura(campanha_id)
    if html is None:
        raise HTTPException(404, "Página não encontrada")
    return html


@app.get("/privacidade", response_class=HTMLResponse)
def privacidade():
    return paginas.privacidade()


@app.get("/ir/{campanha_id}")
def ir_para_oferta(campanha_id: int, v: str = ""):
    c = campanhas.obter(campanha_id)
    if not c:
        raise HTTPException(404, "Campanha não encontrada")
    if 8 <= len(v) <= 64:
        leads.evento(v, campanha_id, "clicou_oferta")
    p = produtos.obter(c["produto_id"])
    return RedirectResponse(campanhas.link_rastreado(p["link_afiliado"], campanha_id), status_code=302)


class EventoVisitante(BaseModel):
    v: str = Field(min_length=8, max_length=64)
    c: int
    tipo: str


@app.post("/api/v/evento")
def evento_visitante(e: EventoVisitante):
    if e.tipo not in leads.EVENTOS_PUBLICOS or not campanhas.obter(e.c):
        raise HTTPException(400, "Evento inválido")
    leads.evento(e.v, e.c, e.tipo)
    return {"ok": True}


class CadastroVisitante(BaseModel):
    v: str = Field(min_length=8, max_length=64)
    c: int
    nome: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=120)
    whatsapp: str = Field(default="", max_length=20)
    consentimento: bool = False


@app.post("/api/v/cadastro")
def cadastro_visitante(d: CadastroVisitante):
    if not campanhas.obter(d.c):
        raise HTTPException(400, "Campanha inválida")
    try:
        leads.cadastro(d.v, d.c, d.nome, d.email, d.whatsapp, d.consentimento)
    except ValueError as erro:
        raise HTTPException(400, str(erro))
    return {"ok": True}


# --- Webhooks das plataformas de afiliado ---------------------------------------

def _conferir(token_configurado, valido):
    if token_configurado:
        if not valido:
            raise HTTPException(401, "Assinatura inválida")
    elif config.MODO == "real":
        raise HTTPException(503, "Webhook sem token configurado")


@app.post("/webhooks/hotmart")
async def webhook_hotmart(request: Request):
    _conferir(config.HOTMART_HOTTOK, afiliados.validar_hotmart(request.headers, config.HOTMART_HOTTOK))
    corpo = await request.json()
    return await run_in_threadpool(afiliados.processar, "hotmart", corpo)


@app.post("/webhooks/kiwify")
async def webhook_kiwify(request: Request, signature: str = ""):
    bruto = await request.body()
    _conferir(config.KIWIFY_TOKEN, afiliados.validar_kiwify(bruto, signature, config.KIWIFY_TOKEN))
    corpo = json.loads(bruto or b"{}")
    return await run_in_threadpool(afiliados.processar, "kiwify", corpo)


@app.post("/webhooks/eduzz")
async def webhook_eduzz(request: Request, token: str = ""):
    _conferir(config.EDUZZ_TOKEN, bool(config.EDUZZ_TOKEN) and secrets.compare_digest(token, config.EDUZZ_TOKEN))
    if request.headers.get("content-type", "").startswith("application/json"):
        corpo = await request.json()
    else:
        corpo = dict(await request.form())
    return await run_in_threadpool(afiliados.processar, "eduzz", corpo)


# --- App (PWA) --------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(config.WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(config.WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifesto():
    return FileResponse(config.WEB / "manifest.webmanifest", media_type="application/manifest+json")


app.mount("/static", StaticFiles(directory=config.WEB), name="static")
