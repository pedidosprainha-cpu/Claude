"""Trilha original e efeitos sonoros sintetizados (sem samples de terceiros).

Saídas: build/musica.wav e build/sfx.wav (48 kHz, estéreo)
"""
import json, math
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
SR = 48000
TL = json.loads((B / "timeline.json").read_text())
T = TL["total"]
N = int(T * SR)
L = TL["lines"]
rng = np.random.default_rng(42)


def Wt(line, i, k="t0"):
    return L[line]["words"][i][k]


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


def env_points(points):
    """Envelope linear por pontos [(t, v), ...] amostrado na taxa de áudio."""
    t = np.arange(N) / SR
    ts, vs = zip(*points)
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


def saw(f, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((f * t + phase) % 1.0) - 1


def adsr(n, a, r, sus=1.0):
    e = np.ones(n, np.float32) * sus
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, sus, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


# ---------------------------------------------------------------- harmonia
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [  # Am  F  C/G  G
    ([220.0, 261.63, 329.63], 55.0),
    ([174.61, 220.0, 261.63], 43.65),
    ([196.0, 261.63, 329.63], 65.41),
    ([196.0, 246.94, 293.66], 49.0),
]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


# ---------------------------------------------------------------- stems
def make_pad():
    out = np.zeros((N, 2), np.float32)
    nb = int(math.ceil(T / BAR)) + 1
    for b in range(nb):
        t0 = b * BAR
        notes, root = CHORDS[b % 4]
        n = int((BAR + 0.8) * SR)
        e = adsr(n, 0.5, 0.8)
        for f in notes + [root * 2]:
            for ch, det in ((0, -0.004), (1, 0.004)):
                v = sum(saw(f * (1 + det * k), n, rng.random()) for k in (-1, 0, 1)) / 3
                add_ch = np.zeros((n, 2), np.float32)
                add_ch[:, ch] = v * e * 0.16
                add(out, add_ch, t0)
    return lp(out, 1400)


def make_shimmer():
    out = np.zeros((N, 2), np.float32)
    nb = int(math.ceil(T / BAR)) + 1
    for b in range(nb):
        notes, _ = CHORDS[b % 4]
        n = int((BAR + 1.0) * SR)
        tt = np.arange(n) / SR
        e = adsr(n, 0.8, 1.0)
        for i, f in enumerate(notes):
            v = np.sin(2 * np.pi * f * 4 * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * (3 + i) * tt))
            add(out, (v * e * 0.06).astype(np.float32), b * BAR, pan=(-0.6, 0.0, 0.6)[i])
    return out


def make_arp(bright):
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    pattern = [0, 1, 2, 3, 2, 1, 0, 2]
    for k in range(int(T / step) + 1):
        t0 = k * step
        notes, root = chord_at(t0)
        seq = [notes[0] * 2, notes[1] * 2, notes[2] * 2, notes[0] * 4]
        f = seq[pattern[k % 8]]
        n = int(0.45 * SR)
        tt = np.arange(n) / SR
        v = (0.6 * saw(f, n) + 0.4 * np.sign(np.sin(2 * np.pi * f * tt))) * np.exp(-tt / (0.16 if bright else 0.12))
        add(out, v.astype(np.float32), t0, 1.0 if not bright else 0.5, pan=0.35 if k % 2 else -0.35)
    return lp(out, 4200 if bright else 900)


def make_bass():
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    for k in range(int(T / step) + 1):
        t0 = k * step
        _, root = chord_at(t0)
        n = int(0.32 * SR)
        tt = np.arange(n) / SR
        v = np.tanh(2.2 * np.sin(2 * np.pi * root * 2 * tt)) * np.exp(-tt / 0.16) * adsr(n, 0.005, 0.05)
        add(out, v.astype(np.float32), t0, 0.15)
    return lp(out, 500)


