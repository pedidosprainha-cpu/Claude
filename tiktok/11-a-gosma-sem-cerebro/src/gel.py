"""Sombreamento de "gel" para o Physarum: transforma tubos (segmentos com raio) ou um campo de densidade num
relevo, e ilumina como macrofotografia: amarelo translúcido, brilho especular, luz que atravessa o gel,
sombra sobre o ágar e profundidade de campo."""
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, zoom

AMARELO_CLARO = np.array([1.0, 0.90, 0.42])
AMARELO_FUNDO = np.array([0.98, 0.66, 0.05])
LUZ = np.array([-0.45, -0.62, 0.64]); LUZ /= np.linalg.norm(LUZ)
MEIO = LUZ + np.array([0, 0, 1.0]); MEIO /= np.linalg.norm(MEIO)
BINS = [(0, 1.6), (1.6, 3.2), (3.2, 6.0), (6.0, 11.0), (11.0, 99.0)]


def relevo_tubos(segs, W, H, escala=0.5):
    """segs: (N, 5) x0, y0, x1, y1, raio (px da imagem final). Devolve a altura (H*escala, W*escala)."""
    w, h = int(W * escala), int(H * escala)
    alt = np.zeros((h, w), np.float32)
    if len(segs) == 0:
        return alt
    segs = np.asarray(segs, float)
    for r0, r1 in BINS:
        sel = segs[(segs[:, 4] >= r0) & (segs[:, 4] < r1)]
        if not len(sel):
            continue
        rm = float(np.clip(sel[:, 4].mean(), 0.6, 40)) * escala
        im = Image.new("L", (w * 2, h * 2), 0); d = ImageDraw.Draw(im)  # 2x para suavizar
        for x0, y0, x1, y1, r in sel:
            rr = max(0.7, r * escala) * 2
            d.line([(x0 * escala * 2, y0 * escala * 2), (x1 * escala * 2, y1 * escala * 2)], fill=255, width=max(1, int(round(rr * 2))))
            d.ellipse([x1 * escala * 2 - rr, y1 * escala * 2 - rr, x1 * escala * 2 + rr, y1 * escala * 2 + rr], fill=255)
        m = np.asarray(im.resize((w, h), Image.BILINEAR), np.float32) / 255
        b = gaussian_filter(m, max(0.6, rm * 0.55))
        np.maximum(alt, np.clip(b * 1.6, 0, 1) ** 0.7 * rm, out=alt)
    return alt


def relevo_lencol(segs, W, H, escala=0.5, largura=30.0, altura=2.6, sigma=7.0):
    """lençol fino de protoplasma perto da frente: segs (N, 5) x0, y0, x1, y1, intensidade 0..1"""
    w, h = int(W * escala), int(H * escala)
    if len(segs) == 0:
        return np.zeros((h, w), np.float32)
    im = Image.new("L", (w, h), 0); d = ImageDraw.Draw(im)
    lw = max(1, int(largura * escala))
    for x0, y0, x1, y1, k in sorted(np.asarray(segs, float).tolist(), key=lambda s: s[4]):
        d.line([(x0 * escala, y0 * escala), (x1 * escala, y1 * escala)], fill=int(255 * min(1, k)), width=lw)
    m = gaussian_filter(np.asarray(im, np.float32) / 255, sigma * escala)
    return (np.clip(m * 1.4, 0, 1) ** 0.8 * altura).astype(np.float32)


def juntar(tubos, lencol):
    """soma suave: o lençol não empilha por cima de um tubo grosso"""
    return tubos + lencol * (1 - np.clip(tubos / 3.0, 0, 1))


