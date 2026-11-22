"""Physarum crescendo numa malha orgânica, com uma frente que avança e veias que se formam atrás dela.

- Malha: triangulação de Delaunay de pontos aleatórios (ângulos naturais, sem cara de grade).
- Frente: distância de Dijkstra a partir da origem, com ruído suave, para a borda irregular em leque.
- Veias: modelo de Tero (tero.py). O protoplasma sai da origem (e da comida já alcançada) e corre até a borda
  que cresce; os tubos com mais fluxo engrossam, e o resto do lençol afina e some.
"""
import heapq
import numpy as np
from scipy.spatial import Delaunay
from scipy.ndimage import gaussian_filter, map_coordinates
from tero import Rede


def pontos(W, H, n, mascara=None, seed=0, margem=0):
    rng = np.random.default_rng(seed)
    p = np.c_[rng.uniform(margem, W - margem, n * 2), rng.uniform(margem, H - margem, n * 2)]
    if mascara is not None:
        p = p[mascara[p[:, 1].astype(int).clip(0, mascara.shape[0] - 1), p[:, 0].astype(int).clip(0, mascara.shape[1] - 1)]]
    return p[:n]


def malha(p, maxlen, mascara=None):
    tri = Delaunay(p)
    e = set()
    for a, b, c in tri.simplices:
        e.update({tuple(sorted(x)) for x in ((a, b), (b, c), (a, c))})
    e = np.array(sorted(e))
    d = np.hypot(*(p[e[:, 0]] - p[e[:, 1]]).T)
    ok = d < maxlen
    if mascara is not None:
        m = (p[e[:, 0]] + p[e[:, 1]]) / 2
        ok &= mascara[m[:, 1].astype(int).clip(0, mascara.shape[0] - 1), m[:, 0].astype(int).clip(0, mascara.shape[1] - 1)]
    return e[ok]


def campo_ruido(W, H, seed, escala=60.0):
    rng = np.random.default_rng(seed)
    g = gaussian_filter(rng.normal(0, 1, (int(H / escala * 4) + 4, int(W / escala * 4) + 4)), 2)
    g /= g.std() + 1e-9
    return lambda x, y: map_coordinates(g, [np.asarray(y) / escala * 4, np.asarray(x) / escala * 4], order=1, mode="nearest")


def dijkstra(n, e, peso, origens):
    viz = [[] for _ in range(n)]
    for (a, b), w in zip(e, peso):
        viz[a].append((b, w)); viz[b].append((a, w))
    d = np.full(n, np.inf); h = []
    for o, d0 in origens:
        d[o] = d0; heapq.heappush(h, (d0, o))
    while h:
        dd, u = heapq.heappop(h)
        if dd > d[u]:
            continue
        for v, w in viz[u]:
            if dd + w < d[v]:
                d[v] = dd + w; heapq.heappush(h, (d[v], v))
    return d


class Plasmodio:
    def __init__(self, p, e, origens, ruido=None, aspereza=0.55, repulsao=None, seed=0):
        """origens: lista de (nó, atraso em px de frente). repulsao(x, y) >= 0 encarece caminhos (ex.: muco, sal)."""
        self.p, self.e = p, e
        self.rede = Rede(p, e)
        self.rede.D[:] = 0
        mid = (p[e[:, 0]] + p[e[:, 1]]) / 2
        w = self.rede.L.copy()
        if ruido is not None:
            w *= np.exp(aspereza * ruido(mid[:, 0], mid[:, 1]))
        if repulsao is not None:
            w *= 1 + repulsao(mid[:, 0], mid[:, 1])
        self.dist = dijkstra(len(p), e, w, origens)
        self.de = np.maximum(self.dist[e[:, 0]], self.dist[e[:, 1]])
        self.origens = [o for o, _ in origens]
        self.rng = np.random.default_rng(seed)
        self.alcancada = np.zeros(len(e), bool)

    def avancar(self, frente, comida=(), passos=2, dt=0.12, I0=3.0, banda=40.0, gama=1.4):
        """move a frente até `frente` (px) e adapta os tubos alcançados"""
        novas = (~self.alcancada) & (self.de <= frente)
        self.rede.D[novas] = 1.0
        self.alcancada |= novas
        if not self.alcancada.any():
            return
        no_alc = np.zeros(len(self.p), bool)
        no_alc[self.e[self.alcancada].ravel()] = True
        borda = np.flatnonzero(no_alc & (self.dist > frente - banda))
        com = [c for c in comida if no_alc[c]]
        fontes = [o for o in self.origens if no_alc[o]] + com
        f = lambda q: q ** gama / (1 + q ** gama)
        for _ in range(passos):
            if not fontes:
                break
            s = fontes[self.rng.integers(len(fontes))]
            sumid = [c for c in com if c != s] + (list(self.rng.choice(borda, min(len(borda), 60), replace=False)) if len(borda) else [])
            if not sumid:
                break
            Q = self.rede.fluxo(s, sumid, I0)
            D = self.rede.D
            D[self.alcancada] += dt * (f(np.abs(Q[self.alcancada])) - D[self.alcancada])
            np.maximum(D, 0, out=D)

    def segmentos(self, frente, rmax=9.0, banda=45.0, dmin=0.04):
        """(tubos, lençol): tubos com raio pela condutividade; lençol com intensidade maior bem na borda"""
        D = self.rede.D
        atras = np.clip(frente - self.de, 0, None)
        perto = np.exp(-atras / banda) * (self.de <= frente)
        perto = perto * (0.55 + 0.45 * np.exp(-atras / (banda * 0.25)))     # borda mais grossa
        ok = self.alcancada & (D > dmin) & (perto < 0.9)
        a, b = self.e[ok, 0], self.e[ok, 1]
        tubos = np.c_[self.p[a], self.p[b], rmax * np.clip(D[ok], 0, 1.6) ** 0.5]
        ok2 = self.alcancada & (perto > 0.04)
        a, b = self.e[ok2, 0], self.e[ok2, 1]
        return tubos, np.c_[self.p[a], self.p[b], perto[ok2]]
