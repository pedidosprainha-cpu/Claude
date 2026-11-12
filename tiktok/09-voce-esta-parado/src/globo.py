"""Globo noturno girando, a partir do Black Marble 2016 da NASA (luzes das cidades, domínio público).

Projeção ortográfica feita aqui (numpy), com escurecimento na borda, atmosfera azul e um fino crescente
iluminado pelo Sol. A Terra gira de oeste para leste, então a longitude central diminui com o tempo.
Saída: build/shots/<nome>/00001.png (fundo transparente) e build/shots/<nome>/params.json
(longitude/latitude centrais e raio de cada quadro, para o render.js desenhar o Equador, o Brasil etc.)
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, gaussian_filter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "shots"
Image.MAX_IMAGE_PIXELS = None
TEX = np.asarray(Image.open(ROOT / "assets" / "terra_noite.jpg").convert("RGB")).astype(np.float32) / 255
TH, TW = TEX.shape[:2]
SIZE = 1080  # quadro quadrado; o render.js posiciona

# nome: quadros, (lon0 início, lon0 fim), lat0, raio (px)
GLOBOS = {
    "gira": (240, (-5.0, -62.0), -12.0, 470),      # a Terra gira e o Brasil entra no centro
    "volta": (330, (-46.6, -100.0), -23.5, 470),    # para o "metade da volta ao mundo" e o fecho
}


def ease(p):
    return p * p * (3 - 2 * p)


def render(lon0, lat0, R):
    n = SIZE
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    X = (x - n / 2) / R
    Y = -(y - n / 2) / R
    rho2 = X * X + Y * Y
    inside = rho2 <= 1
    Z = np.sqrt(np.clip(1 - rho2, 0, 1))
    phi0, lam0 = math.radians(lat0), math.radians(lon0)
    # inversa da ortográfica
    lat = np.arcsin(np.clip(Z * math.sin(phi0) + Y * math.cos(phi0), -1, 1))
    lon = lam0 + np.arctan2(X, Z * math.cos(phi0) - Y * math.sin(phi0))
    u = ((lon / (2 * math.pi) + 0.5) % 1.0) * TW
    v = (0.5 - lat / math.pi) * TH
    rgb = np.stack([map_coordinates(TEX[..., c], [v, u], order=1, mode="wrap") for c in range(3)], -1)
    # realce das luzes e um tom azul-noite no oceano/terra
    rgb = np.clip(rgb * 1.25, 0, 1)
    rgb = rgb + np.array([0.012, 0.022, 0.05]) * (1 - rgb.max(-1, keepdims=True))
    # escurecimento na borda e crescente iluminado pelo Sol (vindo da direita, um pouco de cima)
    limb = (0.35 + 0.65 * Z)[..., None]
    sun = np.array([0.93, 0.18, -0.32]); sun /= np.linalg.norm(sun)
    ndot = (X * sun[0] + Y * sun[1] + Z * sun[2])
    day = np.clip((ndot - 0.55) / 0.45, 0, 1) ** 1.6
    rgb = rgb * limb + day[..., None] * np.array([0.55, 0.72, 1.0]) * 0.55
    # atmosfera: anel azul fora do disco + brilho na borda interna
    r = np.sqrt(rho2)
    atm_out = np.exp(-((r - 1) / 0.035) ** 2) * (r > 1) + np.clip(1 - (r - 1) / 0.09, 0, 1) * (r > 1) * 0.35
    atm_in = np.clip((r - 0.93) / 0.07, 0, 1) * inside
    glow = (atm_out + 0.5 * atm_in)[..., None] * np.array([0.35, 0.6, 1.0]) * (0.55 + 0.45 * np.clip((X * sun[0] + Y * sun[1]) / np.maximum(r, 1e-3) * 0.5 + 0.5, 0, 1))[..., None]
    alpha = np.clip(inside.astype(np.float32) + np.clip(atm_out * 1.2, 0, 1), 0, 1)
    out = np.clip(np.where(inside[..., None], rgb, 0) + glow, 0, 1)
    out[..., :] = gaussian_filter(out, sigma=(0.35, 0.35, 0))
    rgba = np.concatenate([out, alpha[..., None]], -1)
    return (rgba * 255).astype(np.uint8)


def run(name):
    nfr, (l0, l1), lat0, R = GLOBOS[name]
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    params = []
    for k in range(nfr):
        p = k / (nfr - 1)
        lon0 = l0 + (l1 - l0) * (0.15 * p + 0.85 * ease(p)) if name == "gira" else l0 + (l1 - l0) * p
        Image.fromarray(render(lon0, lat0, R), "RGBA").save(d / f"{k + 1:05d}.png", compress_level=1)
        params.append({"lon0": lon0, "lat0": lat0, "R": R})
    (d / "params.json").write_text(json.dumps(params))
    print(name, nfr, "quadros")


if __name__ == "__main__":
    for n in sys.argv[1:] or GLOBOS:
        run(n)
