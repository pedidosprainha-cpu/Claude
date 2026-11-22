"""Labirinto com alguns laços (mais de uma rota entre entrada e saída), como no experimento de Nakagaki (2000),
e o grafo de corredores para o modelo de Tero."""
import numpy as np


def gerar(nx=9, ny=13, laços=7, seed=11):
    """Labirinto perfeito (backtracking) + paredes removidas para abrir rotas alternativas.
    Devolve aberto[(a, b)] para pares de células vizinhas ligadas."""
    rng = np.random.default_rng(seed)
    vis = np.zeros((ny, nx), bool)
    aberto = set()
    pilha = [(0, 0)]; vis[0, 0] = True
    while pilha:
        x, y = pilha[-1]
        viz = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
               if 0 <= x + dx < nx and 0 <= y + dy < ny and not vis[y + dy, x + dx]]
        if not viz:
            pilha.pop(); continue
        q = viz[rng.integers(len(viz))]
        vis[q[1], q[0]] = True
        aberto.add(frozenset(((x, y), q)))
        pilha.append(q)
    # abre algumas paredes internas para criar laços (rotas alternativas, de comprimentos diferentes)
    paredes = [frozenset(((x, y), (x + dx, y + dy))) for y in range(1, ny - 1) for x in range(1, nx - 1)
               for dx, dy in ((1, 0), (0, 1)) if x + dx < nx - 1 and y + dy < ny - 1]
    paredes = [p for p in paredes if p not in aberto]
    for i in rng.choice(len(paredes), laços, replace=False):
        aberto.add(paredes[i])
    return aberto


def grafo(aberto, nx, ny, cel, x0, y0):
    """nós no centro de cada célula; arestas pelos corredores abertos"""
    idx = {(x, y): y * nx + x for y in range(ny) for x in range(nx)}
    xy = [(x0 + (x + 0.5) * cel, y0 + (y + 0.5) * cel) for y in range(ny) for x in range(nx)]
    edges = [tuple(sorted((idx[a], idx[b]))) for a, b in (tuple(p) for p in aberto)]
    return np.array(xy), sorted(edges), idx
