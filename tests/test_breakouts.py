import json
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from fxengine import app_api, breakouts as bk, sessions
from fxengine.analysis import indicators as ta
from fxengine.config import Settings
from fxengine.data.provider import InstrumentData, build_frames
from fxengine.instruments import get


def m15_frame(close, start="2026-11-04 00:00", spread=0.00015):
    c = np.asarray(close, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    idx = pd.date_range(start, periods=len(c), freq="15min", tz="UTC")
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + spread, "l": np.minimum(o, c) - spread,
                         "c": c, "v": 0.0}, index=idx)


def ranging(n=400, seed=5):
    rng = np.random.default_rng(seed)
    return 1.1000 + 0.0007 * np.sin(np.arange(n) / 3.0) + rng.normal(0, 0.00008, n)


def level_of(df, R=6, N=48):
    ref = df.iloc[-(R + N):-R]
    hi, lo = float(ref.h.max()), float(ref.l.min())
    return bk.Level(hi, ["máxima de teste"], "range", 5.0, hi - lo, 1)


def test_classify_confirmed_breakout():
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]          # strong push through the range top
    df = m15_frame(c)
    a = float(ta.atr(df).iloc[-1])
    res = bk.classify(level_of(df), df, None, float(c[-1]), a, 6, 24)
    assert res is not None
    status, d, j, _ = res
    assert d == 1 and status in ("confirmado", "reteste") and j == len(c) - 4


def test_classify_false_breakout_is_a_trap():
    c = ranging()
    c[-4:] = [1.1018, 1.1004, 1.0998, 1.0995]          # pokes above, closes back inside
    df = m15_frame(c)
    a = float(ta.atr(df).iloc[-1])
    status, d, _, extreme = bk.classify(level_of(df), df, None, float(c[-1]), a, 6, 24)
    assert status == "falso" and d == 1
    assert extreme >= 1.1018


def test_classify_breaking_now_on_forming_bar():
    c = ranging()
    df = m15_frame(c)
    lv = level_of(df)
    a = float(ta.atr(df).iloc[-1])
    price = lv.price + 0.6 * a
    forming = pd.Series({"o": c[-1], "h": price, "l": c[-1], "c": price})
    status, d, j, _ = bk.classify(lv, df, forming, price, a, 6, 24)
    assert status == "rompendo" and d == 1 and j == len(df)


def test_no_event_inside_range():
    df = m15_frame(ranging())
    a = float(ta.atr(df).iloc[-1])
    assert bk.classify(level_of(df), df, None, float(df.c.iloc[-1]), a, 6, 24) is None


def _instrument_data(c, symbol="EURUSD"):
    m15 = m15_frame(c)
    h1 = ta.resample(m15, "1h")
    frames = build_frames(None, m15, h1)
    px = float(c[-1])
    inst = get(symbol)
    return InstrumentData(inst, frames, px, px - 0.00005, px + 0.00005,
                          m15.index[-1].to_pydatetime(), "teste", True, [])


def test_detect_end_to_end_builds_a_valid_plan():
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]
    data = _instrument_data(c)
    now = (data.frames["M15"].index[-1] + timedelta(minutes=15, seconds=5)).to_pydatetime()
    out = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now))
    ups = [b for b in out if b.direction == 1 and b.status != "falso"]
    assert ups, [(b.status, b.level.label) for b in out]
    b = ups[0]
    p = b.plan
    assert p.sl < p.entry < p.tp1 < p.tp2
    assert p.entry == data.ask and p.rr1 >= 1.0 and p.lots > 0
    assert 0 <= b.quality <= 100 and b.grade in ("A+", "A", "B", "C", "D")


def test_follow_through_random_walk_is_near_half():
    rng = np.random.default_rng(1)
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.0007, 6000)))
    n, w = bk.follow_through(m15_frame(c, spread=0.0001), 48, 1, 16)
    assert n > 40
    assert 0.3 < w / n < 0.65


def test_tracker_flags_only_new_events(tmp_path):
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]
    data = _instrument_data(c)
    now = (data.frames["M15"].index[-1] + timedelta(minutes=15, seconds=5)).to_pydatetime()
    ev = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now))
    path = str(tmp_path / "state.json")
    assert bk.Tracker(path).mark(ev, now) == len(ev) > 0
    ev2 = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now))
    assert bk.Tracker(path).mark(ev2, now + timedelta(minutes=2)) == 0
    assert all(not b.is_new and b.first_seen is not None for b in ev2)