def kick():
    n = int(0.5 * SR)
    tt = np.arange(n) / SR
    f = 48 + 100 * np.exp(-tt / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    v = np.sin(ph) * np.exp(-tt / 0.22)
    v[:200] += rng.normal(0, 0.3, 200) * np.linspace(1, 0, 200)
    return v.astype(np.float32)


def make_kicks():
    out = np.zeros((N, 2), np.float32)
    k = kick()
    for b in range(int(T / BEAT) + 1):
        add(out, k, b * BEAT, 0.25)
    return out


def make_ticks():
    out = np.zeros((N, 2), np.float32)
    n = int(0.03 * SR)
    for k in range(int(T / (BEAT / 2)) + 1):
        v = hp(rng.normal(0, 1, n), 3500) * np.exp(-np.arange(n) / SR / 0.006)
        add(out, v.astype(np.float32), k * BEAT / 2, 0.32 if k % 2 == 0 else 0.18, pan=0.25 if k % 2 else -0.25)
    return out


# ---------------------------------------------------------------- efeitos
def riser(dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    p = tt / dur
    noise = rng.normal(0, 1, n)
    lo = hp(noise, 300)
    hi = hp(noise, 3000)
    nz = lo * (1 - p) * 0.5 + hi * p
    f = 180 * np.power(1600 / 180, p)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    v = (0.5 * nz + 0.5 * tone) * np.power(p, 2.2)
    return v.astype(np.float32)


def impact(size=1.0):
    n = int(2.4 * SR)
    tt = np.arange(n) / SR
    f = 34 + 60 * np.exp(-tt / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (0.9 * size))
    crash = lp(rng.normal(0, 1, n), 5000) * np.exp(-tt / (0.35 * size)) * 0.5
    return np.tanh(1.5 * (boom + crash)).astype(np.float32)


def whoosh(dur=0.3, lo=400, hi=3500):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    a = bp(noise, lo, lo * 2.5)
    b = bp(noise, hi / 2.5, hi)
    p = tt / dur
    v = (a * (1 - p) + b * p) * np.sin(np.pi * p) ** 1.5
    return v.astype(np.float32)


def rewind(dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = 900 + 600 * np.sin(2 * np.pi * 13 * tt) + 400 * np.sin(2 * np.pi * 3.1 * tt)
    v = saw(1, n) * 0
    v = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + rng.normal(0, 0.4, n)
    v = bp(v, 600, 5000) * (0.6 + 0.4 * np.sin(2 * np.pi * 21 * tt)) * adsr(n, 0.05, 0.12)
    return v.astype(np.float32)


def scratch():
    n = int(0.42 * SR)
    tt = np.arange(n) / SR
    p = tt / tt[-1]
    f = 300 + 1700 * np.sin(np.pi * p) ** 2 * (1 - 0.6 * p)
    v = saw(1, n) * 0
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + bp(rng.normal(0, 1, n), 800, 4000) * 0.6
    v *= adsr(n, 0.01, 0.15)
    thump = np.sin(2 * np.pi * np.cumsum(70 + 80 * np.exp(-tt / 0.03)) / SR) * np.exp(-tt / 0.15)
    return (v + thump).astype(np.float32)


def ding(f=1318.5):
    n = int(0.7 * SR)
    tt = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt / 0.18)
    return v.astype(np.float32)


def click():
    n = int(0.06 * SR)
    tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.004)).astype(np.float32)


