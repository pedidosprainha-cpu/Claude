import numpy as np
import pandas as pd

from fxengine.config import Settings
from fxengine.data import provider as pv


def bars(start, n, freq="1h", base=1.10):
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    c = base + np.arange(n) * 1e-5
    return pd.DataFrame({"o": c, "h": c + 1e-4, "l": c - 1e-4, "c": c, "v": 0.0}, index=idx)


class FakeYahoo:
    """Serves a 'true' long series; short ranges are its tail. Counts calls per range."""

    def __init__(self, full):
        self.full, self.calls = full, []

    def candles(self, http, symbol, iv, rng, ttl=0):
        self.calls.append(rng)
        days = {"1y": 366, "1mo": 31, "30d": 43, "5d": 8, "1d": 1}[rng]
        return self.full[self.full.index >= self.full.index[-1] - pd.Timedelta(days=days)].copy(), {}


def test_incremental_splice_equals_full_download(tmp_path, monkeypatch):
    full = bars("2025-11-01", 24 * 380)
    fake = FakeYahoo(full.iloc[:-100])                      # history up to some point
    monkeypatch.setattr(pv.yahoo, "candles", fake.candles)
    p = pv.Provider(Settings(cache_dir=str(tmp_path)))
    first, _ = p.candles("EURUSD=X", "1h", "1y", 0)
    assert fake.calls == ["1y"]
    fake.full = full                                         # time passes: 100 new bars
    second, _ = p.candles("EURUSD=X", "1h", "1y", 0)
    assert fake.calls[-1] == "1mo"                           # only the short range was downloaded
    ref, _ = FakeYahoo(full).candles(None, "", "1h", "1y")
    assert second.index.equals(ref.index) and np.allclose(second.c, ref.c)


def test_falls_back_to_full_when_pieces_do_not_overlap(tmp_path, monkeypatch):
    full = bars("2025-11-01", 24 * 380)
    fake = FakeYahoo(full.iloc[: 24 * 300])
    monkeypatch.setattr(pv.yahoo, "candles", fake.candles)
    p = pv.Provider(Settings(cache_dir=str(tmp_path)))
    p.candles("EURUSD=X", "1h", "1y", 0)
    fake.full = full                                         # 80 days later: 1mo no longer overlaps
    out, _ = p.candles("EURUSD=X", "1h", "1y", 0)
    assert fake.calls[-2:] == ["1mo", "1y"] and out.index[-1] == full.index[-1]


def test_corrupt_store_costs_one_full_download(tmp_path, monkeypatch):
    fake = FakeYahoo(bars("2025-11-01", 24 * 380))
    monkeypatch.setattr(pv.yahoo, "candles", fake.candles)
    p = pv.Provider(Settings(cache_dir=str(tmp_path)))
    (tmp_path / "hist").mkdir()
    (tmp_path / "hist" / "EURUSD_X_1h.pkl").write_bytes(b"not a pickle")
    out, _ = p.candles("EURUSD=X", "1h", "1y", 0)
    assert fake.calls == ["1y"] and len(out) > 1000


def test_short_ranges_are_not_stored(tmp_path, monkeypatch):
    fake = FakeYahoo(bars("2025-11-01", 24 * 40))
    monkeypatch.setattr(pv.yahoo, "candles", fake.candles)
    p = pv.Provider(Settings(cache_dir=str(tmp_path)))
    p.candles("EURUSD=X", "1h", "1mo", 0)
    assert not (tmp_path / "hist").exists()
