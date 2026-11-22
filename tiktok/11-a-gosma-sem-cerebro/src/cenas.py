"""Gera as tomadas simuladas do Physarum (quadros JPG em build/shots/<nome>/ + meta.json com as fases).

Tomadas:
  macro      crescimento em leque, com veias, em volta de flocos de aveia (gancho, "o nome dela", fecho)
  labirinto  pedaços espalhados no labirinto se juntam e enchem tudo; comida na entrada e na saída;
             o modelo de Tero (2007) deixa só o caminho mais curto
  toquio     mapa real da região de Tóquio (Natural Earth), aveia em 36 cidades; a gosma sai de Tóquio,
             cobre a terra e o modelo de Tero (2010) afina a rede
  rastro     arena em Y: um braço já tem muco (rastro antigo) e a gosma escolhe o outro (Reid et al., 2012)
  sal        três pontes com sal (dia 1, 3 e 5): a cada dia ela atravessa mais rápido (Boisseau et al., 2016)
  fusao      duas gosmas se juntam; a que "aprendeu" (tingida) passa o comportamento para a outra
             (Vogel & Dussutour, 2016)

Uso: python3 src/cenas.py [nomes...]   (sem nomes: todas)
"""
import json, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gel import relevo_tubos, relevo_lencol, juntar, sombrear, para_png, agar
from molde import pontos, malha, campo_ruido, Plasmodio, dijkstra
from tero import Rede, caminho_mais_curto
from labirinto import gerar, grafo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "shots"
W, H = 1080, 1920
CIANO = np.array([0.35, 0.85, 1.0])

# ------------------------------------------------------------------ renderização em paralelo
_BG = {}


def _init(fundos):
    _BG.update(fundos)


