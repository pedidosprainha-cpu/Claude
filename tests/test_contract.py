"""Contract between the Android app (Kotlin) and the engine (Python).

The app calls fxengine.app_api through Chaquopy with positional arguments
(android/.../engine/EngineRunner.kt) and reads the JSON with explicit keys
(android/.../data/*Models.kt). These tests call the engine exactly as the app does and check
that every key the app reads exists in the real output - a renamed field would otherwise
only show up as an empty screen on the phone."""
import json
import os
import re

import pytest

from fxengine import app_api

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "fxengine", "app")


class Listener:
    def __init__(self):
        self.calls = 0

    def onProgress(self, pct, msg):  # noqa: N802 - Kotlin interface name
        assert 0 <= pct <= 100 and isinstance(msg, str)
        self.calls += 1


def kotlin_calls() -> dict[str, list[str]]:
    src = open(os.path.join(KT, "engine", "EngineRunner.kt"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'callAttr\(\s*"(\w+)",(.*?)\)\.toString\(\)', src, re.S):
        args = [a.strip() for a in re.split(r",\s*\n|,(?![^(]*\))", m.group(2)) if a.strip()]
        out[m.group(1)] = args
    return out


def python_value(expr: str, tmp: str, listener: Listener):
    table = {"cacheDir()": tmp, "settings.balance": 10_000.0, "settings.riskPct": 1.0, "settings.assets": "all",
             "TZ": "America/Sao_Paulo", "settings.useEdge": True, "settings.useNews": True,
             "settings.breakoutPlan": "mercado", "symbol": "EURUSD", "false": True}   # offline in tests
    if expr.startswith("LambdaProgressListener"):
        return listener
    assert expr in table, f"argumento Kotlin sem mapeamento no teste: {expr}"
    return table[expr]


def keys_read(file: str) -> set[str]:
    src = open(os.path.join(KT, "data", file), encoding="utf-8").read()
    pat = r'\.(?:s|d|xs|xd|xdn|jd|js|tn|optString|optInt|optDouble|optBoolean|optJSONObject|optJSONArray|isNull|has)\("([a-z0-9_]+)"'
    return set(re.findall(pat, src))


def all_keys(obj, acc=None) -> set[str]:
    acc = set() if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            all_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            all_keys(v, acc)
    return acc


OPTIONAL = {"error", "detail", "available"}       # failure envelope / feature switches


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    tmp = str(tmp_path_factory.mktemp("contract"))
    out = {}
    for fn, args in kotlin_calls().items():
        listener = Listener()
        vals = [python_value(a, tmp, listener) for a in args]
        raw = getattr(app_api, fn)(*vals)
        d = json.loads(raw)
        assert d.get("ok"), (fn, d.get("error"), d.get("detail", "")[-800:])
        out[fn] = (d, listener.calls)
    return out


def test_every_kotlin_call_exists_and_runs(outputs):
    assert set(outputs) >= {"run", "scan_breakouts", "analyze_asset", "scan_explosions"}
    for fn, (_, progress_calls) in outputs.items():
        assert progress_calls > 0, f"{fn}: o app não receberia progresso"


@pytest.mark.parametrize("fn,files", [
    ("run", ["Models.kt", "TrackModels.kt"]),
    ("analyze_asset", ["AssetModels.kt"]),
    ("scan_explosions", ["ExplosionModels.kt", "TrackModels.kt"]),
    ("scan_breakouts", ["BreakoutModels.kt"]),
])
def test_every_key_the_app_reads_exists(outputs, fn, files):
    present = all_keys(outputs[fn][0])
    wanted = set().union(*(keys_read(f) for f in files)) - OPTIONAL
    shared = {"Models.kt": keys_read("Models.kt")}
    if fn != "run":       # other parsers reuse parseOpp/parseItem from Models.kt / BreakoutModels.kt
        wanted -= shared["Models.kt"] - all_keys(outputs["run"][0])
    missing = sorted(k for k in wanted if k not in present)
    # keys that only appear when a feature is active in live data (e.g. fills of limit orders)
    allowed_absent = {"fills", "confirmations", "first_seen", "hist", "fill_price", "filled_at", "valid_until",
                      "headline_tone", "edge", "explosion", "signal_model", "model", "pf", "squeeze", "p_up",
                      "trade", "mean_r", "win", "n", "since",
                      "limit",                                   # only when a limit order was filled
                      "tone",                                    # only when headlines exist (none offline)
                      "acionaveis_regra_antiga", "acionaveis_modelo_novo", "geometry",
                      "stop_atr_h1"}                             # legacy v1 breakout-model card (compat branch)
    assert not [k for k in missing if k not in allowed_absent], missing
