import json

import pytest

from fxengine import Engine, Settings
from fxengine.cli import main
from fxengine.report import render_text, to_json


@pytest.fixture(scope="module")
def result():
    return Engine(Settings(offline=True, seed=7)).scan()


def test_scan_ranks_and_plans(result):
    assert len(result.opportunities) == 32
    scores = [o.score for o in result.opportunities]
    assert scores == sorted(scores, reverse=True)
    for o in result.opportunities:
        p = o.plan
        assert 0 <= o.score <= 100
        assert o.grade in ("A+", "A", "B", "C", "D")
        if o.direction == 1:
            assert p.sl < p.entry < p.tp1 <= p.tp2
            assert p.entry == o.ask
        else:
            assert p.tp2 <= p.tp1 < p.entry < p.sl
            assert p.entry == o.bid
        assert p.rr1 >= 1.0 - 1e-9


def test_best_is_executable_and_gates_respected(result):
    if result.best is not None:
        assert result.best.executable and not result.best.gates
        assert result.best.score >= result.settings.min_score
    # synthetic NZD event 25 min ahead must block every NZD instrument
    for o in result.opportunities:
        if "NZD" in o.symbol:
            assert not o.executable
            assert any("evento" in g for g in o.gates)


def test_planted_strength_detected(result):
    ranking = [c for c, _ in result.strength.ranking]
    assert ranking[0] == "AUD" and ranking[-1] == "JPY"


def test_reports_render(result):
    txt = render_text(result, detail=True)
    assert "RANKING" in txt and "FORÇA RELATIVA" in txt
    d = json.loads(to_json(result))
    assert d["ranking"] and "plan" in d["ranking"][0]


def test_cli_offline(capsys):
    assert main(["--offline", "--sem-edge", "-a", "fx", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "FXENGINE" in out


def test_app_api_contract():
    from fxengine import app_api

    calls = []

    class Listener:
        def onProgress(self, pct, msg):  # noqa: N802 - mirrors the Java interface
            calls.append((pct, msg))

    raw = app_api.run("/tmp/fxengine-test-cache", 5000, 0.5, "all", use_edge=False,
                      listener=Listener(), offline=True)
    d = json.loads(raw)
    assert d["ok"] is True
    assert calls[0][0] == 1 and calls[-1] == (100, "Concluído")
    assert all(isinstance(p, int) for p, _ in calls)
    assert d["decision"]["headline"]
    o = d["ranking"][0]
    for key in ("symbol", "side", "grade", "entry", "sl", "tp1", "tp2", "lots", "order_text", "reasons"):
        assert key in o
    assert d["settings"]["risk_pct"] == 0.5
    assert len(d["strength"]) == 8


def test_app_api_reports_errors_as_json():
    from fxengine import app_api

    d = json.loads(app_api.run("/tmp/fxengine-test-cache", assets="NOPE", offline=True))
    assert d["ok"] is False and "NOPE" in d["error"]


def test_scan_asset_and_api_offline(tmp_path):
    from fxengine import app_api

    calls = []

    class Listener:
        def onProgress(self, pct, msg):  # noqa: N802
            calls.append(pct)

    for sym in ("EURJPY", "XAUUSD"):
        d = json.loads(app_api.analyze_asset(str(tmp_path), sym, listener=Listener(), offline=True, use_edge=False))
        assert d["ok"] is True and d["symbol"] == sym
        assert d["decision"]["headline"] and len(d["mtf"]) == 5
        assert d["levels"] and all(lv["side"] in ("resistência", "suporte") for lv in d["levels"])
        assert len(d["chart"]["H1"]["c"]) == 120 and len(d["chart"]["H1"]["t"]) == 120
        assert d["daily"]["adr_pips"] > 0 and set(d["daily"]["pivots"]) == {"R2", "R1", "P", "S1", "S2"}
        assert "opportunity" in d and "breakouts" in d
    assert calls[-1] == 100
    bad = json.loads(app_api.analyze_asset(str(tmp_path), "NOPE", offline=True))
    assert bad["ok"] is False


def test_cli_asset_offline(capsys):
    assert main(["ativo", "-a", "GBPUSD", "--offline", "--sem-edge"]) == 0
    out = capsys.readouterr().out
    assert "GBPUSD" in out and "Níveis" in out
    assert main(["ativo", "-a", "XAUUSD", "--offline", "--sem-edge", "--json", "-"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["ok"] and d["symbol"] == "XAUUSD" and d["is_metal"]
    assert all(h["tone"] in (-1, 0, 1) for h in d["headlines"])
