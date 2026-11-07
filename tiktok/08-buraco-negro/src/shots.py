"""Tomadas verticais (1080x1920, 30 qps) recortadas das simulações 360° da NASA (SVS 14576).

Cada tomada é uma câmera virtual dentro do filme equirretangular de 8K (filtro v360 do ffmpeg),
com direção (yaw/pitch) e campo de visão animados quadro a quadro em função do tempo do filme.
Saída: build/shots/<nome>/00001.jpg ... (o quadro k corresponde ao tempo src0 + (k-1)/30 do filme)

Os filmes ficam fora do repositório (são grandes); src/baixar.sh baixa tudo.
"""
import math, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOOT = Path(os.environ.get("FOOTAGE", ROOT / "footage"))
OUT = ROOT / "build" / "shots"
PLUNGE = FOOT / "14576_BH_Plunge_Rectilinear_8192x4096_60.mp4"
FLYBY = FOOT / "14576_BH_FlyBy_Rectilinear_8192x4096_60.mp4"
PANO = ROOT / "assets" / "via_lactea_360.jpg"
W, H, FPS = 1080, 1920, 30


def hfov(v):  # campo horizontal para 9:16
    return 2 * math.degrees(math.atan(math.tan(math.radians(v / 2)) * W / H))


def ease(p):
    p = min(1, max(0, p))
    return p * p * (3 - 2 * p)


def interp(keys, t):
    """keys: [(t, valor), ...] com suavização entre os pontos"""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return keys[-1][1]


SHOTS = {
    # aproximação, olhando para a frente (gancho, rebobinar e "a queda")
    "aprox": dict(src=PLUNGE, t0=0.0, t1=18.0, yaw=[(0, 0)], pitch=[(0, 0)], fov=[(0, 70)]),
    # o "chapéu": disco visto por cima e por baixo ao mesmo tempo
    "luz": dict(src=FLYBY, t0=2.0, t1=10.5, yaw=[(0, 0)], pitch=[(0, -13)], fov=[(0, 38)]),
    # plano-sequência: cruza o horizonte e olha para cima, onde o universo encolhe
    "mergulho": dict(src=PLUNGE, t0=36.0, t1=58.6, yaw=[(0, 0)],
                     pitch=[(36, 0), (40.5, 10), (42.6, 32), (44.5, 56), (47, 75), (49, 86), (52, 90), (58.6, 90)],
                     fov=[(0, 86)]),
    # passa raspando e escapa: chicote de 180° para ver o buraco negro ficando para trás
    "escape": dict(src=FLYBY, t0=42.0, t1=66.3, yaw=[(42, 0), (49.6, 0), (50.5, 180), (66.3, 180)],
                   pitch=[(0, 0)], fov=[(0, 72)]),
}


def run_video(name, s):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    n = int(round((s["t1"] - s["t0"]) * FPS))
    # cada comando refaz o mapa de projeção (caro): só manda o que muda, e só quando muda.
    # Atenção: no v360, yaw/pitch enviados por comando são RELATIVOS à orientação atual,
    # então mandamos a diferença em relação ao quadro anterior (uma rotação por eixo por tomada).
    cmds, last = [], {}
    for k in range(n):
        tt = s["t0"] + k / FPS
        parts = []
        for key in ("yaw", "pitch"):
            v = round(interp(s[key], tt), 3)
            if k and abs(v - last[key]) > 1e-6:
                parts.append(f"v360@cam {key} {v - last[key]:.4f}")
            last[key] = v
        if parts:
            cmds.append(f"{k / FPS:.4f} " + ", ".join(parts) + ";")
    animado = bool(cmds)
    cf = d / "cmd.txt"
    cf.write_text("\n".join(cmds) + "\n")
    v0 = interp(s["fov"], s["t0"])
    vf = ((f"fps={FPS},sendcmd=f={cf}," if animado else f"fps={FPS},") +
          f"v360@cam=e:flat:w={W}:h={H}:interp={'cubic' if animado else 'lanczos'}:"
          f"yaw={interp(s['yaw'], s['t0'])}:pitch={interp(s['pitch'], s['t0'])}:v_fov={v0}:h_fov={hfov(v0)}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["t0"]), "-i", str(s["src"]), "-t", str(s["t1"] - s["t0"]),
                    "-vf", vf, "-q:v", "2", str(d / "%05d.jpg")], check=True)
    print(name, n, "quadros")


def run_pano():
    """aproximação até o centro da galáxia no panorama 360° do ESO (o centro galáctico fica no centro da imagem)"""
    d = OUT / "pano"
    d.mkdir(parents=True, exist_ok=True)
    n = 90
    for k in range(n):
        u = k / (n - 1)
        v = 118 * math.pow(36 / 118, u)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(PANO), "-frames:v", "1", "-vf",
                        f"v360=e:flat:w={W}:h={H}:interp=lanczos:yaw=0:pitch=0:v_fov={v:.3f}:h_fov={hfov(v):.3f}",
                        "-q:v", "2", str(d / f"{k + 1:05d}.jpg")], check=True)
    print("pano", n, "quadros")


if __name__ == "__main__":
    which = sys.argv[1:] or list(SHOTS) + ["pano"]
    for name in which:
        if name == "pano":
            run_pano()
        else:
            run_video(name, SHOTS[name])