def _render(job):
    nome, i, tubos, lencol, extra = job
    fundo = _BG[extra.get("fundo", "bg")]
    alt = juntar(relevo_tubos(tubos, W, H), relevo_lencol(lencol, W, H, largura=extra.get("larg", 30)) if len(lencol) else 0)
    pulso = None
    if "pulso" in extra:  # fluxo de vaivém (shuttle streaming): onda de espessura saindo da origem
        t, cx, cy = extra["pulso"]
        yy, xx = np.mgrid[0:alt.shape[0], 0:alt.shape[1]]
        r = np.hypot(xx * 2 - cx, yy * 2 - cy)
        pz = (1 + 0.075 * np.sin(2 * np.pi * (t / 1.6) - r / 260)).astype(np.float32)
        from scipy.ndimage import zoom
        pulso = zoom(pz, (H / pz.shape[0], W / pz.shape[1]), order=1)
    cor = None
    if "tinta" in extra:  # (segmentos com intensidade) → tingimento ciano do que foi aprendido
        im = Image.new("L", (W // 2, H // 2), 0); d = ImageDraw.Draw(im)
        for x0, y0, x1, y1, k in extra["tinta"]:
            d.line([(x0 / 2, y0 / 2), (x1 / 2, y1 / 2)], fill=int(255 * k), width=14)
        k = gaussian_filter(np.asarray(im.resize((W, H), Image.BILINEAR), np.float32) / 255, 6) * 0.75
        cor = np.dstack([np.broadcast_to(CIANO, (H, W, 3)), k[..., None]])
    base = fundo
    if "muco" in extra:  # filme de muco (rastro antigo): brilho translúcido esbranquiçado
        am = relevo_lencol(extra["muco"], W, H, largura=60, altura=1.6, sigma=10)
        base = sombrear(am, fundo, cores=([0.85, 0.86, 0.80], [0.75, 0.74, 0.62]), opacidade=0.38, brilho=0.9)
    img = sombrear(alt, base, pulso=pulso, foco=extra.get("foco"), cor_extra=cor, mascara=extra.get("mascara"))
    para_png(img).save(OUT / nome / f"{i + 1:05d}.jpg", quality=93)
    return i


class Saida:
    def __init__(self, nome, fundos, procs=4):
        self.nome = nome
        (OUT / nome).mkdir(parents=True, exist_ok=True)
        for f in (OUT / nome).glob("*.jpg"):
            f.unlink()
        self.pool = Pool(procs, initializer=_init, initargs=(fundos,))
        self.pend = []; self.n = 0; self.t = time.time()

    def quadro(self, tubos, lencol=(), **extra):
        tubos = np.asarray(tubos, np.float32).reshape(-1, 5); lencol = np.asarray(lencol, np.float32).reshape(-1, 5)
        self.pend.append(self.pool.apply_async(_render, ((self.nome, self.n, tubos, lencol, extra),)))
        self.n += 1
        while len(self.pend) > 12:
            self.pend.pop(0).get()

    def fim(self, meta):
        for p in self.pend:
            p.get()
        self.pool.close(); self.pool.join()
        meta["frames"] = self.n
        (OUT / self.nome / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        print(f"{self.nome}: {self.n} quadros em {time.time() - self.t:.0f}s", flush=True)


# ------------------------------------------------------------------ elementos de cenário
def aveia(img, x, y, s=1.0, seed=0):
    """floco de aveia: elipse irregular bege com textura, sombra e brilho (desenhado no fundo, sob a gosma)"""
    rng = np.random.default_rng(seed)
    R = int(34 * s); c = Image.new("RGBA", (R * 4, R * 4), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    ang = np.linspace(0, 2 * np.pi, 22, endpoint=False)
    rx, ry = R * (1.1 + 0.2 * rng.random()), R * (0.75 + 0.2 * rng.random())
    rot = rng.uniform(0, np.pi)
    pts = [(2 * R + np.cos(a + rot) * rx * (0.85 + 0.25 * rng.random()) * np.cos(a) - 0 + 0, 2 * R + np.sin(a + rot) * ry * (0.85 + 0.25 * rng.random())) for a in ang]
    pts = [(2 * R + (rx * np.cos(a)) * np.cos(rot) - (ry * np.sin(a)) * np.sin(rot) + rng.normal(0, R * 0.06),
            2 * R + (rx * np.cos(a)) * np.sin(rot) + (ry * np.sin(a)) * np.cos(rot) + rng.normal(0, R * 0.06)) for a in ang]
    d.polygon(pts, fill=(214, 196, 150, 255))
    a = np.asarray(c).astype(np.float32) / 255
    tex = gaussian_filter(rng.normal(0, 1, a.shape[:2]), 1.2)
    a[..., :3] *= (0.86 + 0.12 * tex[..., None] / (np.abs(tex).max() + 1e-6))
    luz = gaussian_filter(a[..., 3], 3); gy, gx = np.gradient(luz)
    a[..., :3] *= np.clip(1 + 2.2 * (-gx - gy)[..., None], 0.6, 1.4)
    a[..., :3] = np.clip(a[..., :3], 0, 1)
    sombra = gaussian_filter(np.roll(np.roll(a[..., 3], int(5 * s), 0), int(4 * s), 1), 4 * s)
    x0, y0 = int(x - 2 * R), int(y - 2 * R)
    reg = img[max(0, y0):y0 + 4 * R, max(0, x0):x0 + 4 * R]
    sa = sombra[max(0, -y0):max(0, -y0) + reg.shape[0], max(0, -x0):max(0, -x0) + reg.shape[1]]
    aa = a[max(0, -y0):max(0, -y0) + reg.shape[0], max(0, -x0):max(0, -x0) + reg.shape[1]]
    reg *= (1 - 0.55 * sa[..., None])
    reg[:] = reg * (1 - aa[..., 3:4]) + aa[..., :3] * aa[..., 3:4]


def placa(seed=3, tom=(0.075, 0.07, 0.06)):
    return agar(W, H, seed=seed, tom=tom)


# ------------------------------------------------------------------ macro
def macro():
    rng = np.random.default_rng(7)
    fundo = placa(3)
    oat = [(240, 560), (850, 430), (170, 1050), (930, 1000), (430, 260), (760, 1580), (300, 1520), (620, 820)]
    for k, (x, y) in enumerate(oat):
        aveia(fundo, x, y, 1.0 + 0.25 * rng.random(), seed=k)
    p = pontos(W, H, 17000, seed=2, margem=-30); e = malha(p, 38)
    o = int(np.argmin(np.hypot(p[:, 0] - 560, p[:, 1] - 1240)))
    fn = [int(np.argmin(np.hypot(p[:, 0] - x, p[:, 1] - y))) for x, y in oat]
    pl = Plasmodio(p, e, [(o, 0)], ruido=campo_ruido(W, H, 5, 90), aspereza=0.7, seed=3)
    S = Saida("macro", {"bg": fundo})
    N = 600
    for k in range(N):
        F = 25 + 1450 * (1 - (1 - k / N) ** 1.6)
        pl.avancar(F, comida=fn, passos=2, I0=5.0, gama=1.3, banda=50)
        tb, lc = pl.segmentos(F, rmax=10, banda=50)
        S.quadro(tb, lc, pulso=(k / 30, 560, 1240), foco=(1000, 760))
    S.fim({"origem": [560, 1240], "aveia": oat})


# ------------------------------------------------------------------ labirinto
def labirinto():
    nx, ny, cel = 9, 13, 100
    x0, y0 = 90, 330
    ab = gerar(nx, ny, 7, 7); xy, E, idx = grafo(ab, nx, ny, cel, x0, y0)
    # fundo: ágar nos corredores, filme plástico nas paredes
    fundo = placa(4, tom=(0.06, 0.058, 0.055))
    cor = Image.new("L", (W, H), 0); d = ImageDraw.Draw(cor)
    for a, b in E: d.line([tuple(xy[a]), tuple(xy[b])], fill=255, width=86)
    for q in xy: d.rectangle([q[0] - 43, q[1] - 43, q[0] + 43, q[1] + 43], fill=255)
    c = gaussian_filter(np.asarray(cor, np.float32) / 255, 1.2)
    fundo = fundo * (0.5 + 1.35 * c[..., None]) + c[..., None] * np.array([0.055, 0.05, 0.035])
    borda = np.clip(gaussian_filter(c, 2.5) - c, 0, 1) * 6  # brilho na quina das paredes (filme plástico)
    fundo = np.clip(fundo + borda[..., None] * np.array([0.10, 0.10, 0.11]), 0, 1).astype(np.float32)
    fundo_c = fundo.copy()
    ent, sai = idx[(0, 0)], idx[(nx - 1, ny - 1)]
    aveia(fundo_c, *xy[ent], 0.8, seed=21); aveia(fundo_c, *xy[sai], 0.8, seed=22)
    mascara = np.clip(c * 1.15, 0, 1).astype(np.float32)
    # enchimento: pedaços em 6 células, crescendo pelos corredores (distância em células)
    rng = np.random.default_rng(5)
    cels = list(idx.values()); sementes = rng.choice(cels, 6, replace=False)
    n = len(xy); viz = [[] for _ in range(n)]
    for a, b in E: viz[a].append(b); viz[b].append(a)
    dist = np.full(n, np.inf)
    fila = list(sementes)
    for s_ in sementes: dist[s_] = 0
    while fila:
        u = fila.pop(0)
        for v in viz[u]:
            if dist[v] > dist[u] + 1: dist[v] = dist[u] + 1; fila.append(v)
    dmax = dist.max()
    R = Rede(xy, E)
    snaps = caminho_mais_curto(R, ent, sai, 260, dt=0.25, gravar=set(range(261)))
    S = Saida("labirinto", {"bg": fundo, "bgc": fundo_c})
    Nf, Nc, Ns = 150, 36, 240
    for k in range(Nf):  # pedaços crescem e se fundem
        F = (dmax + 1.2) * (k / (Nf - 1)) ** 0.9
        segs = []
        for (a, b) in E:
            f = np.clip(F - max(dist[a], dist[b]) + 1, 0, 1)
            if f > 0: segs.append((*xy[a], *xy[b], 31 * f ** 0.6))
        pcs = [(*xy[s_], *xy[s_], 31 * min(1, 0.6 + F)) for s_ in sementes]
        S.quadro(segs + pcs, mascara=mascara, foco=(960, 900))
    full = [(*xy[a], *xy[b], 31.0) for a, b in E]
    for k in range(Nc):  # comida na entrada e na saída
        S.quadro(full, mascara=mascara, foco=(960, 900), fundo="bgc")
    for k in range(Ns):  # o modelo de Tero escolhe o caminho mais curto
        st = int(260 * (k / (Ns - 1)) ** 1.7)
        D = snaps[st]
        segs = [(*xy[a], *xy[b], 31 * min(1, v) ** 0.55) for (a, b), v in zip(E, D) if v > 0.02]
        S.quadro(segs, mascara=mascara, foco=(960, 900), fundo="bgc")
    caminho = [list(map(float, xy[i])) for i in range(n)]
    S.fim({"fases": {"enche": [0, Nf], "comida": Nf, "seleciona": [Nf + Nc, Nf + Nc + Ns]},
           "entrada": list(map(float, xy[ent])), "saida": list(map(float, xy[sai])), "celula": cel, "x0": x0, "y0": y0, "nx": nx, "ny": ny})


# ------------------------------------------------------------------ Tóquio
def toquio():
    import shapefile
    LON0, LON1, LAT1, LAT0 = 139.10, 140.36, 36.25, 35.10
    SX = W / (LON1 - LON0); SY = SX / np.cos(np.radians(35.7)); Y0 = 330
    P = lambda x, y: ((x - LON0) * SX, (LAT1 - y) * SY + Y0)
    terra = Image.new("L", (W, H), 0); d = ImageDraw.Draw(terra)
    for s in shapefile.Reader(str(ROOT / "assets" / "mapa" / "terra_kanto.shp")).shapes():
        b = s.bbox
        if b[2] < LON0 - 1 or b[0] > LON1 + 1 or b[3] < LAT0 - 1 or b[1] > LAT1 + 1: continue
        parts = list(s.parts) + [len(s.points)]
        for a, c in zip(parts, parts[1:]): d.polygon([P(*q) for q in s.points[a:c]], fill=255)
    m = np.asarray(terra) > 0
    # fundo: placa com o mapa "projetado" no ágar (terra mais clara, mar escuro e a linha da costa)
    tex = placa(6, tom=(0.06, 0.06, 0.06))
    tf = gaussian_filter(m.astype(np.float32), 1.6)[..., None]
    terra_c = tex * 2.6 + np.array([0.075, 0.068, 0.05])          # ágar claro sobre a terra
    mar_c = tex * 0.5 + np.array([0.010, 0.022, 0.040])           # mar escuro, azulado
    fundo = terra_c * tf + mar_c * (1 - tf)
    costa = np.clip(gaussian_filter(m.astype(np.float32), 1.2) * (1 - gaussian_filter(m.astype(np.float32), 1.2)) * 4, 0, 1)
    fundo = np.clip(fundo + costa[..., None] * np.array([0.22, 0.26, 0.3]), 0, 1).astype(np.float32)
    CID = json.loads((ROOT / "assets" / "cidades.json").read_text())
    fundo_c = fundo.copy()
    for k, (nome, (lo, la)) in enumerate(CID.items()):
        aveia(fundo_c, *P(lo, la), 0.42 if nome != "Tóquio" else 0.55, seed=40 + k)
    mm = m.copy(); mm[:Y0 - 5] = False; mm[Y0 + int((LAT1 - LAT0) * SY) + 5:] = False
    p = pontos(W, H, 9000, mascara=mm, seed=8)
    e = malha(p, 30, mascara=m)
    cid = [int(np.argmin(np.hypot(*(p - np.array(P(*v))).T))) for v in CID.values()]
    o = cid[list(CID).index("Tóquio")]
    pl = Plasmodio(p, e, [(o, 0)], ruido=campo_ruido(W, H, 9, 70), aspereza=0.5, seed=4)
    alcance = float(np.nanmax(pl.dist[np.isfinite(pl.dist)]))
    S = Saida("toquio", {"bg": fundo_c})
    Ng, Na = 150, 300
    for k in range(Ng):  # a gosma sai de Tóquio e cobre a terra
        F = 20 + (alcance + 40) * (k / (Ng - 1)) ** 1.15
        pl.avancar(F, comida=cid, passos=3, dt=0.1, I0=20.0, gama=1.8, banda=40)
        tb, lc = pl.segmentos(F, rmax=6.5, banda=40)
        S.quadro(tb, lc, larg=20)
    F = alcance + 500
    for k in range(Na):  # rede adaptativa (Tero 2010)
        pl.avancar(F, comida=cid, passos=5, dt=0.1, I0=20.0, gama=1.8, banda=40)
        tb, lc = pl.segmentos(F, rmax=6.5, banda=40)
        S.quadro(tb, [], larg=20)
    # trilhos reais (Natural Earth) e cidades, em pixels, para o render.js desenhar por cima
    trilhos = []
    for s in shapefile.Reader(str(ROOT / "assets" / "mapa" / "ne_10m_railroads.shp")).shapes():
        if any(LON0 - 0.2 <= x <= LON1 + 0.2 and LAT0 - 0.2 <= y <= LAT1 + 0.2 for x, y in s.points):
            trilhos.append([[round(c, 1) for c in P(*q)] for q in s.points])
    cidades = {k: [round(c, 1) for c in P(*v)] for k, v in CID.items()}
    S.fim({"fases": {"cresce": [0, Ng], "adapta": [Ng, Ng + Na]}, "trilhos": trilhos, "cidades": cidades})


# ------------------------------------------------------------------ rastro (arena em Y)
def rastro():
    Y = Image.new("L", (W, H), 0); d = ImageDraw.Draw(Y)
    d.line([(540, 1700), (540, 1050)], fill=255, width=230)
    d.line([(540, 1080), (250, 480)], fill=255, width=230); d.line([(540, 1080), (830, 480)], fill=255, width=230)
    for q in ((540, 1700), (250, 480), (830, 480), (540, 1060)): d.ellipse([q[0] - 115, q[1] - 115, q[0] + 115, q[1] + 115], fill=255)
    m = gaussian_filter(np.asarray(Y, np.float32) / 255, 2)
    fundo = placa(8, tom=(0.055, 0.053, 0.05))
    fundo = (fundo * (0.5 + 1.2 * m[..., None]) + m[..., None] * np.array([0.05, 0.045, 0.035])).astype(np.float32)
    aveia(fundo, 250, 470, 0.9, seed=61); aveia(fundo, 830, 470, 0.9, seed=62)
    esq = lambda x, y: ((np.asarray(x) < 520) & (np.asarray(y) < 1030)).astype(float)
    p = pontos(W, H, 9000, mascara=np.asarray(Y) > 128, seed=12); e = malha(p, 34, mascara=np.asarray(Y) > 128)
    o = int(np.argmin(np.hypot(p[:, 0] - 540, p[:, 1] - 1680)))
    pl = Plasmodio(p, e, [(o, 0)], ruido=campo_ruido(W, H, 3, 80), aspereza=0.45, repulsao=lambda x, y: 14 * esq(x, y), seed=2)
    # muco: o braço esquerdo já foi explorado antes (filme translúcido)
    rng = np.random.default_rng(3)
    mu = [(x, y, x + rng.normal(0, 30), y + rng.normal(0, 30), 0.9) for x, y in p[(p[:, 0] < 500) & (p[:, 1] < 1000)][::3]]
    alvo = [int(np.argmin(np.hypot(p[:, 0] - 830, p[:, 1] - 480)))]   # a aveia do braço livre
    S = Saida("rastro", {"bg": fundo})
    N = 150
    for k in range(N):
        F = 30 + 1450 * (k / (N - 1)) ** 1.1
        pl.avancar(F, comida=alvo, passos=2, I0=4.0, gama=1.3, banda=45)
        tb, lc = pl.segmentos(F, rmax=9, banda=45)
        S.quadro(tb, lc, muco=mu)
    S.fim({"bracos": {"muco": [250, 480], "livre": [830, 480]}})


# ------------------------------------------------------------------ sal (três pontes: dia 1, 3, 5)
def sal():
    ys = [640, 990, 1340]; xa, xb, s0, s1 = 120, 960, 370, 700
    Y = Image.new("L", (W, H), 0); d = ImageDraw.Draw(Y)
    for y in ys:
        d.rounded_rectangle([xa - 70, y - 72, xb + 70, y + 72], radius=72, fill=255)
    m = gaussian_filter(np.asarray(Y, np.float32) / 255, 2)
    fundo = placa(9, tom=(0.055, 0.053, 0.05))
    fundo = (fundo * (0.5 + 1.2 * m[..., None]) + m[..., None] * np.array([0.05, 0.045, 0.035])).astype(np.float32)
    rng = np.random.default_rng(4)
    cr = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dc = ImageDraw.Draw(cr)
    for y in ys:  # cristais de sal: cubinhos com face clara em cima e sombra
        for _ in range(95):
            x, yy, s, a = rng.uniform(s0, s1), y + rng.uniform(-58, 58), rng.uniform(3.5, 8), rng.uniform(0, np.pi / 2)
            q = [(x + s * np.cos(a + k * np.pi / 2), yy + s * np.sin(a + k * np.pi / 2)) for k in range(4)]
            v = int(rng.uniform(170, 235))
            dc.polygon([(qx + 2, qy + 3) for qx, qy in q], fill=(0, 0, 0, 120))
            dc.polygon(q, fill=(v, v, v + 8, 255)); dc.line(q[:2], fill=(255, 255, 255, 255), width=1)
        aveia(fundo, xb, y, 0.8, seed=int(y))
    cra = np.asarray(cr.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    fundo = fundo * (1 - cra[..., 3:4]) + cra[..., :3] * cra[..., 3:4]
    fundo = np.clip(fundo, 0, 1).astype(np.float32)
    msk = np.asarray(Y) > 128
    sims = []
    for j, (y, k) in enumerate(zip(ys, (9.0, 2.2, 0.15))):
        mj = msk.copy(); mj[:y - 80] = False; mj[y + 80:] = False
        p = pontos(W, H, 3600, mascara=mj, seed=20 + j); e = malha(p, 30, mascara=mj)
        o = int(np.argmin(np.hypot(p[:, 0] - xa, p[:, 1] - y)))
        rep = lambda x, yy, k=k: k * ((np.asarray(x) > s0) & (np.asarray(x) < s1)).astype(float)
        sims.append(Plasmodio(p, e, [(o, 0)], ruido=campo_ruido(W, H, 30 + j, 60), aspereza=0.35, repulsao=rep, seed=j))
    S = Saida("sal", {"bg": fundo})
    N = 150
    for k in range(N):
        F = 20 + 2200 * (k / (N - 1)) ** 1.05
        tbs, lcs = [], []
        for pl in sims:
            pl.avancar(F, comida=[], passos=1, I0=3.0, gama=1.3, banda=130)
            tb, lc = pl.segmentos(F, rmax=8, banda=130); tbs.append(tb); lcs.append(lc)
        S.quadro(np.vstack(tbs), np.vstack(lcs), larg=34)
    S.fim({"pontes": ys, "sal": [s0, s1]})


# ------------------------------------------------------------------ fusão
def fusao():
    fundo = placa(10)
    A, B = (330, 720), (760, 1260)
    aveia(fundo, 860, 520, 0.9, seed=81); aveia(fundo, 220, 1450, 0.9, seed=82)
    p = pontos(W, H, 15000, seed=31, margem=-20); e = malha(p, 36)
    oa = int(np.argmin(np.hypot(p[:, 0] - A[0], p[:, 1] - A[1]))); ob = int(np.argmin(np.hypot(p[:, 0] - B[0], p[:, 1] - B[1])))
    ru = campo_ruido(W, H, 13, 90)
    pl = Plasmodio(p, e, [(oa, 0), (ob, 0)], ruido=ru, aspereza=0.6, seed=5)
    # distâncias separadas, para saber quem é quem e espalhar o tingimento depois da fusão
    mid = (p[e[:, 0]] + p[e[:, 1]]) / 2
    w = pl.rede.L * np.exp(0.6 * ru(mid[:, 0], mid[:, 1]))
    da = dijkstra(len(p), e, w, [(oa, 0)]); db = dijkstra(len(p), e, w, [(ob, 0)])
    encontro = float(np.min(np.maximum(da, db)))
    S = Saida("fusao", {"bg": fundo})
    N = 165; tf = 0.5
    for k in range(N):
        q = k / (N - 1)
        F = 20 + (encontro + 260) * min(1, q / tf) ** 1.1
        pl.avancar(F, comida=[], passos=2, I0=4.0, gama=1.3, banda=45)
        tb, lc = pl.segmentos(F, rmax=10, banda=45)
        # tingimento: começa só na gosma A; depois da fusão, avança para dentro da B
        alcance = encontro + max(0, q - tf) / (1 - tf) * 1400
        ea = np.minimum(da[e[:, 0]], da[e[:, 1]])
        ok = pl.alcancada & (pl.rede.D > 0.04) & ((ea < db[e[:, 0]]) | (ea < alcance))
        tinta = np.c_[p[e[ok, 0]], p[e[ok, 1]], np.clip(1 - (ea[ok] - min(alcance, encontro)) / 300, 0.3, 1) if q > tf else np.ones(ok.sum())]
        S.quadro(tb, lc, tinta=tinta.tolist())
    S.fim({"A": A, "B": B, "fusao": int(N * tf)})


if __name__ == "__main__":
    nomes = sys.argv[1:] or ["macro", "labirinto", "toquio", "rastro", "sal", "fusao"]
    for n in nomes:
        globals()[n]()
