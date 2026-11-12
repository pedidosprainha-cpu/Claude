from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from fxintel import instruments as I
from fxintel.data.calendar import CalendarProvider
from fxintel.data.hub import DataHub, derive, spot_adjust
from fxintel.data.models import Quote, repair_level_shifts, utcnow
from fxintel.data.oanda import OandaProvider, parse_time
from fxintel.fundamental.events import event_risk

from .conftest import synthetic_bars


def test_oanda_parsing():
    d = {"prices": [{"instrument": "EUR_USD", "time": "2026-11-12T10:00:00.123456789Z",
                     "bids": [{"price": "1.10000"}], "asks": [{"price": "1.10012"}], "tradeable": True}]}
    p = OandaProvider.parse_pricing(d)["EUR_USD"]
    assert p["ask"] > p["bid"] and p["time"].tzinfo is not None
    c = {"candles": [{"time": "2026-11-12T10:00:00.000000000Z", "complete": True, "volume": 10,
                      "bid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
                      "ask": {"o": "1.1002", "h": "1.2002", "l": "1.0002", "c": "1.1502"}}]}
    df = OandaProvider.parse_candles(c)
    assert len(df) == 1 and abs(df["spread"].iloc[0] - 0.0002) < 1e-9
    assert parse_time("2026-01-02T03:04:05Z").hour == 3


def test_calendar_and_blackout():
    now = utcnow()
    soon = (now + timedelta(minutes=20)).astimezone(timezone(timedelta(hours=-5))).isoformat()
    later = (now + timedelta(hours=10)).astimezone(timezone(timedelta(hours=-5))).isoformat()
    ev = CalendarProvider.parse([
        {"title": "CPI m/m", "country": "USD", "date": soon, "impact": "High", "forecast": "", "previous": ""},
        {"title": "Retail Sales", "country": "JPY", "date": later, "impact": "Medium", "forecast": "", "previous": ""},
    ])
    r = event_risk(I.get("EURUSD"), ev, now)
    assert r["blocked"] and "CPI" in r["reason"]
    assert event_risk(I.get("XAUUSD"), ev, now)["blocked"]       # ouro sensível a eventos do USD
    assert not event_risk(I.get("EURGBP"), ev, now)["blocked"]


def test_roll_gap_repair():
    df = synthetic_bars(500, price=50.0, vol=0.002)
    df.loc[df.index[250]:, ["o", "h", "l", "c"]] += 1.0   # salto artificial de rolagem
    fixed, n = repair_level_shifts(df, 3600)
    assert n >= 1
    gap = abs(fixed["o"].iloc[250] - fixed["c"].iloc[249])
    assert gap < 0.2


def test_spot_adjust_metals():
    df = synthetic_bars(100, price=3000.0, vol=0.002)
    adj, info = spot_adjust(I.get("XAUUSD"), df, 3030.0)
    assert abs(adj["c"].iloc[-1] - 3030.0) < 1e-6 and info["method"] == "multiplicativo"
    adj2, info2 = spot_adjust(I.get("XAGUSD"), df / 60, 51.0)
    assert abs(adj2["c"].iloc[-1] - 51.0) < 1e-6 and info2["method"] == "aditivo"


class _Cal(CalendarProvider):
    def events(self, max_age_min: int = 60):
        return []


class FakeHub(DataHub):
    """DataHub sem rede: barras sintéticas e cotações derivadas do último fechamento."""

    def __init__(self, settings):
        super().__init__(settings)
        self.calendar = _Cal()
        end = pd.Timestamp(utcnow()).floor("h")
        self._h1 = {}
        for i, s in enumerate(settings["universe"]):
            inst = I.get(s)
            p0 = {"XAUUSD": 3000.0, "XAGUSD": 50.0}.get(s, 150.0 if inst.quote == "JPY" else 1.1)
            b = synthetic_bars(3000, price=p0, seed=10 + i)
            b.index = pd.date_range(end=end - pd.Timedelta(hours=1), periods=len(b), freq="1h", tz="UTC")
            self._h1[s] = b

    def bars(self, symbol, tf, full=False):
        h1 = self._h1[symbol]
        if tf in ("H4", "D1"):
            return derive(h1, tf)
        if tf == "H1":
            return h1
        n = 1200
        b = synthetic_bars(n, freq="5min" if tf == "M5" else "15min", price=float(h1["c"].iloc[-1]), seed=99)
        b.index = pd.date_range(end=pd.Timestamp(utcnow()).floor("5min") - pd.Timedelta(minutes=15),
                                periods=n, freq="5min" if tf == "M5" else "15min", tz="UTC")
        return b

    def macro_bars(self, name, tf="H1"):
        b = synthetic_bars(3000, price=100.0, seed=hash(name) % 1000)
        b.index = self._h1[self.settings["universe"][0]].index
        return b

    def quotes(self, symbols):
        out = {}
        for s in symbols:
            inst = I.get(s)
            px = float(self._h1[s]["c"].iloc[-1])
            sp = inst.typical_spread
            out[s] = Quote(s, px - sp / 2, px + sp / 2, utcnow(), "fake", "estimated")
        self._last_quotes.update(out)
        return out


