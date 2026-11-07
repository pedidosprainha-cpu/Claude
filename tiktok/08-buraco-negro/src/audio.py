"""Trilha original e desenho de som do vídeo 08 (Ciência #6). Tudo sintetizado, sem samples de terceiros.

Lá menor, 84 BPM. Recursos:
- reverb de convolução com resposta ao impulso sintética (sala grande, cauda de ~4 s)
- "braam" de trailer no gancho e graves profundos nos impactos
- ostinato pulsante que cresce durante a queda
- a trilha para como uma fita perdendo rotação em "…e congela na beira"
- silêncio total no instante em que se cruza o horizonte de eventos
- tom de Shepard (queda sem fim) dentro do horizonte
- tique-taque de dois relógios: o seu (desacelerando) e o de quem ficou

Saídas: build/musica.wav, build/sfx.wav e build/ir_voz.wav (48 kHz, estéreo)
"""
import json, math
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
SR = 48000
TL = json.loads((B / "timeline.json").read_text())
T = TL["total"]
N = int(T * SR)
L = TL["lines"]
M = TL["marks"]
REW = TL["rew"]
rng = np.random.default_rng(23)


def Wt(line, i, k="t0"):
    return L[line]["words"][i][k]


def lp(x, fc, o=2): return sosfilt(butter(o, fc, "low", fs=SR, output="sos"), x, axis=0)
def hp(x, fc, o=2): return sosfilt(butter(o, fc, "high", fs=SR, output="sos"), x, axis=0)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


def env_points(points, n=N):
    t = np.arange(n) / SR
    ts, vs = zip(*sorted(points))
    return np.interp(t, ts, vs).astype(np.float32)


def add(buf, x, t0, gain=1.0, pan=0.0):
    s = int(t0 * SR)
    if s >= len(buf) or s + len(x) <= 0:
        return
    if s < 0:
        x, s = x[-s:], 0
    x = x[: len(buf) - s]
    if x.ndim == 1:
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        buf[s:s + len(x), 0] += x * gain * l * 1.414
        buf[s:s + len(x), 1] += x * gain * r * 1.414
    else:
        buf[s:s + len(x)] += x * gain


def adsr(n, a, r, sus=1.0):
    e = np.ones(n, np.float32) * sus
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, sus, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


