"""Modelo de Tero et al. para a rede de tubos do Physarum (o mesmo usado pelos autores dos experimentos).

Cada tubo (aresta) tem condutividade D e comprimento L. A cada passo, o protoplasma é empurrado de uma
fonte para um sumidouro; o fluxo Q em cada tubo sai das leis de Kirchhoff (como num circuito elétrico) e
cada tubo se adapta:  dD/dt = f(|Q|) − D.
Tubo com muito fluxo engrossa; tubo sem fluxo encolhe e desaparece.

- Labirinto (Tero, Kobayashi & Nakagaki, J. Theor. Biol. 2007): f(Q) = |Q|, fonte e sumidouro fixos →
  sobra só o caminho mais curto.
- Rede de Tóquio (Tero et al., Science 2010): f(Q) = |Q|^γ / (1 + |Q|^γ), γ = 1,8; a cada passo uma
  cidade sorteada empurra o fluxo e as demais o recebem.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve


class Rede:
    def __init__(self, xy, edges):
        self.xy = np.asarray(xy, float)
        self.e = np.asarray(edges, int)
        self.n = len(self.xy)
        d = self.xy[self.e[:, 0]] - self.xy[self.e[:, 1]]
        self.L = np.hypot(d[:, 0], d[:, 1])
        self.D = np.ones(len(self.e))
        m = len(self.e)
        # matriz de incidência: (n × m), +1 na origem e −1 no destino da aresta
        self.B = sp.csr_matrix((np.r_[np.ones(m), -np.ones(m)], (np.r_[self.e[:, 0], self.e[:, 1]], np.r_[np.arange(m), np.arange(m)])),
                               shape=(self.n, m))

    def fluxo(self, fonte, sumidouro, I0):
        g = self.D / self.L + 1e-9
        Lap = (self.B @ sp.diags(g) @ self.B.T).tocsc()
        b = np.zeros(self.n); b[fonte] += I0
        sumidouro = np.atleast_1d(sumidouro); np.add.at(b, sumidouro, -I0 / len(sumidouro))
        # aterra o sumidouro (pressão zero) para a matriz deixar de ser singular
        k = np.atleast_1d(sumidouro)[0]
        keep = np.ones(self.n, bool); keep[k] = False
        p = np.zeros(self.n)
        p[keep] = spsolve(Lap[keep][:, keep] + sp.identity(self.n - 1, format="csc") * 1e-10, b[keep])
        return g * (self.B.T @ p)

    def passo(self, Q, dt, f):
        self.D += dt * (f(np.abs(Q)) - self.D)
        np.maximum(self.D, 0, out=self.D)


def caminho_mais_curto(rede, fonte, sumidouro, passos, dt=0.25, I0=1.0, gravar=()):
    """Tero 2007 (μ = 1). Devolve {passo: D} para os passos pedidos."""
    snaps = {}
    for k in range(passos + 1):
        if k in gravar:
            snaps[k] = rede.D.copy()
        if k == passos:
            break
        rede.passo(rede.fluxo(fonte, sumidouro, I0), dt, lambda q: q)
    return snaps


def rede_adaptativa(rede, cidades, passos, dt=0.2, I0=2.0, gama=1.8, gravar=(), seed=1):
    """Tero 2010: a cada passo, uma cidade sorteada empurra o fluxo e as outras recebem."""
    rng = np.random.default_rng(seed)
    f = lambda q: q ** gama / (1 + q ** gama)
    snaps = {}
    for k in range(passos + 1):
        if k in gravar:
            snaps[k] = rede.D.copy()
        if k == passos:
            break
        a = rng.integers(len(cidades))
        outras = [c for i, c in enumerate(cidades) if i != a]
        rede.passo(rede.fluxo(cidades[a], outras, I0), dt, f)
    return snaps
