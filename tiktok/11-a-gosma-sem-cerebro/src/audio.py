"""Trilha original e desenho de som do vídeo 11 (Ciência #8). Tudo sintetizado, sem samples de terceiros.

Clima de laboratório curioso: Fá lídio a 90 BPM, marimba e kalimba (síntese modal), pads quentes, cordas e um
pulso grave que "respira" como o vaivém do protoplasma. Efeitos: bolhas e sons úmidos no crescimento, tique de
relógio no time-lapse, flocos de aveia caindo, um carrilhão genérico de estação nos trilhos de Tóquio, cristais
de sal e o brilho da fusão. Na pergunta final a música quase para.

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


# ---------------------------------------------------------------- harmonia: Fá lídio (Fmaj7 – Am – C – G), 90 BPM
BPM = 90
BEAT = 60 / BPM
BAR = 4 * BEAT
CH = {
    "Am": [110.00, 130.81, 164.81, 220.00], "F": [87.31, 130.81, 174.61, 220.00], "C": [98.00, 130.81, 164.81, 196.00],
    "G": [98.00, 123.47, 146.83, 196.00], "Fmaj7": [87.31, 130.81, 164.81, 220.00], "Dm": [73.42, 146.83, 174.61, 220.00],
    "E": [82.41, 123.47, 164.81, 207.65], "Bb": [58.27, 146.83, 174.61, 233.08], "Gm": [98.00, 146.83, 196.00, 233.08],
    "A": [110.00, 138.59, 164.81, 220.00],
}
PROG = ["Fmaj7", "Am", "C", "G"]


def chord_at(t):
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


def rumble(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = lp(rng.normal(0, 1, n), 120, 4) * 6 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    return (v * adsr(n, 0.3, 0.8)).astype(np.float32)


def cello(t0, dur, f, gain=0.18):
    n = int(dur * SR); tt = np.arange(n) / SR
    vib = 1 + 0.003 * np.sin(2 * np.pi * 5 * tt)
    ph = np.cumsum(f * vib) / SR
    v = (2 * (ph % 1) - 1) * adsr(n, 0.5, 0.8)
    out = np.zeros((N, 2), np.float32); add(out, lp(v, 900).astype(np.float32), t0, gain); return out


def piano(f, dur=2.6):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = sum(a * np.sin(2 * np.pi * f * k * tt) * np.exp(-tt / (1.6 / k)) for k, a in ((1, 1), (2, 0.35), (3, 0.12), (4, 0.06)))
    v[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    return lp(v, 2400).astype(np.float32) * adsr(n, 0, 0.2)


def make_piano(t0, t1, gain=1.0):
    out = np.zeros((N, 2), np.float32); step = BEAT
    for k in range(int(t0 / step), int(t1 / step) + 1):
        t = k * step; notes = chord_at(t)
        f = [notes[1] * 2, notes[2] * 2, notes[3] * 2, notes[2] * 2][k % 4]
        add(out, piano(f), t, 0.11 * gain, pan=0.25 if k % 2 else -0.25)
    return out


def music_box(t0, t1):
    out = np.zeros((N, 2), np.float32); step = BEAT / 2
    mel = [4, 2, 1, 2, 4, 3, 2, 1]
    for k in range(int(t0 / step), int(t1 / step) + 1):
        t = k * step; notes = chord_at(t); f = notes[1 + mel[k % 8] % 3] * 4 * (2 if mel[k % 8] > 3 else 1)
        add(out, bell(f, 1.6), t, 0.045, pan=0.3)
    return out


def pizz(t0, t1):
    out = np.zeros((N, 2), np.float32); step = BEAT / 2
    for k in range(int(t0 / step), int(t1 / step) + 1):
        if k % 4 == 3: continue
        t = k * step; notes = chord_at(t); f = notes[(k % 3) + 1] * 2
        n = int(0.35 * SR); tt = np.arange(n) / SR
        v = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.08)
        add(out, v.astype(np.float32), t, 0.12, pan=-0.3 if k % 2 else 0.3)
    return out


def timpani_roll(dur, f=55.0):
    n = int(dur * SR); tt = np.arange(n) / SR; out = np.zeros(n)
    for s in np.arange(0, dur, 0.055):
        m = n - int(s * SR); t2 = np.arange(m) / SR
        out[int(s * SR):] += np.sin(2 * np.pi * f * (1 + 0.1 * np.exp(-t2 / 0.05)) * t2) * np.exp(-t2 / 0.6) * (0.3 + 0.7 * s / dur)
    return (lp(out, 400) / 8 * adsr(n, 0.05, 0.2)).astype(np.float32)



# ---------------------------------------------------------------- instrumentos novos
def marimba(f, dur=1.2):
    """barra de marimba: parciais 1 : 3,93 : 9,2 com decaimentos diferentes + batida da baqueta"""
    n = int(dur * SR); tt = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.45) + 0.35 * np.sin(2 * np.pi * f * 3.93 * tt) * np.exp(-tt / 0.08)
         + 0.12 * np.sin(2 * np.pi * f * 9.2 * tt) * np.exp(-tt / 0.03))
    v += lp(rng.normal(0, 1, n), 3000) * np.exp(-tt / 0.004) * 0.15
    return (v * adsr(n, 0.001, 0.05)).astype(np.float32)


def kalimba(f, dur=1.6):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.6) + 0.2 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt / 0.05)
    return (v * adsr(n, 0.001, 0.1)).astype(np.float32)


def make_marimba(t0, t1, gain=1.0, pat=(0, 2, 1, 3, 2, 1, 3, 1)):
    out = np.zeros((N, 2), np.float32); step = BEAT / 2
    for k in range(int(t0 / step), int(t1 / step) + 1):
        t = k * step; nt = chord_at(t)
        f = [nt[1] * 2, nt[2] * 2, nt[3] * 2, nt[1] * 4][pat[k % 8]]
        add(out, marimba(f), t, 0.16 * gain * (1.0 if k % 2 == 0 else 0.75), pan=0.3 if k % 2 else -0.3)
    return out


def make_kalimba(t0, t1, gain=1.0):
    out = np.zeros((N, 2), np.float32); step = BEAT
    mel = [3, 2, 1, 2, 3, 3, 1, 0]
    for k in range(int(t0 / step), int(t1 / step) + 1):
        if k % 8 == 7: continue
        t = k * step; nt = chord_at(t); f = nt[1 + mel[k % 8] % 3] * 4
        add(out, kalimba(f), t + 0.02, 0.09 * gain, pan=0.45)
    return out


def pulso(dur, periodo=1.6):
    """batida grave e macia, como o vaivém do protoplasma"""
    out = np.zeros(int(dur * SR) + SR, np.float32)
    for s in np.arange(0, dur, periodo):
        n = int(0.7 * SR); tt = np.arange(n) / SR
        f = 46 + 20 * np.exp(-tt / 0.05)
        v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.22) * adsr(n, 0.01, 0.1)
        i = int(s * SR); out[i:i + n] += v.astype(np.float32)
    return out[: int(dur * SR)]


def bolhas(dur, taxa=9.0, lo=350, hi=1400):
    """bolhinhas úmidas: chirps curtos subindo de tom"""
    n = int(dur * SR); out = np.zeros((n, 2), np.float32)
    for _ in range(int(dur * taxa)):
        s = rng.integers(0, max(1, n - 4000)); m = int(rng.uniform(0.02, 0.05) * SR); tt = np.arange(m) / SR
        f0 = rng.uniform(lo, hi); f = f0 * (1 + 1.8 * tt / tt[-1])
        v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2
        ch = rng.uniform(0, 1); out[s:s + m, 0] += v * (1 - ch); out[s:s + m, 1] += v * ch
    return out * adsr(n, 0.3, 0.4)[:, None]


def umido(dur=0.6):
    """som úmido de gosma (ruído com formante que desliza)"""
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    v = rng.normal(0, 1, n)
    y = bp(v, 200, 900) * (1 - p) + bp(v, 500, 2200) * p
    return (y * np.sin(np.pi * p) ** 1.2 * 0.8).astype(np.float32)


def toque(f=420):
    """floco caindo no ágar"""
    n = int(0.25 * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.03) + lp(rng.normal(0, 1, n), 2500) * np.exp(-tt / 0.006) * 0.5
    return v.astype(np.float32)


def carrilhao():
    """carrilhão genérico de estação (duas notas, sintetizado)"""
    out = np.zeros(int(2.4 * SR), np.float32)
    for k, f in enumerate((659.25, 523.25)):
        b = bell(f, 1.8); i = int(k * 0.42 * SR); out[i:i + len(b)] += b * 0.8
    return out


def trilho(dur):
    """passagem de trem distante: clac-clac rítmico abafado"""
    n = int(dur * SR); out = np.zeros(n); tt = np.arange(n) / SR
    for s in np.arange(0.1, dur, 0.38):
        for d in (0, 0.11):
            i = int((s + d) * SR); m = int(0.06 * SR)
            if i + m < n: out[i:i + m] += lp(rng.normal(0, 1, m), 900) * np.exp(-np.arange(m) / (0.01 * SR))
    out += lp(rng.normal(0, 1, n), 200) * 0.3
    return (out * np.sin(np.pi * tt / dur) * 0.6).astype(np.float32)


def cristal():
    n = int(0.5 * SR); tt = np.arange(n) / SR; f = rng.uniform(3000, 6000)
    return (np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.05) * 0.5).astype(np.float32)


def brilho(dur=1.6):
    out = np.zeros((int(dur * SR) + SR, 2), np.float32)
    for k, f in enumerate([1046.5, 1318.5, 1568.0, 2093.0, 2637.0]):
        add(out, bell(f, 1.2), k * dur / 8, 0.08, pan=-0.5 + k * 0.25)
    return out


def risco():
    """tsk: risco na etiqueta"""
    n = int(0.16 * SR); tt = np.arange(n) / SR
    return (bp(rng.normal(0, 1, n), 2000, 7000) * np.exp(-tt / 0.04) * np.sin(np.pi * tt / tt[-1])).astype(np.float32)


def main():
    end = T
    ir = make_ir(3.0, 0.02)
    sc = {k: L[k]["start"] for k in TL["order"]}
    E = {
        "pad": env_points([(0, 0.5), (REW[0], 0.5), (REW[0] + 0.05, 0), (REW[1], 0), (REW[1] + 0.3, 0.45), (sc["toquio"], 0.55), (sc["regra"], 0.6),
                           (sc["memoria"], 0.5), (sc["fecho"], 0.6), (M["pergunta"], 0.35), (sc["cta"], 0.45), (end, 0.5)]),
        "strings": env_points([(0, 0.2), (REW[0], 0.25), (REW[0] + 0.05, 0), (sc["labirinto"], 0), (M["lab_curto"], 0.5), (sc["toquio"], 0.45), (M["trilhos"], 0.8),
                               (sc["regra"], 0.2), (sc["memoria"], 0.35), (M["aprende"], 0.7), (sc["fecho"], 0.5), (M["pergunta"], 0), (end - 0.6, 0), (end, 0.2)]),
        "ost": env_points([(0, 0.3), (REW[0], 0.3), (REW[0] + 0.05, 0), (sc["toquio"], 0), (M["liga"], 0.35), (sc["regra"], 0), (sc["memoria"], 0.25), (M["junta"], 0.4),
                           (sc["fecho"], 0), (end - 0.6, 0), (end, 0.3)]),
        "bass": env_points([(0, 0.4), (REW[0], 0.4), (REW[0] + 0.05, 0), (REW[1] + 0.3, 0.3), (sc["labirinto"], 0.35), (sc["toquio"], 0.5), (sc["regra"], 0.3),
                            (sc["memoria"], 0.45), (sc["fecho"], 0.3), (M["pergunta"], 0), (sc["cta"], 0.4), (end, 0.4)]),
    }
    stems = {"pad": make_pad(), "strings": make_strings(), "ost": make_ostinato(), "bass": make_bass()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music += make_marimba(0, REW[0], 0.9) + make_marimba(sc["labirinto"] - 0.2, sc["regra"] - 0.3, 0.8) + make_marimba(sc["memoria"], sc["fecho"], 0.7)
    music += make_kalimba(REW[1] + 0.2, sc["labirinto"]) + make_kalimba(sc["regra"], sc["memoria"], 0.8) + make_kalimba(sc["fecho"], M["pergunta"], 0.7)
    music += make_piano(M["pergunta"] - 0.2, sc["cta"] + 0.5, 0.8)
    music[int(REW[0] * SR): int(REW[1] * SR)] *= 0.1
    music = reverb(music, ir, 0.5)
    music = np.tanh(music * 1.15) / 1.15

    sfx = np.zeros((N + SR * 6, 2), np.float32)
    add(sfx, pulso(M["toquio_hook"]), 0, 0.22)
    add(sfx, umido(0.8), 0.0, 0.08); add(sfx, bolhas(M["toquio_hook"], 6), 0, 0.05)
    add(sfx, carrilhao(), M["toquio_hook"] + 0.15, 0.12, pan=0.2); add(sfx, whoosh(0.5, 300, 4000), M["toquio_hook"] - 0.25, 0.07)
    add(sfx, brilho(1.2), M["ensina"] - 0.05, 0.9)
    add(sfx, rewind(REW[1] - REW[0] + 0.15), REW[0] - 0.05, 0.22)
    # nome
    add(sfx, bolhas(sc["labirinto"] - sc["nome"], 5), sc["nome"], 0.04)
    for i in (9, 11, 13):
        add(sfx, risco(), Wt("nome", i) + 0.1, 0.07)
    add(sfx, blip(1318, 0.12), Wt("nome", 16), 0.06); add(sfx, blip(988, 0.12), Wt("nome", 21), 0.05)
    # labirinto
    add(sfx, sub_whump(), sc["labirinto"] - 0.1, 0.12)
    add(sfx, bolhas(M["lab_comida"] - M["lab_bota"], 10), M["lab_bota"], 0.05); add(sfx, umido(1.2), M["lab_bota"] + 0.3, 0.05)
    add(sfx, toque(380), M["lab_comida"] + 0.05, 0.12, pan=-0.4); add(sfx, toque(340), M["lab_comida"] + 0.3, 0.12, pan=0.4)
    sel1 = M["lab_curto"] + 0.7
    for k, tt_ in enumerate(np.arange(M["lab_largou"], sel1, 0.25)):
        add(sfx, tick(2400 if k % 2 else 2000), tt_, 0.035)
    for k in range(5):
        add(sfx, marimba(523.25 * 2 ** (-k / 6)), M["lab_largou"] + 0.15 + k * 0.32, 0.05, pan=(k % 2) * 0.6 - 0.3)
    add(sfx, brilho(1.0), M["lab_curto"] + 0.2, 0.7)
    # Tóquio
    for k in range(12):
        add(sfx, toque(rng.uniform(300, 480)), M["aveia"] + k * 0.05, 0.05, pan=rng.uniform(-0.7, 0.7))
    add(sfx, bolhas(M["trilhos"] - M["liga"], 8), M["liga"], 0.045)
    for k, tt_ in enumerate(np.arange(M["liga"], M["trilhos"] - 0.3, 0.25)):
        add(sfx, tick(2400 if k % 2 else 2000), tt_, 0.03)
    add(sfx, carrilhao(), M["trilhos"] - 0.05, 0.14); add(sfx, trilho(3.0), M["trilhos"], 0.12)
    # regra
    add(sfx, bolhas(sc["memoria"] - sc["regra"], 7, 500, 1600), sc["regra"], 0.04)
    add(sfx, sub_whump(), M["engrossa"], 0.1)
    n = int(0.9 * SR); tt = np.arange(n) / SR
    add(sfx, (np.sin(2 * np.pi * np.cumsum(700 * np.power(0.3, tt / 0.9)) / SR) * np.exp(-tt / 0.4) * 0.5).astype(np.float32), M["some"], 0.08)
    # memória
    add(sfx, umido(1.0), M["rastro"], 0.06); add(sfx, bolhas(M["sal"] - M["rastro"], 6), M["rastro"], 0.04)
    for k in range(10):
        add(sfx, cristal(), M["sal"] + 0.1 + k * 0.09, 0.05, pan=rng.uniform(-0.6, 0.6))
    for j, k in enumerate((0, 0.7, 1.4)):
        add(sfx, blip(784 * (1 + j * 0.25), 0.1), M["sal"] + 0.3 + k, 0.05)
    add(sfx, whoosh(0.9, 200, 3000), M["junta"] - 0.3, 0.08); add(sfx, umido(1.0), M["junta"] + 0.2, 0.07)
    add(sfx, brilho(1.6), M["aprende"] - 0.1, 1.0)
    # fecho
    add(sfx, impact(1.0), M["zero"] - 0.05, 0.12); add(sfx, braam(43.65, 2.5), M["zero"] - 0.05, 0.05)
    for k, f in enumerate([349.23, 440.0, 523.25, 659.25]):
        add(sfx, bell(f, 3.5), L["fecho"]["end"] + 0.1 + k * 0.1, 0.035)
    add(sfx, blip(1568, 0.2), Wt("cta", 0) + 0.6, 0.18)
    add(sfx, bell(2093, 1.5), Wt("cta", 0) + 0.63, 0.06)
    add(sfx, whoosh(0.7, 200, 3000), T - 0.7, 0.12)
    sfx = sfx[:N]
    sfx = reverb(sfx, make_ir(2.0, 0.015, seed=3), 0.3)

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    irv = make_ir(1.1, 0.012, damp=(7000, 2200), seed=7)
    wavfile.write(B / "ir_voz.wav", SR, (irv / np.abs(irv).max() * 0.9 * 32767).astype(np.int16))
    print("musica.wav, sfx.wav e ir_voz.wav prontos", T, "s")


if __name__ == "__main__":
    main()