def saw(f, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((f * t + phase) % 1.0) - 1


# ---------------------------------------------------------------- reverb de convolução
def make_ir(dur=4.0, predelay=0.02, damp=(9000, 1800), seed=1):
    r = np.random.default_rng(seed)
    n = int(dur * SR); t = np.arange(n) / SR
    out = np.zeros((n + int(predelay * SR), 2), np.float32)
    for ch in range(2):
        noise = r.normal(0, 1, n)
        # amortecimento: agudos morrem antes (mistura de duas versões filtradas)
        bright, dark = lp(noise, damp[0]), lp(noise, damp[1])
        mix = bright * np.exp(-t / (dur * 0.12)) + dark * (1 - np.exp(-t / (dur * 0.12)))
        e = np.exp(-6.9 * t / dur)  # -60 dB no fim
        out[int(predelay * SR):, ch] = mix * e
    # reflexões iniciais
    for k in range(12):
        d = int((0.008 + r.random() * 0.06) * SR); out[d, k % 2] += (0.6 - k * 0.04)
    return out / np.sqrt((out ** 2).sum() / 2)


def reverb(x, ir, wet=0.35):
    y = np.zeros_like(x)
    for ch in range(2):
        y[:, ch] = fftconvolve(x[:, ch], ir[:, ch])[: len(x)]
    return x * (1 - wet * 0.5) + y * wet * 0.5


# ---------------------------------------------------------------- harmonia: Lá menor (Am – F – C – G), 84 BPM
BPM = 84
BEAT = 60 / BPM
BAR = 4 * BEAT
CH = {
    "Am": [110.00, 130.81, 164.81, 220.00], "F": [87.31, 130.81, 174.61, 220.00], "C": [98.00, 130.81, 164.81, 196.00],
    "G": [98.00, 123.47, 146.83, 196.00], "Fmaj7": [87.31, 130.81, 164.81, 220.00], "Dm": [73.42, 146.83, 174.61, 220.00],
    "E": [82.41, 123.47, 164.81, 207.65],
}
PROG = ["Am", "F", "C", "G"]
PROG_TWIST = ["F", "C", "G", "Am"]


def chord_at(t):
    if t >= Wt("twist", 0) - 0.4:
        k = int((t - (Wt("twist", 0) - 0.4)) // BAR) % 4; return CH[PROG_TWIST[k]]
    return CH[PROG[int(t // BAR) % 4]]


def make_pad():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 2):
        t0 = b * BAR; notes = chord_at(t0)
        n = int((BAR + 1.0) * SR); e = adsr(n, 0.8, 1.0)
        for f in notes:
            for ch, det in ((0, -0.004), (1, 0.004)):
                v = sum(saw(f * (1 + det * k), n, rng.random()) for k in (-1, 0, 1)) / 3
                x = np.zeros((n, 2), np.float32); x[:, ch] = v * e * 0.12
                add(out, x, t0)
    return lp(out, 1500)


def make_strings():
    """ensemble de cordas: saws com vibrato e ataque lento, oitava acima"""
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 2):
        t0 = b * BAR; notes = chord_at(t0)
        n = int((BAR + 1.2) * SR); tt = np.arange(n) / SR; e = adsr(n, 1.1, 1.0)
        for i, f in enumerate(notes[1:]):
            vib = 1 + 0.003 * np.sin(2 * np.pi * (5.2 + 0.3 * i) * tt + i)
            ph = np.cumsum(f * 2 * vib) / SR
            v = (2 * (ph % 1) - 1) * e * 0.06
            add(out, v.astype(np.float32), t0, pan=(-0.6, 0.0, 0.6)[i])
    return lp(hp(out, 180), 3200)


def make_choir():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 2):
        t0 = b * BAR; notes = chord_at(t0)
        n = int((BAR + 1.4) * SR); tt = np.arange(n) / SR; e = adsr(n, 1.0, 1.2)
        for i, f in enumerate(notes[1:]):
            vib = 1 + 0.004 * np.sin(2 * np.pi * 4.8 * tt + i * 2)
            ph = 2 * np.pi * np.cumsum(f * 2 * vib) / SR
            v = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph) + 0.06 * np.sin(5 * ph)) * e * 0.06
            add(out, v.astype(np.float32), t0, pan=(-0.5, 0.0, 0.5)[i])
    return lp(out, 2600)


