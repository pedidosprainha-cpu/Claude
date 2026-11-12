"""Backend HTTP/WebSocket do FXIntel (FastAPI).

Execução:  python -m fxintel serve   (ou: uvicorn backend.app.main:app)
Autenticação: cabeçalho `X-API-Key` (ou `?api_key=` no WebSocket). Na primeira execução, se
não houver chaves, uma chave administrativa é criada e gravada em var/admin_api_key.txt
(ou definida por FXI_API_KEY). Em produção, publique atrás de HTTPS (ver deploy/Caddyfile).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from fxintel import __version__
from fxintel import instruments as I
from fxintel.config import DATA_DIR, ROOT, load_settings, save_settings
from fxintel.data import market_open, utcnow
from fxintel.engine import AnalysisEngine
from fxintel.execution.broker import OandaBroker
from fxintel.logging_setup import setup_logging
from fxintel.monitor import Monitor
from fxintel.storage import Storage
from fxintel.training import REPORT_JSON

log = logging.getLogger("fxintel.api")
DASHBOARD = ROOT / "dashboard"


class AppState:
    def __init__(self):
        self.settings = load_settings()
        self.storage = Storage()
        self.engine = AnalysisEngine(self.settings, storage=self.storage)
        self.hub = self.engine.hub
        self.monitor = Monitor(self.engine)
        self.started = time.time()
        self.quotes: dict[str, dict] = {}
        self.quotes_at: str | None = None
        self.ws: set[WebSocket] = set()
        self.heartbeat: dict[str, str] = {}
        self.training = False
        self.last_alert_id = 0
        self.tasks: list[asyncio.Task] = []
        self.auth_fail: dict[str, list[float]] = {}


S: AppState | None = None


def bootstrap_key(st: Storage) -> None:
    env_key = os.environ.get("FXI_API_KEY")
    if env_key:
        from fxintel.storage import hash_key, now_iso
        if not st.check_api_key(env_key):
            with st.tx() as c:
                c.execute("INSERT OR IGNORE INTO api_keys (name, key_hash, created_at) VALUES (?,?,?)",
                          ("env", hash_key(env_key), now_iso()))
        return
    if not st.has_api_keys():
        key = st.create_api_key("admin")
        p = DATA_DIR / "admin_api_key.txt"
        p.write_text(key + "\n", encoding="utf-8")
        os.chmod(p, 0o600)
        print(f"\n[FXIntel] Chave de API administrativa criada e salva em {p}\n")


async def broadcast(msg: dict) -> None:
    dead = []
    data = json.dumps(msg, ensure_ascii=False, default=str)
    for ws in list(S.ws):
        try:
            await ws.send_text(data)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        S.ws.discard(ws)


async def quotes_loop():
    while True:
        try:
            qs = await run_in_threadpool(S.hub.quotes, S.settings["universe"])
            S.quotes = {s: q.to_dict(I.get(s).pip) for s, q in qs.items()}
            S.quotes_at = utcnow().isoformat()
            evs = await run_in_threadpool(S.engine.broker.update, qs)
            S.heartbeat["quotes"] = S.quotes_at
            await broadcast({"type": "quotes", "at": S.quotes_at, "data": S.quotes})
            for e in evs:
                S.storage.add_alert("demo", "info", f"Posição demo {e['symbol']}: {e['event']} "
                                    f"(R realizado {e['realized_r']:+.2f})", e["symbol"], e,
                                    dedup=f"paper:{e['position_id']}:{e['event']}")
        except Exception as exc:  # noqa: BLE001
            log.warning("quotes_loop: %s", exc)
        await asyncio.sleep(max(3, S.settings["server"]["quote_refresh_s"]))


async def monitor_loop():
    await asyncio.sleep(15)
    while True:
        try:
            await run_in_threadpool(S.monitor.track_signals)
            await run_in_threadpool(S.monitor.check_alerts)
            new = S.storage.alerts(since_id=S.last_alert_id, limit=50)
            if new:
                S.last_alert_id = max(a["id"] for a in new)
                for a in reversed(new):
                    await broadcast({"type": "alert", "data": a})
            S.heartbeat["monitor"] = utcnow().isoformat()
        except Exception as exc:  # noqa: BLE001
            log.warning("monitor_loop: %s", exc)
        await asyncio.sleep(S.settings["alerts"]["check_interval_s"])


async def maintenance_loop():
    """Pré-aquecimento horário dos quadros técnicos, análise automática opcional e retreino."""
    await asyncio.sleep(5)
    last_warm_hour = None
    last_auto = 0.0
    while True:
        try:
            now = utcnow()
            if market_open(now) and now.hour != last_warm_hour and now.minute >= 1 and not S.engine.busy:
                await run_in_threadpool(S.engine.analyze_now, False, "aquecimento")
                last_warm_hour = now.hour
            every = S.settings["server"].get("auto_analyze_min", 0)
            if every and time.time() - last_auto >= every * 60 and market_open(now) and not S.engine.busy:
                res = await run_in_threadpool(S.engine.analyze_now, True, "automática")
                last_auto = time.time()
                await broadcast({"type": "analysis", "data": {"id": res["id"], "status": res["status"],
                                                              "headline": res["headline"]}})
            ms = S.engine.model_status()
            auto = os.environ.get("FXI_AUTO_RETRAIN", "1") != "0"
            if auto and not S.training and (not ms["available"] or ms["age_hours"] > S.settings["model"]["retrain_hours"]):
                threading.Thread(target=_train_thread, daemon=True).start()
            S.heartbeat["maintenance"] = utcnow().isoformat()
        except Exception as exc:  # noqa: BLE001
            log.warning("maintenance_loop: %s", exc)
        await asyncio.sleep(60)


def _train_thread():
    from fxintel.training import train
    S.training = True
    S.storage.log_event("training", "Retreino do modelo iniciado")
    try:
        rep = train(S.settings, S.hub)
        S.storage.log_event("training", f"Retreino concluído (validado={rep['model_validated']})")
        S.storage.add_alert("modelo", "info", f"Modelo retreinado — validado fora da amostra: "
                            f"{'sim' if rep['model_validated'] else 'não'}", dedup=f"train:{rep['generated_at']}")
    except Exception as exc:  # noqa: BLE001
        log.exception("falha no retreino")
        S.storage.log_event("training", f"Falha no retreino: {exc}", level="ERROR")
    finally:
        S.training = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global S
    setup_logging()
    S = AppState()
    bootstrap_key(S.storage)
    S.storage.log_event("startup", f"Servidor iniciado (v{__version__})")
    if os.environ.get("FXI_DISABLE_BACKGROUND") != "1":
        S.tasks = [asyncio.create_task(quotes_loop()), asyncio.create_task(monitor_loop()),
                   asyncio.create_task(maintenance_loop())]
    yield
    for t in S.tasks:
        t.cancel()


app = FastAPI(title="FXIntel API", version=__version__, lifespan=lifespan,
              description="Motor de inteligência de mercado para Forex e metais preciosos.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("FXI_CORS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


def auth(x_api_key: str | None = Header(default=None), api_key: str | None = Query(default=None)) -> str:
    key = x_api_key or api_key
    if not key or not S.storage.check_api_key(key):
        time.sleep(0.3)  # atraso contra força bruta
        raise HTTPException(status_code=401, detail="Chave de API inválida ou ausente (X-API-Key)")
    return key


# ---------------------------------------------------------------------------- públicos
@app.get("/api/v1/health")
def health():
    now = utcnow()
    hb_age = {k: round((now - datetime.fromisoformat(v)).total_seconds(), 1) for k, v in S.heartbeat.items()}
    db_ok = True
    try:
        S.storage.q("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    ms = S.engine.model_status()
    providers = S.hub.health()
    degraded = [p["name"] for p in providers["providers"]
                if (p["name"] != "oanda" or providers["oanda_configured"]) and not p["ok"]]
    return {
        "status": "ok" if db_ok and not degraded else "degradado",
        "version": __version__, "time": now.isoformat(), "uptime_s": round(time.time() - S.started),
        "market_open": market_open(now), "quotes_at": S.quotes_at, "heartbeat_age_s": hb_age,
        "database": db_ok, "providers": providers, "degraded": degraded,
        "model": {k: ms.get(k) for k in ("available", "validated", "trained_at", "age_hours", "stale")},
        "training": S.training, "analysis_running": S.engine.busy,
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(DASHBOARD / "index.html")


if DASHBOARD.exists():
    app.mount("/static", StaticFiles(directory=DASHBOARD), name="static")
(ROOT / "reports").mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory=ROOT / "reports"), name="reports")


# ---------------------------------------------------------------------------- dados
@app.get("/api/v1/instruments")
def instruments(_: str = Depends(auth)):
    return [{"symbol": i.symbol, "kind": i.kind, "pip": i.pip, "digits": i.digits,
             "contract_size": i.contract_size, "typical_spread_pips": i.typical_spread_pips,
             "enabled": i.symbol in S.settings["universe"], "history_note": i.history_note}
            for i in I.INSTRUMENTS.values()]


@app.get("/api/v1/quotes")
async def quotes(_: str = Depends(auth)):
    if not S.quotes:
        qs = await run_in_threadpool(S.hub.quotes, S.settings["universe"])
        S.quotes = {s: q.to_dict(I.get(s).pip) for s, q in qs.items()}
        S.quotes_at = utcnow().isoformat()
    now = utcnow()
    for q in S.quotes.values():
        q["age_s"] = round((now - datetime.fromisoformat(q["time"])).total_seconds(), 1)
    return {"at": S.quotes_at, "market_open": market_open(now), "data": S.quotes}


@app.get("/api/v1/chart/{symbol}")
async def chart(symbol: str, tf: str = "H1", bars: int = Query(150, ge=20, le=1000), _: str = Depends(auth)):
    symbol = symbol.upper()
    if symbol not in I.INSTRUMENTS or tf not in ("M5", "M15", "H1", "H4", "D1"):
        raise HTTPException(404, "instrumento/timeframe inválido")
    return await run_in_threadpool(S.engine.chart, symbol, tf, bars)


@app.get("/api/v1/calendar")
async def calendar(hours: int = 72, _: str = Depends(auth)):
    try:
        evs = await run_in_threadpool(S.hub.calendar.events)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"calendário indisponível: {exc}") from exc
    now = utcnow()
    return [e.to_dict() for e in evs if (e.time - now).total_seconds() > -3 * 3600
            and (e.time - now).total_seconds() < hours * 3600]


# ---------------------------------------------------------------------------- análise
@app.post("/api/v1/analyze")
async def analyze(_: str = Depends(auth)):
    if S.engine.busy:
        # aguarda a análise em curso (ex.: aquecimento) e então executa
        for _i in range(240):
            await asyncio.sleep(0.5)
            if not S.engine.busy:
                break
    try:
        res = await run_in_threadpool(S.engine.analyze_now, True, "manual")
    except Exception as exc:  # noqa: BLE001
        log.exception("falha na análise")
        S.storage.log_event("analysis_error", str(exc), level="ERROR")
        raise HTTPException(500, f"falha na análise: {exc}") from exc
    await broadcast({"type": "analysis", "data": {"id": res["id"], "status": res["status"],
                                                  "headline": res["headline"]}})
    return res


@app.get("/api/v1/analysis/latest")
def latest(_: str = Depends(auth)):
    r = S.storage.latest_analysis()
    if not r:
        raise HTTPException(404, "nenhuma análise ainda")
    return r


@app.get("/api/v1/analyses")
def analyses(limit: int = Query(50, le=500), _: str = Depends(auth)):
    return S.storage.analyses(limit)


@app.get("/api/v1/analyses/{aid}")
def analysis(aid: str, _: str = Depends(auth)):
    r = S.storage.analysis(aid)
    if not r:
        raise HTTPException(404, "análise não encontrada")
    return r


@app.get("/api/v1/instrument/{symbol}")
def instrument_detail(symbol: str, _: str = Depends(auth)):
    d = S.engine.last_details.get(symbol.upper())
    if not d:
        raise HTTPException(404, "execute uma análise primeiro")
    return d


@app.get("/api/v1/signals")
def signals(limit: int = Query(100, le=1000), status: str | None = None, _: str = Depends(auth)):
    return {"stats": S.storage.signal_stats(), "items": S.storage.signals(limit, status)}


@app.get("/api/v1/signals/{sid}")
def signal(sid: str, _: str = Depends(auth)):
    r = S.storage.signal(sid)
    if not r:
        raise HTTPException(404, "sinal não encontrado")
    return r


@app.get("/api/v1/alerts")
def alerts(since_id: int = 0, limit: int = Query(100, le=500), _: str = Depends(auth)):
    return S.storage.alerts(since_id, limit)


@app.get("/api/v1/events")
def events(limit: int = Query(100, le=1000), _: str = Depends(auth)):
    return S.storage.events(limit)


# ---------------------------------------------------------------------------- modelo e relatório
@app.get("/api/v1/model")
def model(_: str = Depends(auth)):
    return S.engine.model_status() | {"training": S.training}


@app.post("/api/v1/model/train")
def model_train(_: str = Depends(auth)):
    if S.training:
        return {"started": False, "message": "treino já em andamento"}
    threading.Thread(target=_train_thread, daemon=True).start()
    return {"started": True, "message": "treino iniciado em segundo plano (alguns minutos)"}


@app.get("/api/v1/report")
def report(_: str = Depends(auth)):
    if not REPORT_JSON.exists():
        raise HTTPException(404, "relatório ainda não gerado")
    return JSONResponse(json.loads(REPORT_JSON.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------- configurações
EDITABLE = {"universe", "account", "risk", "gates", "alerts", "server", "spread_overrides_pips", "slippage",
            "scoring_weights"}


@app.get("/api/v1/settings")
def get_settings(_: str = Depends(auth)):
    return S.settings


@app.put("/api/v1/settings")
def put_settings(patch: dict[str, Any] = Body(...), _: str = Depends(auth)):
    bad = set(patch) - EDITABLE
    if bad:
        raise HTTPException(400, f"chaves não editáveis: {sorted(bad)}")
    if "universe" in patch:
        u = [s.upper() for s in patch["universe"]]
        unknown = [s for s in u if s not in I.INSTRUMENTS]
        if unknown or not u:
            raise HTTPException(400, f"instrumentos inválidos: {unknown}")
        patch["universe"] = u
    if "risk" in patch:
        rp = patch["risk"].get("risk_per_trade_pct")
        if rp is not None and not (0 < float(rp) <= 2.0):
            raise HTTPException(400, "risk_per_trade_pct deve estar entre 0 e 2%")
    new = save_settings(patch)
    S.settings.clear()
    S.settings.update(new)
    S.storage.log_event("settings", "Configurações atualizadas", data=patch)
    return new


# ---------------------------------------------------------------------------- execução
@app.get("/api/v1/paper/positions")
def paper_positions(_: str = Depends(auth)):
    return {"open": S.engine.broker.open_positions(), "all": S.engine.broker.all_positions(200)}


@app.post("/api/v1/paper/execute")
def paper_execute(signal_id: str = Body(..., embed=True), _: str = Depends(auth)):
    sig = S.storage.signal(signal_id)
    if not sig:
        raise HTTPException(404, "sinal não encontrado")
    p = sig["payload"]
    if datetime.fromisoformat(p["validity"]["valid_until"]) < datetime.now(timezone.utc):
        raise HTTPException(409, "sinal expirado")
    q = S.hub.quotes([p["instrument"]]).get(p["instrument"])
    sz = (p.get("risk") or {}).get("sizing") or {}
    d = 1 if p["direction"] == "BUY" else -1
    res = S.engine.broker.place_market_order(p["instrument"], d, sz.get("units", 0), p["stop_loss"]["price"],
                                             p["take_profit"][0]["price"], signal_id, quote=q,
                                             tp2=p["take_profit"][1]["price"], risk_amount=sz.get("risk_amount"))
    if not res.ok:
        raise HTTPException(409, res.message)
    return res.__dict__


@app.post("/api/v1/broker/oanda/execute")
def oanda_execute(signal_id: str = Body(...), confirm: bool = Body(False), _: str = Depends(auth)):
    sig = S.storage.signal(signal_id)
    if not sig:
        raise HTTPException(404, "sinal não encontrado")
    p = sig["payload"]
    sz = (p.get("risk") or {}).get("sizing") or {}
    res = OandaBroker().place_market_order(p["instrument"], 1 if p["direction"] == "BUY" else -1,
                                           sz.get("units", 0), p["stop_loss"]["price"],
                                           p["take_profit"][0]["price"], signal_id, confirm=confirm)
    S.storage.log_event("broker_order", res.message, data={"signal_id": signal_id, "ok": res.ok})
    return {k: v for k, v in res.__dict__.items() if k != "raw"}


# ---------------------------------------------------------------------------- chaves
@app.get("/api/v1/keys")
def keys(_: str = Depends(auth)):
    return S.storage.list_api_keys()


@app.post("/api/v1/keys")
def new_key(name: str = Body("dispositivo", embed=True), _: str = Depends(auth)):
    return {"name": name, "api_key": S.storage.create_api_key(name),
            "note": "Guarde esta chave: ela não será exibida novamente."}


@app.delete("/api/v1/keys/{kid}")
def revoke(kid: int, _: str = Depends(auth)):
    S.storage.revoke_api_key(kid)
    return {"revoked": kid}


# ---------------------------------------------------------------------------- websocket
@app.websocket("/api/v1/ws")
async def ws_endpoint(ws: WebSocket, api_key: str = Query(default="")):
    if not S.storage.check_api_key(api_key):
        await ws.close(code=4401)
        return
    await ws.accept()
    S.ws.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "version": __version__, "quotes": S.quotes,
                                       "at": S.quotes_at}, default=str))
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text(json.dumps({"type": "pong", "at": utcnow().isoformat()}))
    except WebSocketDisconnect:
        pass
    finally:
        S.ws.discard(ws)