def test_scan_breakouts_api_offline(tmp_path):
    calls = []

    class Listener:
        def onProgress(self, pct, msg):  # noqa: N802 - mirrors the Java interface
            calls.append(pct)

    raw = app_api.scan_breakouts(str(tmp_path), 5000, 1.0, "all", listener=Listener(), offline=True)
    d = json.loads(raw)
    assert d["ok"] is True and d["scanned"] == 32
    assert calls[-1] == 100
    assert d["breakouts"], "synthetic market should contain breakouts"
    item = d["breakouts"][0]
    for key in ("id", "symbol", "tf", "side", "status", "status_label", "level", "level_label",
                "quality", "grade", "plan", "order_text", "is_new", "actionable", "headline"):
        assert key in item
    assert d["new_count"] == len(d["breakouts"])
    again = json.loads(app_api.scan_breakouts(str(tmp_path), offline=True))
    assert again["new_count"] == 0


@pytest.mark.parametrize("status", ["rompendo", "confirmado", "reteste", "falso"])
def test_status_labels_exist(status):
    assert bk.STATUS_LABEL[status]


def test_derived_feature_values():
    f = {"ext_atr": 2.0, "st_falso": 1.0, "htf_trend": -0.5}
    assert bk.derived_value("ext_atr^2", f) == 4.0
    assert bk.derived_value("st_falso*htf_trend", f) == -0.5
    assert bk.derived_value("missing", f) == 0.0


def test_model_sets_probability_and_grade(tmp_path):
    names = list(bk.FEATURES) + ["ext_atr^2"]
    coef = [0.0] * len(names)
    coef[names.index("htf_trend")] = 1.0
    model_file = tmp_path / "m.json"
    model_file.write_text(json.dumps({
        "features": names, "mean": [0.0] * len(names), "std": [1.0] * len(names), "coef": coef,
        "intercept": 0.0, "ev_grades": [[0.3, "A+"], [0.2, "A"], [0.1, "B"], [0.0, "C"]],
        "ev_actionable": 0.1, "p_actionable": 0.0, "info": {"events": 1}}))
    model = bk.load_model(str(model_file))
    assert model is not None and 0 < model.prob({"htf_trend": 0.5}) < 1
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]
    data = _instrument_data(c)
    now = (data.frames["M15"].index[-1] + timedelta(minutes=15, seconds=5)).to_pydatetime()
    out = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now), model=model)
    assert out
    for b in out:
        assert b.prob is not None and 0 < b.prob < 1
        assert b.ev_r == pytest.approx(b.prob * b.plan.rr1 - (1 - b.prob))
        assert b.quality == pytest.approx(round(b.prob * 100, 1))
        if b.status == "rompendo":
            assert not b.actionable


def test_missing_model_falls_back_to_rules(tmp_path):
    assert bk.load_model(str(tmp_path / "nope.json")) is None
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]
    data = _instrument_data(c)
    now = (data.frames["M15"].index[-1] + timedelta(minutes=15, seconds=5)).to_pydatetime()
    out = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now), model=bk.NO_MODEL)
    assert out and all(b.prob is None and b.quality == b.heuristic for b in out)


def test_model_geometry_drives_the_plan(tmp_path):
    names = list(bk.FEATURES)
    model_file = tmp_path / "g.json"
    model_file.write_text(json.dumps({
        "features": names, "mean": [0.0] * len(names), "std": [1.0] * len(names), "coef": [0.0] * len(names),
        "intercept": 0.0, "ev_grades": [[0.0, "C"]], "ev_actionable": 0.1, "p_actionable": 0.0,
        "geometry": {"stop_atr_h1": 1.0, "tp1_r": 2.0}, "info": {}}))
    model = bk.load_model(str(model_file))
    c = ranging()
    c[-4:] = [1.1016, 1.1022, 1.1026, 1.1029]
    data = _instrument_data(c)
    now = (data.frames["M15"].index[-1] + timedelta(minutes=15, seconds=5)).to_pydatetime()
    atr_h1 = float(ta.atr(data.frames["H1"]).iloc[-1])
    out = bk.detect(data, now, Settings(), {"EURUSD": data.price}, None, [], sessions.state(now), model=model)
    assert out
    for b in out:
        sl_dist = abs(b.plan.entry - b.plan.sl)
        assert sl_dist >= atr_h1 - 1e-9
        assert b.plan.rr1 == pytest.approx(2.0)
