"""Failure modes the app meets in the real world: no internet, flaky sources, closed market.
The engine must always answer with valid JSON (never an exception through Chaquopy)."""
import json
from datetime import datetime, timezone

import pytest

from fxengine import app_api
from fxengine.config import Settings
from fxengine.data import fundamentals, swissquote, yahoo
from fxengine.data.http import DataError
from fxengine.data.synthetic import SyntheticProvider
from fxengine.instruments import UNIVERSE


def _down(*a, **k):
    raise DataError("sem conexão (simulado)")


@pytest.fixture
def no_internet(monkeypatch):
    for mod, names in ((yahoo, ["candles"]), (swissquote, ["quote"]),
                       (fundamentals, ["calendar", "policy_rates", "cot", "headlines"])):
        for n in names:
            monkeypatch.setattr(mod, n, _down)


def test_no_internet_gives_a_clear_error_everywhere(tmp_path, no_internet):
    calls = [lambda: app_api.run(str(tmp_path), 10000, 1.0, "all"),
             lambda: app_api.scan_explosions(str(tmp_path)),
             lambda: app_api.analyze_asset(str(tmp_path), "EURUSD"),
             lambda: app_api.scan_breakouts(str(tmp_path))]
    for call in calls:
        d = json.loads(call())
        assert d["ok"] is False and d["error"], d


@pytest.fixture(scope="module")
def synth_h1():
    prov = SyntheticProvider(Settings(offline=True), days=200)
    return {i.yahoo: prov.load_instrument(i, None).frames for i in UNIVERSE.values()}


def test_half_the_sources_failing(tmp_path, monkeypatch, synth_h1):
    """Yahoo works for half of the instruments, quotes and fundamentals are down."""
    ok = {i.yahoo for k, i in enumerate(UNIVERSE.values()) if k % 2 == 0}

    def candles(http, symbol, iv, rng, ttl=0):
        if symbol not in ok:
            raise DataError("HTTP 500 (simulado)")
        tf = {"5m": "M5", "15m": "M15", "1h": "H1"}.get(iv, "H1")
        return synth_h1[symbol][tf].copy(), {}

    monkeypatch.setattr(yahoo, "candles", candles)
    monkeypatch.setattr(swissquote, "quote", _down)
    for n in ("calendar", "policy_rates", "cot", "headlines"):
        monkeypatch.setattr(fundamentals, n, _down)
    d = json.loads(app_api.run(str(tmp_path), 10000, 1.0, "all"))
    assert d["ok"], d.get("error")
    assert 0 < len(d["ranking"]) <= 16
    assert d["data_issues"], "as falhas precisam aparecer para o usuário"
    x = json.loads(app_api.scan_explosions(str(tmp_path)))
    assert x["ok"] and 0 < x["scanned"] <= 16


def test_closed_market_never_recommends(tmp_path, monkeypatch):
    saturday = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)
    orig = SyntheticProvider.__init__

    def init(self, settings, days=365):
        orig(self, settings, days)
        self.now = saturday

    monkeypatch.setattr(SyntheticProvider, "__init__", init)
    d = json.loads(app_api.run(str(tmp_path), 10000, 1.0, "all", offline=True))
    assert d["ok"] and d["decision"]["execute"] is False
    assert not any(o["executable"] for o in d["ranking"])