def epiano(f, dur=1.8):
    n = int(dur * SR); tt = np.arange(n) / SR
    mod = 1.6 * np.exp(-tt / 0.18) * np.sin(2 * np.pi * f * tt)
    v = np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / 0.9) + 0.25 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt / 0.3)
    v[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    return (v * adsr(n, 0.0, 0.1)).astype(np.float32)


def make_pluck(t0, t1, gain=1.0):
    """arpejo de piano elétrico em semicolcheias"""
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2; pat = [0, 2, 1, 3, 2, 1, 3, 2]
    k0 = int(t0 / step)
    for k in range(k0, int(t1 / step) + 1):
        t = k * step; notes = chord_at(t)
        f = [notes[1] * 2, notes[2] * 2, notes[3] * 2, notes[1] * 4][pat[k % 8]]
        add(out, epiano(f, 1.4), t, 0.12 * gain, pan=0.35 if k % 2 else -0.35)
    return out


def make_ostinato():
    """pulso de colcheias (sintetizador filtrado), cresce na queda"""
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    for k in range(int(T / step) + 1):
        t = k * step; root = chord_at(t)[0]
        n = int(0.24 * SR); tt = np.arange(n) / SR
        v = saw(root, n) * np.exp(-tt / 0.09) * adsr(n, 0.003, 0.03)
        add(out, v.astype(np.float32), t, 0.16, pan=0.2 if k % 2 else -0.2)
    return lp(out, 900)


def make_bass():
    out = np.zeros((N, 2), np.float32)
    for k in range(int(T / BEAT) + 1):
        t = k * BEAT; root = chord_at(t)[0] / 2
        n = int(0.9 * SR); tt = np.arange(n) / SR
        v = np.tanh(2.2 * np.sin(2 * np.pi * root * tt)) * np.exp(-tt / 0.5) * adsr(n, 0.01, 0.1)
        add(out, v.astype(np.float32), t, 0.2)
    return lp(out, 300)


def tom(f=90):
    n = int(0.9 * SR); tt = np.arange(n) / SR
    ff = f * (1 + 0.6 * np.exp(-tt / 0.04))
    v = np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-tt / 0.28) + lp(rng.normal(0, 1, n), 1200) * np.exp(-tt / 0.03) * 0.3
    return v.astype(np.float32)


def make_toms():
    out = np.zeros((N, 2), np.float32)
    pat = [(0, 90), (1.5, 90), (2, 70), (3, 80), (3.5, 70)]
    for bar in range(int(T / BAR) + 1):
        for off, f in pat:
            add(out, tom(f), bar * BAR + off * BEAT, 0.3, pan=(f - 80) / 40)
    return out


def shepard(dur, base=55.0, down=True, rate=0.12):
    """tom de Shepard: parece cair (ou subir) para sempre"""
    n = int(dur * SR); tt = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(8):
        oc = (k + (-1 if down else 1) * rate * tt) % 8
        f = base * 2 ** oc
        amp = np.exp(-0.5 * ((oc - 4) / 1.5) ** 2)
        out += amp * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return (out / 4 * adsr(n, 1.0, 1.5)).astype(np.float32)


# ---------------------------------------------------------------- efeitos
def braam(f=55.0, dur=3.2):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = sum(saw(f * r * (1 + 0.003 * k), n, rng.random()) for k, r in enumerate((1, 1, 2, 3, 1.5)))
    k = np.exp(-tt / 0.35)  # o filtro abre no ataque e fecha devagar
    y = lp(v, 2600, 2) * k + lp(v, 220, 2) * (1 - k)
    return (np.tanh(1.8 * y) * adsr(n, 0.01, 1.5) * np.exp(-tt / 1.6)).astype(np.float32)


def impact(size=1.0):
    n = int(3.5 * SR); tt = np.arange(n) / SR
    f = 28 + 55 * np.exp(-tt / 0.09)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (1.1 * size))
    crack = lp(rng.normal(0, 1, n), 4000) * np.exp(-tt / (0.25 * size)) * 0.4
    return np.tanh(1.6 * (boom + crack)).astype(np.float32)


def sub_whump():
    n = int(2.5 * SR); tt = np.arange(n) / SR
    f = 24 + 30 * np.exp(-tt / 0.15)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.8) * adsr(n, 0.02, 0.3)).astype(np.float32)


def riser(dur, lo=150, hi=1800):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    noise = rng.normal(0, 1, n)
    nz = hp(noise, 400) * (1 - p) * 0.5 + hp(noise, 3500) * p
    f = lo * np.power(hi / lo, p)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return ((0.5 * nz + 0.5 * tone) * np.power(p, 2.0)).astype(np.float32)


def whoosh(dur=0.6, lo=300, hi=5000):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    noise = rng.normal(0, 1, n)
    v = (bp(noise, lo, lo * 2.5) * (1 - p) + bp(noise, hi / 2.5, hi) * p) * np.sin(np.pi * p) ** 1.5
    return v.astype(np.float32)


