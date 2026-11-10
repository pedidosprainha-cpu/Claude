"""Small histogram gradient-boosting classifier (numpy only).

Depth-limited regression trees on the logistic loss, histogram split search on
quantile bins, row subsampling, L2 on leaf values. Exported as plain thresholds
(raw feature values) so the app evaluates it with simple comparisons.
"""
from __future__ import annotations

import numpy as np


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


class GBM:
    def __init__(self, n_trees: int = 150, depth: int = 3, lr: float = 0.05, min_leaf: int = 300,
                 n_bins: int = 32, l2: float = 5.0, subsample: float = 0.7, seed: int = 0):
        self.n_trees, self.depth, self.lr, self.min_leaf = n_trees, depth, lr, min_leaf
        self.n_bins, self.l2, self.subsample, self.seed = n_bins, l2, subsample, seed

    # -------------------------------------------------------------- fit
    def _bin(self, X: np.ndarray) -> np.ndarray:
        Xb = np.zeros(X.shape, dtype=np.uint8)
        for f, e in enumerate(self.edges):
            Xb[:, f] = np.searchsorted(e, X[:, f], side="left") if len(e) else 0
        return Xb

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GBM":
        rng = np.random.default_rng(self.seed)
        n, k = X.shape
        self.edges = []
        for f in range(k):
            qs = np.unique(np.quantile(X[:, f], np.linspace(0, 1, self.n_bins + 1)[1:-1]))
            self.edges.append(qs)
        Xb = self._bin(X)
        p0 = float(np.clip(y.mean(), 1e-4, 1 - 1e-4))
        self.base = float(np.log(p0 / (1 - p0)))
        F = np.full(n, self.base)
        self.trees = []
        for _ in range(self.n_trees):
            p = _sigmoid(F)
            g, h = p - y, np.clip(p * (1 - p), 1e-6, None)
            rows = rng.random(n) < self.subsample
            tree = []
            self._grow(Xb, g, h, np.flatnonzero(rows), 0, tree)
            self.trees.append(tree)
            F += self.lr * self._predict_tree_binned(tree, Xb)
        return self

    def _grow(self, Xb, g, h, rows, d, tree) -> int:
        node = len(tree)
        tree.append(None)
        G, H = g[rows].sum(), h[rows].sum()
        leaf = -G / (H + self.l2)
        if d >= self.depth or len(rows) < 2 * self.min_leaf:
            tree[node] = ("leaf", float(leaf))
            return node
        best = (0.0, None, None)
        parent = G * G / (H + self.l2)
        for f in range(Xb.shape[1]):
            nb = len(self.edges[f]) + 1
            if nb < 2:
                continue
            xb = Xb[rows, f]
            gh = np.bincount(xb, weights=g[rows], minlength=nb)
            hh = np.bincount(xb, weights=h[rows], minlength=nb)
            ch = np.bincount(xb, minlength=nb)
            GL, HL, CL = np.cumsum(gh)[:-1], np.cumsum(hh)[:-1], np.cumsum(ch)[:-1]
            GR, HR, CR = G - GL, H - HL, len(rows) - CL
            ok = (CL >= self.min_leaf) & (CR >= self.min_leaf)
            if not ok.any():
                continue
            gain = GL ** 2 / (HL + self.l2) + GR ** 2 / (HR + self.l2) - parent
            gain[~ok] = -np.inf
            b = int(np.argmax(gain))
            if gain[b] > best[0]:
                best = (float(gain[b]), f, b)
        if best[1] is None:
            tree[node] = ("leaf", float(leaf))
            return node
        _, f, b = best
        left_rows = rows[Xb[rows, f] <= b]
        right_rows = rows[Xb[rows, f] > b]
        li = self._grow(Xb, g, h, left_rows, d + 1, tree)
        ri = self._grow(Xb, g, h, right_rows, d + 1, tree)
        tree[node] = ("split", f, b, li, ri)
        return node

    def _predict_tree_binned(self, tree, Xb) -> np.ndarray:
        out = np.zeros(len(Xb))
        idx = np.zeros(len(Xb), dtype=int)
        active = np.ones(len(Xb), dtype=bool)
        while active.any():
            for node in np.unique(idx[active]):
                m = active & (idx == node)
                t = tree[node]
                if t[0] == "leaf":
                    out[m] = t[1]
                    active[m] = False
                else:
                    _, f, b, li, ri = t
                    go_left = Xb[m, f] <= b
                    sub = np.flatnonzero(m)
                    idx[sub[go_left]] = li
                    idx[sub[~go_left]] = ri
        return out

    # -------------------------------------------------------------- predict / export
    def decision(self, X: np.ndarray) -> np.ndarray:
        Xb = self._bin(X)
        return self.base + self.lr * sum(self._predict_tree_binned(t, Xb) for t in self.trees)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return _sigmoid(self.decision(X))

    def export(self) -> dict:
        """Trees with raw thresholds: go left when x <= threshold (bin b <=> x <= edges[b])."""
        trees = []
        for t in self.trees:
            nodes = []
            for nd in t:
                if nd[0] == "leaf":
                    nodes.append([-1, 0.0, -1, -1, round(self.lr * nd[1], 6)])
                else:
                    _, f, b, li, ri = nd
                    e = self.edges[f]
                    thr = float(e[b]) if b < len(e) else float("inf")
                    nodes.append([int(f), thr, int(li), int(ri), 0.0])
            trees.append(nodes)
        return {"base": round(self.base, 6), "trees": trees}


def gbm_logit(export: dict, x: np.ndarray) -> float:
    """Evaluate an exported model on one feature vector (what the app does)."""
    z = export["base"]
    for nodes in export["trees"]:
        i = 0
        while nodes[i][0] >= 0:
            f, thr, li, ri, _ = nodes[i]
            i = li if x[f] <= thr else ri
        z += nodes[i][4]
    return z
