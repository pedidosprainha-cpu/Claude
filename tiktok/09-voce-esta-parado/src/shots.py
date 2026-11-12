"""Tomadas verticais (1080x1920, 30 qps) recortadas de vídeos 4K da NASA (domínio público).

Lê só os trechos necessários direto do servidor da NASA (requisições por intervalo de bytes), sem baixar
os arquivos inteiros (16 GB e 5,6 GB):
- "4K Earth Views Extended Cut for Earth Day 2021" (jsc2021m000138): a Terra vista da Estação Espacial
- "Step Inside the Station 4K Clean": a tripulação por dentro da Estação

As vistas da Terra são aceleradas (time-lapse) para dar a sensação de velocidade.
Saída: build/shots/<nome>/00001.jpg ...
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "shots"
EV = ("https://images-assets.nasa.gov/video/jsc2021m000138_4K_Earth_Views_Extended_Cut_for_Earth_Day_%202021_210422-4KMP4/"
      "jsc2021m000138_4K_Earth_Views_Extended_Cut_for_Earth_Day_%202021_210422-4KMP4~orig.mp4")
TOUR = "https://images-assets.nasa.gov/video/Step_Inside_the_Station-4K-Clean/Step_Inside_the_Station-4K-Clean~orig.mp4"
W, H, FPS = 1080, 1920, 30

# nome: (fonte, início (s), duração no original (s), aceleração, centro horizontal do recorte 0..1)
SHOTS = {
    "limbo":    (EV, 9 * 60 + 5, 80, 8, 0.55),     # curvatura da Terra contra o espaço negro
    "nuvens":   (EV, 16 * 60 + 30, 180, 12, 0.5),  # Terra curva com nuvens
    "paineis":  (EV, 29 * 60 + 40, 110, 8, 0.66),  # painéis solares da Estação sobre a Terra
    "montanha": (EV, 48 * 60 + 10, 180, 12, 0.5),  # montanhas nevadas e o horizonte
    "flutua":   (TOUR, 4 * 60 + 27, 18, 1, 0.5),   # tripulação flutuando no módulo
    "flutua2":  (TOUR, 0, 9, 1, 0.42),             # astronauta flutuando
    "cupula":   (TOUR, 14 * 60 + 6, 16, 1, 0.5),   # a janela da Cúpula com a Terra
    "estacao":  (TOUR, 14 * 60 + 36, 11, 1, 0.5),  # a Estação vista de fora, sobre a Terra
}


def run(name):
    src, t0, dur, k, cx = SHOTS[name]
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    cw = 2160 * 9 // 16
    vf = (f"setpts=PTS/{k},fps={FPS},crop={cw}:2160:'max(0,min(iw-{cw},iw*{cx}-{cw}/2))':0,"
          f"scale={W}:{H}:flags=lanczos")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(dur), "-i", src, "-an",
                    "-vf", vf, "-q:v", "2", str(d / "%05d.jpg")], check=True)
    print(name, len(list(d.glob("*.jpg"))), "quadros")


if __name__ == "__main__":
    for n in sys.argv[1:] or SHOTS:
        run(n)