def rewind(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 900 + 600 * np.sin(2 * np.pi * 13 * tt) + 400 * np.sin(2 * np.pi * 3.1 * tt)
    v = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + rng.normal(0, 0.4, n)
    return (bp(v, 600, 5000) * (0.6 + 0.4 * np.sin(2 * np.pi * 21 * tt)) * adsr(n, 0.05, 0.12)).astype(np.float32)


def blip(f, d=0.12):
    n = int(d * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.035) * adsr(n, 0.002, 0.02)).astype(np.float32)


def tick(f=2600):
    n = int(0.05 * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.008) + 0.6 * np.sin(2 * np.pi * f * 0.62 * tt) * np.exp(-tt / 0.013)
    return (body + hp(rng.normal(0, 1, n), 3000) * np.exp(-tt / 0.002) * 0.6).astype(np.float32)


def bell(f, dur=2.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    mod = 2.0 * np.exp(-tt / 0.25) * np.sin(2 * np.pi * f * 3.5 * tt)
    return (np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / (dur * 0.4)) * adsr(n, 0.002, 0.05)).astype(np.float32)


def stretch(dur):
    """ruído metálico que desce de tom: o corpo sendo esticado"""
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    f = 900 * np.power(0.25, p)
    v = sum(np.sin(2 * np.pi * np.cumsum(f * r) / SR) * a for r, a in ((1, 1), (1.41, 0.5), (2.13, 0.35)))
    v *= 0.6 + 0.4 * np.sin(2 * np.pi * (12 - 8 * p) * tt)
    return (v * adsr(n, 0.3, 0.2) * 0.4 + bp(rng.normal(0, 1, n), 300, 2500) * 0.15 * p).astype(np.float32)


def tape_stop(x, t0, dur=1.3):
    """a trilha perde rotação até parar a partir de t0 (e fica em silêncio depois)"""
    s = int(t0 * SR); n_out = int(dur * SR)
    spd = np.linspace(1, 0, n_out) ** 1.3
    pos = s + np.cumsum(spd)
    seg = np.stack([np.interp(pos, np.arange(len(x)), x[:, c]) for c in range(2)], axis=1)
    y = x.copy(); y[s:s + n_out] = seg * np.linspace(1, 0.3, n_out)[:, None]; y[s + n_out:] = 0
    return y