def sombrear(alt, fundo, escala=0.5, pulso=None, foco=None, brilho=1.0, cor_extra=None, mascara=None, cores=None, opacidade=1.0):
    """alt: relevo na escala reduzida; fundo: RGB float (H, W, 3) em 0..1 na resolução final."""
    H, W = fundo.shape[:2]
    a = zoom(alt, (H / alt.shape[0], W / alt.shape[1]), order=1) / escala
    if pulso is not None:
        a = a * pulso
    if mascara is not None:
        a = a * mascara
    tx = textura(H, W)
    a = a * (1 + 0.18 * tx[0] + 0.10 * tx[1])            # superfície levemente ondulada, úmida
    gy, gx = np.gradient(a)
    n = np.dstack([-gx * 0.55, -gy * 0.55, np.ones_like(a)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    dif = np.clip(n @ LUZ, 0, 1)
    spec = (np.clip(n @ MEIO, 0, 1) ** 26) * (0.35 + 0.65 * np.clip(tx[1] * 0.5 + 0.5, 0, 1))
    esp = np.clip(a / 7.0, 0, 1)
    alfa = np.clip((a - 0.15) / 1.6, 0, 1); alfa = alfa * alfa * (3 - 2 * alfa) * np.clip(0.55 + a / 6, 0, 0.96)
    gran = 1 + 0.05 * tx[2]                               # citoplasma granulado
    c0, c1 = cores if cores is not None else (AMARELO_CLARO, AMARELO_FUNDO)
    alfa = alfa * opacidade
    cor = (np.asarray(c0) * (1 - esp[..., None]) + np.asarray(c1) * esp[..., None]) * gran[..., None]
    if cor_extra is not None:  # (H, W, 4): cor e intensidade de um tingimento (ex.: o que foi aprendido)
        k = cor_extra[..., 3:4]
        cor = cor * (1 - k) + cor_extra[..., :3] * k
    aro = np.clip(1 - n[..., 2], 0, 1) ** 1.5                 # bordas mais escuras e saturadas (luz rasante)
    gel = cor * (0.40 + 0.62 * dif[..., None]) * (1 - 0.35 * aro[..., None]) * brilho
    # sombra do gel no ágar (luz vem de cima à esquerda) e luz espalhada dentro do gel
    sh = gaussian_filter(np.roll(np.roll(alfa, 5, 0), 4, 1), 5)
    base = fundo * (1 - 0.45 * sh[..., None])
    out = base * (1 - alfa[..., None]) + gel * alfa[..., None]
    sss = gaussian_filter(alfa * (0.4 + esp), 9)[..., None] * cor * 0.22 * brilho
    out = out + sss + spec[..., None] * alfa[..., None] * 0.42
    if foco is not None:  # profundidade de campo: desfoca longe da faixa em foco (y0, faixa)
        y0, faixa = foco
        borr = gaussian_filter(out, (4.5, 4.5, 0))
        yy = np.abs(np.arange(H) - y0) / faixa
        k = np.clip(yy - 0.4, 0, 1)[:, None, None]
        out = out * (1 - k) + borr * k
    return np.clip(out, 0, 1)


_TX = {}


def textura(H, W):
    """três campos de ruído fixos (forma irregular, umidade e grânulos), calculados uma vez por tamanho"""
    if (H, W) not in _TX:
        rng = np.random.default_rng(42)
        lo = zoom(gaussian_filter(rng.normal(0, 1, (H // 8, W // 8)), 3), 8, order=1)[:H, :W]
        mid = zoom(gaussian_filter(rng.normal(0, 1, (H // 4, W // 4)), 2.2), 4, order=1)[:H, :W]
        hi = gaussian_filter(rng.normal(0, 1, (H, W)), 0.9)
        _TX[(H, W)] = [x / (np.abs(x).std() * 2.5 + 1e-6) for x in (lo, mid, hi)]
    return _TX[(H, W)]


def para_png(img):
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def agar(W, H, seed=0, tom=(0.075, 0.07, 0.06), vinheta=0.55):
    """fundo de ágar escuro com textura fina e manchas suaves"""
    rng = np.random.default_rng(seed)
    n1 = gaussian_filter(rng.normal(0, 1, (H // 4, W // 4)), 6)
    n1 = zoom(n1, (H / n1.shape[0], W / n1.shape[1]), order=1)
    n2 = gaussian_filter(rng.normal(0, 1, (H, W)), 0.8)
    base = np.array(tom)[None, None, :] * (1 + 0.35 * n1[..., None] / (np.abs(n1).max() + 1e-6)) + 0.006 * n2[..., None]
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / (W * 0.75), (yy - H / 2) / (H * 0.62))
    return np.clip(base * (1 - vinheta * np.clip(r - 0.35, 0, 1)[..., None]), 0, 1).astype(np.float32)
