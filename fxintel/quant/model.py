"""Modelo probabilístico calibrado: P(TP1 antes do Stop | features no instante da decisão).

- Regressão logística regularizada (padrão; estável e interpretável) ou gradient boosting
  com calibração isotônica/sigmoide em validação temporal.
- Avaliação: Brier, Brier Skill Score vs. taxa-base do treino (climatologia), AUC, log-loss
  e tabela de confiabilidade com intervalos de Wilson.
- O valor esperado em R combina p calibrado com payoffs condicionais estimados no treino.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .stats import wilson


def evaluate(y: np.ndarray, p: np.ndarray, base_rate: float) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) == 0:
        return {"n": 0}
    brier = brier_score_loss(y, p)
    brier_ref = brier_score_loss(y, np.full_like(p, base_rate))
    try:
        auc = roc_auc_score(y, p) if 0 < y.sum() < len(y) else float("nan")
    except ValueError:
        auc = float("nan")
    return {
        "n": int(len(y)), "hit_rate": float(y.mean()), "mean_p": float(p.mean()),
        "brier": float(brier), "brier_climatology": float(brier_ref),
        "bss": float(1 - brier / brier_ref) if brier_ref > 0 else float("nan"),
        "auc": float(auc), "log_loss": float(log_loss(y, p, labels=[0, 1])),
    }


def calibration_table(y: np.ndarray, p: np.ndarray, edges=(0, .3, .4, .45, .5, .55, .6, .7, 1.0)) -> list[dict]:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (p >= a) & (p < b) if b < 1 else (p >= a) & (p <= b)
        n = int(m.sum())
        if n == 0:
            continue
        k = int(y[m].sum())
        lo, hi = wilson(k, n)
        out.append({"bin": [a, b], "n": n, "mean_p": float(p[m].mean()), "observed": k / n,
                    "ci90": [lo, hi]})
    return out


@dataclass
class ProbabilityModel:
    kind: str = "logistic"
    calibration: str = "sigmoid"
    features: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    est: object = None

    def _make(self, n: int):
        if self.kind == "hgb":
            base = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150,
                                                  min_samples_leaf=40, l2_regularization=1.0,
                                                  random_state=3)
            return CalibratedClassifierCV(base, method=self.calibration, cv=TimeSeriesSplit(3))
        return Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("lr", LogisticRegression(C=0.2, max_iter=3000)),
        ])

    def fit(self, X: pd.DataFrame, y: np.ndarray, r: np.ndarray | None = None,
            rr1: np.ndarray | None = None) -> "ProbabilityModel":
        self.features = list(X.columns)
        Xv = X.to_numpy(dtype=float)
        if self.kind == "hgb":
            self._imp = SimpleImputer(strategy="median").fit(Xv)
            Xv = self._imp.transform(Xv)
        self.est = self._make(len(X)).fit(Xv, y)
        self.meta["n_train"] = int(len(y))
        self.meta["base_rate"] = float(np.mean(y))
        if r is not None and rr1 is not None:
            r = np.asarray(r, dtype=float)
            rr1 = np.asarray(rr1, dtype=float)
            win = np.asarray(y) == 1
            self.meta["k_win"] = float(np.nanmean(r[win] / rr1[win])) if win.any() else 0.5
            self.meta["r_loss"] = float(np.nanmean(r[~win])) if (~win).any() else -1.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        Xv = X[self.features].to_numpy(dtype=float)
        if self.kind == "hgb":
            Xv = self._imp.transform(Xv)
        return self.est.predict_proba(Xv)[:, 1]

    def expected_r(self, p: np.ndarray, rr1: np.ndarray) -> np.ndarray:
        k = self.meta.get("k_win", 0.75)
        rl = self.meta.get("r_loss", -1.0)
        return p * k * rr1 + (1 - p) * rl

    def coefficients(self) -> list[dict]:
        if self.kind != "logistic" or self.est is None:
            return []
        lr = self.est.named_steps["lr"]
        return sorted(({"feature": f, "coef": float(c)} for f, c in zip(self.features, lr.coef_[0])),
                      key=lambda d: -abs(d["coef"]))

    def contributions(self, X: pd.DataFrame) -> list[dict]:
        """Contribuição de cada feature para o log-odds (coef × valor padronizado)."""
        if self.kind != "logistic" or self.est is None:
            return []
        imp, sc, lr = (self.est.named_steps[k] for k in ("imp", "sc", "lr"))
        z = sc.transform(imp.transform(X[self.features].to_numpy(dtype=float)))[0]
        con = z * lr.coef_[0]
        return sorted(({"feature": f, "value": float(v), "contribution": float(c)}
                       for f, v, c in zip(self.features, X[self.features].iloc[0], con)),
                      key=lambda d: -abs(d["contribution"]))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(self, f)
        tmp.replace(path)

    @staticmethod
    def load(path: Path) -> "ProbabilityModel | None":
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)
