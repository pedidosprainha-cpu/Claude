"""Configuração de testes: diretórios temporários e geradores de dados sintéticos (sem rede)."""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="fxintel-test-")
os.environ.setdefault("FXI_DATA_DIR", _TMP)
os.environ.setdefault("FXI_DB_PATH", os.path.join(_TMP, "test.db"))
_CFG = os.path.join(_TMP, "config")
os.makedirs(_CFG, exist_ok=True)
import shutil  # noqa: E402

shutil.copy(os.path.join(os.path.dirname(__file__), "..", "config", "central_banks.json"), _CFG)
os.environ["FXI_CONFIG_DIR"] = _CFG  # testes nunca alteram a configuração real do usuário
os.environ["FXI_DISABLE_BACKGROUND"] = "1"
os.environ["FXI_AUTO_RETRAIN"] = "0"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


def synthetic_bars(n: int = 3000, freq: str = "1h", start: str = "2025-01-06", price: float = 1.10,
                   vol: float = 0.0012, seed: int = 1, drift_blocks: bool = True) -> pd.DataFrame:
    """Passeio aleatório com blocos de tendência, sem fins de semana."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=int(n * 1.5), freq=freq, tz="UTC")
    idx = idx[(idx.weekday < 5)][:n]
    drift = np.zeros(n)
    if drift_blocks:
        for b in range(0, n, 300):
            drift[b:b + 300] = rng.choice([-1, 0, 1]) * vol * 0.15
    r = drift + rng.normal(0, vol, n)
    c = price * np.exp(np.cumsum(r))
    o = np.concatenate([[price], c[:-1]])
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol / 2, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol / 2, n)))
    return pd.DataFrame({"o": o, "h": hi, "l": lo, "c": c, "v": 0.0}, index=idx)


@pytest.fixture
def bars():
    return synthetic_bars()
