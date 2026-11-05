"""Trilha original boom-bap (estilo rap brasileiro do início dos anos 90) + efeitos, tudo sintetizado.

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
rng = np.random.default_rng(1992)


def Wt(line, i, k="t0"):
    return L[line]["words"][i][k]


def lp(x, fc, o=2): return sosfilt(butter(o, fc, "low", fs=SR, output="sos"), x, axis=0)
def hp(x, fc, o=2): return sosfilt(butter(o, fc, "high", fs=SR, output="sos"), x, axis=0)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


def env_points(points):
    t = np.arange(N) / SR
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


# ---------------------------------------------------------------- boom-bap a 90 BPM, swing
BPM = 90
BEAT = 60 / BPM
BAR = 4 * BEAT
SWING = 0.08
CH = [  # Dm9  Gm9  Bbmaj7  A7(b9)  — acordes de piano elétrico
    [146.83, 174.61, 220.00, 261.63, 329.63],
    [196.00, 233.08, 293.66, 349.23, 440.00],
    [233.08, 293.66, 349.23, 440.00],
    [220.00, 277.18, 329.63, 392.00, 466.16],
]
ROOTS = [73.42, 98.0, 58.27, 55.0]


def kick():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-tt / 0.04)) / SR) * np.exp(-tt / 0.28)
    v[:240] += rng.normal(0, 0.5, 240) * np.linspace(1, 0, 240)
    return np.tanh(1.6 * v).astype(np.float32)


def snare():
    n = int(0.35 * SR); tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, n), 900, 6500) * np.exp(-tt / 0.16) + np.sin(2 * np.pi * 180 * tt) * np.exp(-tt / 0.07) * 0.9
    return np.tanh(1.4 * v).astype(np.float32)


def hat():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (hp(rng.normal(0, 1, n), 6500) * np.exp(-tt / 0.018)).astype(np.float32)


KK, SN, HH = kick(), snare(), hat()


def drums():
    k = np.zeros((N, 2), np.float32); s = np.zeros((N, 2), np.float32); h = np.zeros((N, 2), np.float32)
    for bar in range(int(T / BAR) + 1):
        b0 = bar * BAR
        for pos in (0, 1.5 + (0.75 if bar % 2 else 0)):           # padrão de bumbo boom-bap
            add(k, KK, b0 + pos * BEAT, 0.6)
        add(k, KK, b0 + 2.5 * BEAT, 0.35)
        for pos in (1, 3):
            add(s, SN, b0 + pos * BEAT, 0.5)
        for e in range(8):
            sw = SWING * BEAT if e % 2 else 0
            add(h, HH, b0 + e * BEAT / 2 + sw, 0.18 if e % 2 == 0 else 0.11, pan=0.25)
    return k, s, h


def rhodes():
    out = np.zeros((N, 2), np.float32)
    for bar in range(int(T / BAR) + 1):
        notes = CH[bar % 4]
        for hit, (pos, dur) in enumerate([(0, 1.6), (2.5, 1.4)]):
            t0 = bar * BAR + pos * BEAT
            n = int(dur * SR); tt = np.arange(n) / SR
            v = sum(np.sin(2 * np.pi * f * tt + 0.6 * np.sin(2 * np.pi * f * 2 * tt) * np.exp(-tt / 0.3)) for f in notes)
            v = v * np.exp(-tt / 0.9) * (1 + 0.12 * np.sin(2 * np.pi * 5 * tt)) * adsr(n, 0.005, 0.2) / len(notes)
            add(out, v.astype(np.float32), t0, 0.22, pan=-0.15 if hit else 0.15)
    return lp(out, 2600)


def bass():
    out = np.zeros((N, 2), np.float32)
    pat = [(0, 1.0, 1.0), (1.5, 0.5, 1.0), (2.5, 0.75, 1.5), (3.5, 0.4, 1.0)]
    for bar in range(int(T / BAR) + 1):
        r = ROOTS[bar % 4]
        for pos, dur, mul in pat:
            n = int(dur * BEAT * SR); tt = np.arange(n) / SR
            v = np.tanh(1.8 * np.sin(2 * np.pi * r * mul * tt)) * adsr(n, 0.008, 0.06)
            add(out, v.astype(np.float32), bar * BAR + pos * BEAT, 0.3)
    return lp(out, 600)


def crackle():
    v = np.zeros(N, np.float32)
    idx = rng.integers(0, N, int(T * 40))
    v[idx] = rng.normal(0, 1, len(idx)) * 0.9
    v = hp(v, 1500) + lp(rng.normal(0, 0.02, N), 3000)
    return np.stack([v, np.roll(v, 37)], axis=1).astype(np.float32)


# ---------------------------------------------------------------- efeitos
def scratch(dur=0.35):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    f = 300 + 1600 * np.abs(np.sin(np.pi * 2.2 * p)) ** 1.5
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + bp(rng.normal(0, 1, n), 600, 4000) * 0.6
    return (v * adsr(n, 0.01, 0.06) * (0.5 + 0.5 * np.abs(np.sin(np.pi * 2.2 * p)))).astype(np.float32)


def tuning(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    whine = np.sin(2 * np.pi * np.cumsum(800 + 2500 * np.abs(np.sin(2 * np.pi * 0.9 * tt))) / SR) * 0.25
    noise = bp(rng.normal(0, 1, n), 500, 6000) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * tt) ** 2)
    return ((whine + noise) * adsr(n, 0.05, 0.15)).astype(np.float32)


def static(dur):
    n = int(dur * SR)
    return (bp(rng.normal(0, 1, n), 400, 7000) * adsr(n, 0.02, 0.15)).astype(np.float32)


def stamp_hit():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * np.cumsum(70 + 90 * np.exp(-tt / 0.02)) / SR) * np.exp(-tt / 0.12) + hp(rng.normal(0, 1, n), 1500) * np.exp(-tt / 0.01) * 0.7
    return v.astype(np.float32)


def typewriter(dur, rate=14):
    n = int(dur * SR); v = np.zeros(n, np.float32)
    for k in range(int(dur * rate)):
        s = int(k / rate * SR + rng.uniform(0, 0.02) * SR); m = int(0.025 * SR)
        if s + m < n:
            v[s:s + m] += (hp(rng.normal(0, 1, m), 2000) * np.exp(-np.arange(m) / (m / 6))).astype(np.float32)
    return v


def tape_rewind(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 900 + 600 * np.sin(2 * np.pi * 13 * tt) + 400 * np.sin(2 * np.pi * 3.1 * tt)
    v = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + rng.normal(0, 0.4, n)
    return (bp(v, 600, 5000) * (0.6 + 0.4 * np.sin(2 * np.pi * 21 * tt)) * adsr(n, 0.05, 0.12)).astype(np.float32)


def projector_flash():
    n = int(0.25 * SR); tt = np.arange(n) / SR
    return (hp(rng.normal(0, 1, n), 3000) * np.exp(-tt / 0.03) * 0.6 + np.sin(2 * np.pi * 120 * tt) * np.exp(-tt / 0.05) * 0.4).astype(np.float32)


def crowd(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, n), 300, 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * tt))
    return (v * adsr(n, 0.5, 0.8)).astype(np.float32)


def ding(f=1318.5):
    n = int(0.8 * SR); tt = np.arange(n) / SR
    return ((np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt / 0.2)).astype(np.float32)


def click():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.004)).astype(np.float32)


def main():
    rew = TL["rew"]
    end = T
    off = Wt("pressao", 13)
    sc = [L[k]["start"] - 0.3 for k in ("fita", "titulo", "contexto", "sucesso", "pressao", "mae", "ruas", "impeach", "gabriel", "final", "cta")]
    full = [(0, 0.9), (rew[0], 0.9), (rew[0] + 0.08, 0), (rew[1] + 0.1, 0), (L["fita"]["start"] - 0.2, 0.8)]
    E = {
        "kick": env_points(full + [(off, 0.9), (off + 0.05, 0), (L["mae"]["start"], 0), (L["mae"]["start"] + 0.1, 0.6), (L["ruas"]["start"], 1), (L["final"]["start"] - 0.1, 1), (L["final"]["start"], 0), (L["cta"]["start"] - 0.2, 0), (L["cta"]["start"], 0.9), (end, 0.9)]),
        "snare": env_points(full + [(off, 0.9), (off + 0.05, 0), (L["mae"]["start"], 0), (L["mae"]["start"] + 0.1, 0.6), (L["ruas"]["start"], 1), (L["final"]["start"] - 0.1, 1), (L["final"]["start"], 0), (L["cta"]["start"] - 0.2, 0), (L["cta"]["start"], 0.9), (end, 0.9)]),
        "hats": env_points(full + [(off, 0.9), (off + 0.05, 0.3), (L["ruas"]["start"], 1), (L["final"]["start"], 0.4), (end, 0.9)]),
        "bass": env_points(full + [(off, 0.9), (off + 0.05, 0), (L["mae"]["start"] + 0.1, 0.6), (L["ruas"]["start"], 1), (L["final"]["start"], 0.5), (end, 0.9)]),
        "rhodes": env_points([(0, 0.8), (rew[0], 0.8), (rew[0] + 0.08, 0), (rew[1] + 0.1, 0), (L["fita"]["start"], 0.8), (end, 0.8)]),
        "crackle": env_points([(0, 1), (end, 1)]),
    }
    k, s, h = drums()
    stems = {"kick": k, "snare": s, "hats": h, "bass": bass(), "rhodes": rhodes(), "crackle": crackle()}
    music = np.zeros((N, 2), np.float32)
    for key, x in stems.items():
        music += x[:N] * E[key][:, None]
    music = np.tanh(music * 1.25) / 1.25

    sfx = np.zeros((N + SR * 3, 2), np.float32)
    add(sfx, static(0.5), Wt("hook", 10) - 0.05, 0.25)
    add(sfx, stamp_hit(), Wt("hook", 10), 0.3)
    add(sfx, tape_rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.28)
    for t0 in sc:
        add(sfx, projector_flash(), t0, 0.25)
    for t0 in (sc[0], sc[2], sc[6], sc[9]):
        add(sfx, scratch(), t0 - 0.15, 0.22)
    add(sfx, typewriter(1.2), L["fita"]["start"], 0.12)
    add(sfx, typewriter(0.9), Wt("fita", 12), 0.12)
    add(sfx, tuning(1.2), Wt("fita", 15), 0.1)
    add(sfx, typewriter(1.4, 10), Wt("titulo", 4), 0.13)
    add(sfx, stamp_hit(), Wt("contexto", 23), 0.25)
    add(sfx, ding(1318.5), Wt("sucesso", 13), 0.1)
    add(sfx, static(0.8), off - 0.1, 0.18)
    add(sfx, stamp_hit(), off, 0.32)
    add(sfx, typewriter(2.2), Wt("mae", 4), 0.12)
    add(sfx, stamp_hit(), Wt("mae", 13), 0.22)
    add(sfx, crowd(L["ruas"]["end"] - L["ruas"]["start"] + 0.8), L["ruas"]["start"] - 0.2, 0.11)
    add(sfx, typewriter(1.2), L["impeach"]["start"], 0.12)
    add(sfx, stamp_hit(), Wt("impeach", 15), 0.3)
    add(sfx, stamp_hit(), Wt("gabriel", 18), 0.18)
    add(sfx, stamp_hit(), Wt("final", 13), 0.32)
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.5)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    sfx = sfx[:N]
    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
