from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from fxengine import track


@dataclass
class FakeAlert:
    symbol: str
    p: float
    alert: bool
    until: datetime
    adr: float = 0.0100
    level: str = "alta"
    p_up: float | None = 0.6
    dir_confident: bool = True
    blocked: bool = False
    feats: dict = field(default_factory=dict)


def h1_path(closes, start="2026-11-02 00:00"):
    idx = pd.date_range(start, periods=len(closes), freq="1h", tz="UTC")
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + 0.0001, "l": np.minimum(o, c) - 0.0001, "c": c}, index=idx)


def test_explosion_record_is_scored_on_real_candles(tmp_path):
    flat = [1.1000] * 10
    jump = [1.1000, 1.1030, 1.1070, 1.1080]          # +0.8 ADR upwards within 4 h
    h1 = h1_path(flat + jump + [1.1080] * 3)
    t_dec = h1.index[10]                              # decision = close of bar 9 → window starts at bar 10
    a = FakeAlert("EURUSD", 0.55, True, (t_dec + pd.Timedelta(hours=4)).to_pydatetime())
    b = FakeAlert("GBPUSD", 0.10, False, (t_dec + pd.Timedelta(hours=4)).to_pydatetime(), p_up=0.4)
    assert track.record_explosions(str(tmp_path), [a, b], theta=0.5, horizon=4) == 2
    assert track.record_explosions(str(tmp_path), [a], theta=0.5, horizon=4) == 0      # same hour: once
    calm = h1_path([1.2500] * 17)
    assert track.evaluate(str(tmp_path), {"EURUSD": h1, "GBPUSD": calm}) == 2
    s = track.summary(str(tmp_path))
    assert s["explosion"]["alerts"] == 1 and s["explosion"]["alert_hit"] == 1.0
    assert s["explosion"]["others"] == 1 and s["explosion"]["other_hit"] == 0.0
    assert s["explosion"]["dir_conf_n"] == 1 and s["explosion"]["dir_conf_hit"] == 1.0     # predicted up, went up


def test_pending_until_the_window_has_passed(tmp_path):
    h1 = h1_path([1.1] * 12)
    a = FakeAlert("EURUSD", 0.5, True, (h1.index[11] + pd.Timedelta(hours=4)).to_pydatetime())
    track.record_explosions(str(tmp_path), [a], 0.5, 4)
    assert track.evaluate(str(tmp_path), {"EURUSD": h1}) == 0
    assert track.summary(str(tmp_path))["pending"] == 1


def test_corrupt_line_does_not_break_the_record(tmp_path):
    (tmp_path / track.FILE).write_text('{"k": "x", "status": "pendente"\nnot json\n', encoding="utf-8")
    assert track.summary(str(tmp_path))["explosion"]["alerts"] == 0


@dataclass
class FakePlan:
    entry: float
    sl_dist: float
    trail_dist: float
    exit_kind: str = "trail"
    tp1: float = 0.0
    horizon_h: int = 48


@dataclass
class FakeOpp:
    symbol: str
    direction: int
    plan: FakePlan
    executable: bool = True
    signal: object = None


def test_signal_trailing_stop_is_scored(tmp_path):
    # buy at 1.1000, risk 0.0020, trail 0.0010: goes to +2R (1.1040) then falls -> exit at 1.1030 (+1.5R)
    path = [1.1000, 1.1000, 1.1015, 1.1030, 1.1040, 1.1035, 1.1020, 1.1000] + [1.1000] * 50
    h1 = h1_path(path)
    now = (h1.index[0] + pd.Timedelta(minutes=10)).to_pydatetime()
    o = FakeOpp("EURUSD", 1, FakePlan(1.1000, 0.0020, 0.0010, horizon_h=48))
    assert track.record_signal(str(tmp_path), o, now)
    assert not track.record_signal(str(tmp_path), o, now)                 # once per hour
    assert track.evaluate(str(tmp_path), {"EURUSD": h1}) == 1
    s = track.summary(str(tmp_path))["signal"]
    assert s["n"] == 1 and abs(s["mean_r"] - 1.5) < 0.06