def main():
    hook_end = L["hook"]["end"]
    rew1 = (hook_end + 0.25, hook_end + 0.95)
    mito0 = Wt("mito", 0)
    errado = Wt("errado", 0)
    explode = Wt("licao", 8)
    moon = TL["cross"]["lua"]
    sun = TL["cross"]["sol"][0]
    uni = TL["cross"]["universo"][0]
    end = T

    # ---- intensidades por stem (t, nível) ----
    E = {
        "pad": env_points([(0, 0.55), (rew1[0], 0.55), (rew1[0] + 0.1, 0), (rew1[1], 0), (rew1[1] + 0.4, 0.6),
                           (L["f23"]["start"], 0.55), (moon[1], 0.7), (L["f103"]["end"], 0.8), (mito0 + 0.4, 0.35),
                           (errado - 0.05, 0.35), (errado + 0.02, 0), (L["britney"]["start"], 0), (L["britney"]["start"] + 0.5, 0.4),
                           (explode, 0.55), (end - 1.2, 0.5), (end, 0.4)]),
        "shimmer": env_points([(0, 0), (moon[1] - 0.1, 0), (moon[1] + 0.3, 1), (L["f103"]["end"] + 0.3, 1), (mito0 + 0.3, 0),
                               (explode, 0), (explode + 0.2, 0.8), (end, 0.5)]),
        "arp_dark": env_points([(0, 0.7), (rew1[0], 0.7), (rew1[0] + 0.1, 0), (L["dobra"]["start"], 0), (L["dobra"]["start"] + 0.6, 0.6),
                                (L["f10"]["start"], 0.7), (L["f23"]["start"], 0.3), (L["f23"]["start"] + 0.5, 0), (mito0, 0),
                                (L["britney"]["start"], 0), (L["britney"]["start"] + 0.3, 0.7), (L["licao"]["start"], 0.7),
                                (explode, 0.2), (end, 0.5)]),
        "arp_bright": env_points([(0, 0), (L["f17"]["start"], 0), (L["f23"]["start"], 0.8), (L["f103"]["end"], 0.9), (mito0, 0),
                                  (L["licao"]["start"], 0), (explode, 0.8), (end - 0.8, 0.6), (end, 0.4)]),
        "bass": env_points([(0, 0), (L["f10"]["start"], 0), (L["f10"]["start"] + 0.3, 0.5), (L["f23"]["start"], 0.8),
                            (L["f103"]["end"], 0.9), (mito0, 0.9), (mito0 + 0.3, 0), (L["britney"]["start"] + 0.2, 0),
                            (L["britney"]["start"] + 0.5, 0.5), (explode, 0.7), (end - 0.6, 0.5), (end, 0.2)]),
        "kick": env_points([(0, 0), (L["f23"]["start"] - 0.1, 0), (L["f23"]["start"], 0.9), (moon[1] - 1.2, 0.9), (moon[1] - 1.1, 0),
                            (moon[1], 0), (moon[1] + 0.05, 1), (L["f103"]["end"], 1), (mito0, 0), (L["rolo"]["start"], 0),
                            (L["rolo"]["start"] + 0.05, 0.6), (explode - 1.4, 0.6), (explode - 1.3, 0), (explode, 0), (explode + 0.05, 0.8),
                            (end - 1.0, 0.8), (end - 0.9, 0)]),
        "ticks": env_points([(0, 0), (rew1[1], 0), (rew1[1] + 0.3, 0.8), (L["f23"]["start"], 0.6), (moon[1], 0.4),
                             (L["f103"]["end"], 0.4), (mito0 + 0.5, 0.9), (errado - 0.05, 0.9), (errado, 0), (L["britney"]["start"], 0),
                             (L["britney"]["start"] + 0.3, 0.4), (end, 0.3)]),
    }
    stems = {
        "pad": make_pad(), "shimmer": make_shimmer(), "arp_dark": make_arp(False), "arp_bright": make_arp(True),
        "bass": make_bass(), "kick": make_kicks(), "ticks": make_ticks(),
    }
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    # leve "cola" e limite
    music = np.tanh(music * 1.2) / 1.2

    # ---- efeitos ----
    sfx = np.zeros((N + SR * 3, 2), np.float32)
    # gancho: foguete até a Lua
    r0 = Wt("hook", 7)
    add(sfx, riser(moon[0] - r0), r0, 0.15)
    add(sfx, whoosh(moon[0] - r0, 300, 6000), r0, 0.35)
    add(sfx, impact(1.0), moon[0], 0.2)
    add(sfx, ding(1760), moon[0] + 0.05, 0.12)
    # dobras da folha de frente
    for tt in (Wt("hook", 2) + 0.05, Wt("hook", 5)):
        add(sfx, whoosh(0.35, 500, 2500), tt, 0.25)
    # rebobinar
    add(sfx, rewind(rew1[1] - rew1[0] + 0.15), rew1[0] - 0.05, 0.25)
    add(sfx, rewind(1.1), mito0 - 0.05, 0.25)
    # passos de dobra
    for s in TL["steps"]:
        if s["t"] > rew1[1] and s["gap"] >= 0.09:
            add(sfx, whoosh(min(0.32, s["gap"] + 0.1), 600, 3000), s["t"], 0.3 if s["gap"] > 0.2 else 0.2, pan=rng.uniform(-0.3, 0.3))
    # marcos
    marcos_t = []
    for f, title in [(7, ""), (10, ""), (14, ""), (17, ""), (23, ""), (27, ""), (30, ""), (32, "")]:
        for i, c in enumerate(TL["count"]):
            if i / TL["fps"] > L["mentira"]["start"] and c >= f:
                marcos_t.append(i / TL["fps"])
                break
    for i, tt in enumerate(marcos_t):
        add(sfx, ding([1046.5, 1174.7, 1318.5, 1396.9, 1568.0, 1760.0, 1975.5, 2093.0][i]), tt, 0.1)
    # Lua (principal): riser + impacto
    r1 = Wt("f42", 2)
    add(sfx, riser(moon[1] - r1), r1, 0.16)
    add(sfx, impact(1.3), moon[1], 0.24)
    # Sol e universo
    add(sfx, whoosh(1.0, 300, 5000), Wt("f51", 0), 0.3)
    add(sfx, impact(0.6), sun, 0.12)
    r2 = L["f103"]["start"] - 0.1
    add(sfx, riser(uni - r2), r2, 0.14)
    add(sfx, whoosh(uni - r2, 200, 8000), r2, 0.4)
    add(sfx, impact(1.5), uni, 0.22)
    # mito / errado
    add(sfx, whoosh(0.4, 300, 1500), Wt("mito", 4) - 0.15, 0.25)
    add(sfx, scratch(), errado - 0.05, 0.2)
    add(sfx, impact(0.4), errado + 0.02, 0.12)
    # recorde
    add(sfx, whoosh(0.4, 400, 3000), L["britney"]["start"] + 0.1, 0.25)
    add(sfx, ding(2093.0), Wt("britney", 10), 0.16)
    add(sfx, ding(2637.0), Wt("britney", 10) + 0.08, 0.1)
    # rolo desenrolando
    add(sfx, whoosh(Wt("rolo", 10, "t1") - Wt("rolo", 2), 200, 1200), Wt("rolo", 2), 0.25)
    # lição: riser até explodir
    add(sfx, whoosh(0.4, 400, 3000), L["licao"]["start"] - 0.1, 0.2)
    add(sfx, riser(explode - Wt("licao", 6)), Wt("licao", 6), 0.14)
    add(sfx, impact(1.1), explode, 0.2)
    # CTA
    add(sfx, whoosh(0.4, 400, 3000), L["cta"]["start"] - 0.1, 0.22)
    add(sfx, click(), Wt("cta", 0) + 0.55, 0.5)
    add(sfx, ding(1568.0), Wt("cta", 0) + 0.58, 0.12)
    # volta para a folha (loop)
    add(sfx, whoosh(0.5, 300, 2500), T - 0.6, 0.18)
    sfx = sfx[:N]

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