@pytest.fixture(scope="module")
def engine():
    from fxintel.config import load_settings
    from fxintel.engine import AnalysisEngine
    from fxintel.storage import Storage
    st = load_settings()
    st = {**st, "universe": ["EURUSD", "USDJPY", "XAUUSD", "GBPUSD"]}
    return AnalysisEngine(st, hub=FakeHub(st), storage=Storage())


def test_engine_end_to_end_offline(engine):
    r = engine.analyze_now()
    assert r["status"] in ("SINAL", "SEM_OPORTUNIDADE")
    assert len(r["market"]) == 4 and all(m.get("error") is None for m in r["market"])
    assert r["model"]["available"] is False                    # sem modelo treinado no ambiente de teste
    if r["status"] == "SEM_OPORTUNIDADE":
        assert r["signal"] is None and r["no_signal_reasons"]
    for c in r["observations"]:
        # sem modelo validado, nenhum candidato pode ser recomendado
        assert any(g["gate"] == "modelo_validado" and not g["passed"] for g in c["gates"])
        for k in ("instrument", "direction", "entry", "stop_loss", "take_profit", "risk_reward", "probability",
                  "confidence", "justification", "invalidation", "validity"):
            assert k in c
    assert engine.storage.latest_analysis()["id"] == r["id"]
    # ranking: até 5 itens, um por instrumento, ordenados pela nota, com status explícito
    rk = r["ranking"]
    assert 1 <= len(rk) <= 5 and [c["rank"] for c in rk] == list(range(1, len(rk) + 1))
    assert all(a["score"] >= b["score"] for a, b in zip(rk, rk[1:]))
    assert len({c["instrument"] for c in rk}) == len(rk)
    assert all(c["status"] in ("SINAL", "ELEGIVEL", "OBSERVACAO", "AGUARDANDO_GATILHO") for c in rk)
    for c in rk:
        if not c["has_setup"]:  # plano sem gatilho nunca é recomendado
            assert c["status"] == "AGUARDANDO_GATILHO" and "setup_ativo" in c["blocked_by"]
            assert c["probability"]["model_p"] is None


def test_api_auth_and_endpoints(engine):
    from fastapi.testclient import TestClient

    import backend.app.main as M
    with TestClient(M.app) as client:
        M.S.engine = engine
        M.S.hub = engine.hub
        h = client.get("/api/v1/health")
        assert h.status_code == 200 and "providers" in h.json()
        # padrão: sem chave de API
        assert h.json()["auth_required"] is False
        assert client.get("/api/v1/settings").status_code == 200
        # chave só é exigida quando FXI_REQUIRE_API_KEY=1
        import os
        os.environ["FXI_REQUIRE_API_KEY"] = "1"
        try:
            assert client.get("/api/v1/settings").status_code == 401
            key = M.S.storage.create_api_key("teste")
            assert client.get("/api/v1/settings", headers={"X-API-Key": key}).status_code == 200
        finally:
            os.environ.pop("FXI_REQUIRE_API_KEY", None)
        hdr = {}
        assert client.get("/api/v1/settings", headers=hdr).json()["risk"]["risk_per_trade_pct"] > 0
        bad = client.put("/api/v1/settings", headers=hdr, json={"risk": {"risk_per_trade_pct": 10}})
        assert bad.status_code == 400
        ok = client.put("/api/v1/settings", headers=hdr, json={"risk": {"risk_per_trade_pct": 0.4}})
        assert ok.status_code == 200 and ok.json()["risk"]["risk_per_trade_pct"] == 0.4
        assert client.put("/api/v1/settings", headers=hdr, json={"universe": ["FOO"]}).status_code == 400
        r = client.post("/api/v1/analyze", headers=hdr)
        assert r.status_code == 200 and r.json()["status"] in ("SINAL", "SEM_OPORTUNIDADE")
        assert client.get("/api/v1/analysis/latest", headers=hdr).status_code == 200
        assert client.get("/api/v1/signals", headers=hdr).status_code == 200
        assert client.get("/api/v1/chart/EURUSD?tf=H1&bars=50", headers=hdr).json()["bars"]
        assert client.get("/api/v1/model", headers=hdr).json()["available"] is False
        assert client.post("/api/v1/broker/oanda/execute", headers=hdr,
                           json={"signal_id": "x", "confirm": True}).status_code == 404


def test_public_quote_parsers():
    from fxintel.data.publicquotes import SwissquoteProvider, TrueFxProvider
    sq = [{"topo": {"platform": "SwissquoteLtd"}, "ts": 1794518719205, "spreadProfilePrices": [
        {"spreadProfile": "premium", "bid": 1.10529, "ask": 1.10544},
        {"spreadProfile": "elite", "bid": 1.10535, "ask": 1.10537}]}]
    q = SwissquoteProvider.parse(sq, "premium")
    assert q["bid"] == 1.10529 and q["ask"] == 1.10544 and q["profile"] == "premium"
    q2 = SwissquoteProvider.parse(sq, "standard")  # perfil ausente -> o de maior spread (conservador)
    assert q2["profile"] == "premium"
    tf = TrueFxProvider.parse("EUR/USD,1794518708567,1.10,535,1.10,539,1.10454,1.11031,1.10925\n"
                              "USD/JPY,1794518708876,159.,864,159.,871,159.300,160.047,159.757")
    assert abs(tf["EURUSD"]["bid"] - 1.10535) < 1e-12 and abs(tf["USDJPY"]["ask"] - 159.871) < 1e-9