def main():
    end = T
    ir = make_ir(4.2, 0.025)
    sc = {k: L[k]["start"] for k in TL["order"]}
    cross, blink, whip, fita, boom = M["cross"], M["blink"], M["whip"], M["fita"], M["boom"]
    dentro_end = L["fim"]["start"]
    # ------------------------------------------------ música (por seções)
    E = {
        "pad": env_points([(0, 0.55), (REW[0], 0.6), (REW[0] + 0.05, 0), (REW[1], 0), (REW[1] + 0.4, 0.5), (sc["queda"], 0.6), (sc["luz"], 0.65),
                           (sc["tempo"], 0.55), (cross - 0.05, 0.45), (cross, 0), (sc["dentro"], 0), (sc["dentro"] + 1.0, 0.6), (blink, 0.7), (blink + 0.02, 0),
                           (sc["twist"] - 0.3, 0), (sc["twist"] + 0.4, 0.6), (sc["fecho"], 0.75), (L["fecho"]["end"] + 0.5, 0.8), (sc["cta"], 0.5), (end - 0.6, 0.55), (end, 0.55)]),
        "strings": env_points([(0, 0.0), (boom, 0.2), (REW[0], 0.5), (REW[0] + 0.05, 0), (sc["tamanho"], 0), (sc["queda"], 0.35), (sc["luz"], 0.6), (sc["tempo"], 0.4),
                               (cross, 0), (sc["dentro"] + 1.0, 0), (sc["fim"], 0.7), (blink, 1.0), (blink + 0.02, 0), (sc["twist"] + 1.5, 0), (whip, 0.5),
                               (sc["fecho"], 0.8), (L["fecho"]["end"], 0.9), (sc["cta"], 0), (end, 0)]),
        "choir": env_points([(0, 0), (boom, 0.5), (REW[0], 0.4), (REW[0] + 0.05, 0), (M["eht"], 0), (M["eht"] + 0.6, 0.55), (sc["tamanho"] + 1, 0.2),
                             (sc["tempo"], 0), (cross, 0), (cross + 0.6, 0.5), (sc["dentro"], 0.8), (blink, 0.9), (blink + 0.02, 0),
                             (sc["fecho"], 0.5), (L["fecho"]["end"], 0.8), (sc["cta"], 0.2), (end, 0)]),
        "pluck": env_points([(0, 0), (REW[1], 0), (REW[1] + 0.3, 0.4), (sc["queda"], 0.7), (sc["luz"], 0.8), (sc["tempo"], 0.3), (fita, 0.2), (fita + 0.02, 0),
                             (whip, 0), (whip + 0.4, 0.8), (sc["fecho"], 0.6), (sc["cta"], 0.8), (end - 0.6, 0.3), (end, 0)]),
        "ost": env_points([(0, 0.35), (boom, 0.5), (REW[0], 0.5), (REW[0] + 0.05, 0), (sc["tamanho"], 0), (sc["queda"], 0.6), (sc["luz"], 0.8), (sc["tempo"], 0.5),
                           (fita, 0.4), (fita + 0.02, 0), (sc["fim"], 0), (sc["fim"] + 0.5, 0.6), (blink, 0.9), (blink + 0.02, 0), (end - 1.0, 0), (end, 0.35)]),
        "bass": env_points([(0, 0.3), (boom, 0.8), (REW[0], 0.6), (REW[0] + 0.05, 0), (REW[1] + 0.4, 0.35), (sc["queda"], 0.7), (sc["tempo"], 0.5), (cross, 0.4), (cross + 0.01, 0),
                            (sc["dentro"] + 1.0, 0.5), (blink, 0.8), (blink + 0.02, 0), (whip, 0), (whip + 0.4, 0.6), (sc["fecho"], 0.5), (sc["cta"], 0.5), (end, 0.3)]),
        "toms": env_points([(0, 0), (sc["queda"], 0), (sc["queda"] + 0.1, 0.5), (sc["luz"], 0.65), (sc["tempo"], 0), (sc["fim"], 0), (sc["fim"] + 0.5, 0.7), (blink, 0.9),
                            (blink + 0.02, 0), (end, 0)]),
    }
    stems = {"pad": make_pad(), "strings": make_strings(), "choir": make_choir(), "pluck": make_pluck(0, T), "ost": make_ostinato(),
             "bass": make_bass(), "toms": make_toms()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    # tom de Shepard (queda sem fim) dentro do horizonte
    add(music, shepard(blink - (cross + 0.4) + 0.2, 55, True), cross + 0.4, 0.22)
    # a trilha perde rotação em "…e congela na beira" e fica em silêncio até depois do horizonte
    music = tape_stop(music, fita + 0.05, 1.4)
    music[int((fita + 1.45) * SR): int((sc["cruza"] - 0.6) * SR)] *= 0
    music = reverb(music, ir, 0.55)
    music = np.tanh(music * 1.15) / 1.15

    # ------------------------------------------------ efeitos
    sfx = np.zeros((N + SR * 5, 2), np.float32)
    add(sfx, riser(boom - 0.1 + 0.4, 80, 900), -0.4, 0.12)
    add(sfx, braam(55.0), boom, 0.32); add(sfx, impact(1.3), boom, 0.22)
    for k, t in enumerate(np.arange(Wt("nasa", 5), Wt("nasa", 7, "t1"), 0.07)):
        add(sfx, blip(1800 + 300 * (k % 3), 0.05), t, 0.05)
    add(sfx, rewind(REW[1] - REW[0] + 0.15), REW[0] - 0.05, 0.24)
    add(sfx, whoosh(1.6, 120, 6000), REW[1] - 0.1, 0.2)
    add(sfx, bell(880, 3.0), M["eht"], 0.07); add(sfx, bell(1318.5, 3.0), M["eht"] + 0.08, 0.05)
    add(sfx, whoosh(0.9, 200, 5000), sc["tamanho"] - 0.45, 0.16)
    for k, w in enumerate((2, 6, 10, 15)):
        add(sfx, blip(1200 + 200 * k), Wt("tamanho", w), 0.07)
    add(sfx, whoosh(0.7, 150, 4000), sc["queda"] - 0.3, 0.18)
    add(sfx, impact(0.6), sc["queda"], 0.08)
    add(sfx, whoosh(0.5, 400, 7000), sc["luz"] - 0.25, 0.15)
    for w in (13, 16):
        add(sfx, bell(1760, 1.2), Wt("luz", w), 0.05)
    add(sfx, whoosh(1.2, 100, 2500), sc["tempo"] - 0.5, 0.15)
    # relógios: o seu (cada vez mais lento, visto de longe) e o de quem ficou (normal)
    t = sc["tempo"] - 0.2; gap = 0.5
    while t < fita + 0.9:
        add(sfx, tick(2600), t, 0.06, pan=-0.4); t += gap; gap *= 1.09 if t > sc["congela"] else 1.0
    t = sc["tempo"] - 0.2
    while t < fita + 1.6:
        add(sfx, tick(1900), t, 0.045, pan=0.4); t += 0.5
    add(sfx, impact(0.5), fita + 1.4, 0.05)
    # cruzar o horizonte: um grave surdo e nada mais
    add(sfx, sub_whump(), cross, 0.32)
    add(sfx, riser(cross - (sc["cruza"] - 0.3), 60, 400), sc["cruza"] - 0.3, 0.05)
    # lá dentro: esticar, e o piscar de olhos
    add(sfx, stretch(blink - Wt("fim", 11)), Wt("fim", 11), 0.12)
    add(sfx, riser(blink - Wt("fim", 14) + 0.1, 200, 3000), Wt("fim", 14), 0.14)
    add(sfx, impact(0.4), blink, 0.05)
    # reviravolta: o chicote da câmera e o "−36 min"
    add(sfx, whoosh(0.9, 300, 7000), whip - 0.1, 0.24, pan=0.3)
    for k in range(10):
        add(sfx, tick(2400), Wt("twist", 8) + k * 0.12, 0.03, pan=-0.3)
    add(sfx, bell(1046.5, 2.5), Wt("twist", 12), 0.08); add(sfx, bell(1568, 2.5), Wt("twist", 12) + 0.1, 0.05)
    add(sfx, whoosh(1.4, 100, 3000), sc["fecho"] - 0.5, 0.12)
    for k, f in enumerate([440.0, 523.25, 659.25, 880.0]):
        add(sfx, bell(f, 3.5), L["fecho"]["end"] + 0.1 + k * 0.09, 0.05)
    add(sfx, blip(1568, 0.2), Wt("cta", 0) + 0.6, 0.18)
    add(sfx, bell(2093, 1.5), Wt("cta", 0) + 0.63, 0.06)
    add(sfx, whoosh(0.7, 200, 3000), T - 0.7, 0.16)
    sfx = sfx[:N]
    sfx = reverb(sfx, make_ir(2.5, 0.015, seed=3), 0.35)

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    irv = make_ir(1.1, 0.012, damp=(7000, 2200), seed=7)
    wavfile.write(B / "ir_voz.wav", SR, (irv / np.abs(irv).max() * 0.9 * 32767).astype(np.int16))
    print("musica.wav, sfx.wav e ir_voz.wav prontos", T, "s")


if __name__ == "__main__":
    main()
