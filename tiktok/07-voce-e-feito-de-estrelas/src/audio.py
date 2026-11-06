"""Trilha original e efeitos do vídeo 07 (Ciência #5), tudo sintetizado, sem samples de terceiros.

Ré menor a 72 BPM: o andamento de um coração em repouso. O batimento abre o vídeo (sangue)
e volta no fecho ("você é o universo"). Sinos em FM para as estrelas e o ouro, coro etéreo,
graves de supernova, e o "chirp" das ondas gravitacionais seguindo a espiral das estrelas de nêutrons.

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
rng = np.random.default_rng(17)


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


def saw(f, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((f * t + phase) % 1.0) - 1


def adsr(n, a, r, sus=1.0):
    e = np.ones(n, np.float32) * sus
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, sus, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


# ---------------------------------------------------------------- harmonia: Dm – B♭ – F – C
BPM = 72
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [
    ([146.83, 174.61, 220.00], 36.71),   # Dm
    ([146.83, 174.61, 233.08], 58.27),   # B♭
    ([174.61, 220.00, 261.63], 43.65),   # F
    ([164.81, 196.00, 261.63], 32.70),   # C
]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


def make_pad():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, root = CHORDS[b % 4]
        n = int((BAR + 0.9) * SR)
        e = adsr(n, 0.7, 0.9)
        for f in notes + [root * 4]:
            for ch, det in ((0, -0.004), (1, 0.004)):
                v = sum(saw(f * (1 + det * k), n, rng.random()) for k in (-1, 0, 1)) / 3
                x = np.zeros((n, 2), np.float32); x[:, ch] = v * e * 0.15
                add(out, x, b * BAR)
    return lp(out, 1200)


def make_choir():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, _ = CHORDS[b % 4]
        n = int((BAR + 1.2) * SR); tt = np.arange(n) / SR; e = adsr(n, 0.9, 1.1)
        for i, f in enumerate(notes):
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * tt + i)
            ph = 2 * np.pi * np.cumsum(f * 2 * vib) / SR
            v = (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)) * e * 0.07
            add(out, v.astype(np.float32), b * BAR, pan=(-0.5, 0.0, 0.5)[i])
    return lp(out, 2600)


def bell(f, dur=1.6, idx=2.2, ratio=3.5):
    n = int(dur * SR); tt = np.arange(n) / SR
    mod = idx * np.exp(-tt / 0.25) * np.sin(2 * np.pi * f * ratio * tt)
    return (np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / (dur * 0.45)) * adsr(n, 0.002, 0.05)).astype(np.float32)


def make_bells():
    """arpejo de sinos (celesta) em colcheias"""
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    pattern = [0, 2, 1, 3, 2, 1, 3, 2]
    for k in range(int(T / step) + 1):
        t0 = k * step
        notes, _ = chord_at(t0)
        seq = [notes[0] * 4, notes[1] * 4, notes[2] * 4, notes[0] * 8]
        add(out, bell(seq[pattern[k % 8]], 1.2, 1.6), t0, 0.22, pan=0.4 if k % 2 else -0.4)
    return lp(out, 7000)


def make_bass():
    out = np.zeros((N, 2), np.float32)
    step = BEAT
    for k in range(int(T / step) + 1):
        t0 = k * step
        _, root = chord_at(t0)
        n = int(0.7 * SR); tt = np.arange(n) / SR
        v = np.tanh(2.0 * np.sin(2 * np.pi * root * 2 * tt)) * np.exp(-tt / 0.35) * adsr(n, 0.01, 0.08)
        add(out, v.astype(np.float32), t0, 0.16)
    return lp(out, 420)


def kick():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    f = 45 + 100 * np.exp(-tt / 0.035)
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.22)
    v[:200] += rng.normal(0, 0.3, 200) * np.linspace(1, 0, 200)
    return v.astype(np.float32)


def make_kicks():
    out = np.zeros((N, 2), np.float32)
    k = kick()
    for b in range(int(T / BEAT) + 1):
        add(out, k, b * BEAT, 0.26)
    return out


def heartbeat():
    n = int(0.55 * SR)
    def thump(t0, a):
        x = np.zeros(n); s = int(t0 * SR); m = n - s; t2 = np.arange(m) / SR
        x[s:] = a * np.sin(2 * np.pi * (46 + 40 * np.exp(-t2 / 0.03)) * t2) * np.exp(-t2 / 0.1)
        return x
    return lp(thump(0, 1.0) + thump(0.2, 0.65), 260).astype(np.float32)


def make_heart():
    out = np.zeros((N, 2), np.float32)
    hb = heartbeat()
    for b in range(int(T / BEAT) + 1):
        add(out, hb, b * BEAT, 0.55)
    return out


def make_shimmer():
    n = N; tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, (n, 2)), 6000, 12000) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * tt))[:, None]
    return (v * 0.06).astype(np.float32)


# ---------------------------------------------------------------- efeitos
def riser(dur):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    noise = rng.normal(0, 1, n)
    nz = hp(noise, 300) * (1 - p) * 0.5 + hp(noise, 3000) * p
    f = 160 * np.power(1500 / 160, p)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return ((0.5 * nz + 0.5 * tone) * np.power(p, 2.2)).astype(np.float32)


def impact(size=1.0):
    n = int(3.0 * SR); tt = np.arange(n) / SR
    f = 30 + 60 * np.exp(-tt / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (0.9 * size))
    crash = lp(rng.normal(0, 1, n), 5000) * np.exp(-tt / (0.35 * size)) * 0.5
    return np.tanh(1.5 * (boom + crash)).astype(np.float32)


def rumble(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = lp(rng.normal(0, 1, n), 120, 4) * 6 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    return (v * adsr(n, 0.3, 0.8)).astype(np.float32)


def whoosh(dur=0.3, lo=400, hi=3500):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    noise = rng.normal(0, 1, n)
    v = (bp(noise, lo, lo * 2.5) * (1 - p) + bp(noise, hi / 2.5, hi) * p) * np.sin(np.pi * p) ** 1.5
    return v.astype(np.float32)


def rewind(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 900 + 600 * np.sin(2 * np.pi * 13 * tt) + 400 * np.sin(2 * np.pi * 3.1 * tt)
    v = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + rng.normal(0, 0.4, n)
    return (bp(v, 600, 5000) * (0.6 + 0.4 * np.sin(2 * np.pi * 21 * tt)) * adsr(n, 0.05, 0.12)).astype(np.float32)


def ding(f=1318.5):
    n = int(0.8 * SR); tt = np.arange(n) / SR
    return ((np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt / 0.2)).astype(np.float32)


def blip(f):
    n = int(0.18 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.05) * adsr(n, 0.002, 0.02)).astype(np.float32)


def click():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.004)).astype(np.float32)


def tick():
    n = int(0.04 * SR); tt = np.arange(n) / SR
    return (hp(rng.normal(0, 1, n), 2500) * np.exp(-tt / 0.004) + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt / 0.006) * 0.5).astype(np.float32)


def gong(f=110.0, dur=4.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    parts = [(1.0, 1.0), (2.76, 0.5), (5.4, 0.3), (8.9, 0.2), (1.5, 0.35)]
    v = sum(a * np.sin(2 * np.pi * f * r * tt * (1 + 0.002 * np.sin(2 * np.pi * 3 * tt))) * np.exp(-tt / (dur * 0.35 / r ** 0.3)) for r, a in parts)
    return (v * adsr(n, 0.004, 0.3) * 0.5).astype(np.float32)


def wind(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, n), 300, 1800) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.2 * tt + 1))
    return (v * adsr(n, 0.5, 0.7)).astype(np.float32)


def bird():
    n = int(0.22 * SR); tt = np.arange(n) / SR
    f = 3400 + 1500 * np.sin(np.pi * tt / tt[-1]) + 300 * np.sin(2 * np.pi * 28 * tt)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2).astype(np.float32)


def gw_chirp(t0, tm, dur_after=0.0):
    """onda gravitacional sonificada: frequência sobe como τ^(-3/8) até a fusão"""
    n = int((tm - t0) * SR); tt = np.arange(n) / SR
    tau = np.maximum(tm - t0 - tt, 2e-3); Tp = tm - t0
    f = np.minimum(70 * np.power(tau / Tp, -3 / 8), 900)
    ph = 2 * np.pi * np.cumsum(f) / SR
    a = np.power(f / 70, 2 / 3) * np.minimum(1, tt / 0.6)
    v = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * a
    return (v / np.max(np.abs(v))).astype(np.float32)


def sparkle(dur=1.4, base=2093.0):
    out = np.zeros(int(dur * SR), np.float32)
    for k in range(14):
        f = base * 2 ** (rng.integers(0, 12) / 12) * (2 if k % 3 == 0 else 1)
        b = bell(f, 0.9, 1.0, 2.0)
        s = int(rng.uniform(0, dur - 0.9) * SR)
        out[s:s + len(b)] += b[: len(out) - s] * 0.25
    return out


def main():
    rew = TL["rew"]; end = T
    boom = Wt("hook", 14); tBang = Wt("hidrogenio", 15); tBoomO = Wt("oxigenio", 16)
    tDay, tNow = Wt("caranguejo", 13), Wt("caranguejo", 21)
    tSpiral, tMerge, tShake = Wt("ouro", 3), Wt("ouro", 14), Wt("ouro", 19)
    tVoce = Wt("viagem", 17)
    sc = {k: L[k]["start"] - d for k, d in [("tudo", 0.4), ("hidrogenio", 0.4), ("carbono", 0.45), ("oxigenio", 0.35), ("caranguejo", 0.4),
                                           ("ouro", 0.45), ("viagem", 0.45), ("fecho", 0.55), ("cta", 0.4)]}
    E = {
        "heart": env_points([(0, 0.85), (Wt("hook", 8), 0.85), (boom, 0.9), (boom + 0.05, 0), (sc["fecho"], 0), (sc["fecho"] + 1.0, 0.55),
                             (L["fecho"]["end"], 0.55), (sc["cta"], 0.25), (end - 1.2, 0.3), (end, 0.85)]),
        "pad": env_points([(0, 0.35), (boom, 0.45), (boom + 0.1, 0.8), (rew[0], 0.7), (rew[0] + 0.08, 0), (rew[1], 0), (rew[1] + 0.5, 0.5),
                           (sc["hidrogenio"], 0.35), (tBang, 0.4), (tBang + 0.1, 0.85), (sc["carbono"], 0.6), (sc["oxigenio"], 0.6), (tBoomO, 0.8),
                           (sc["caranguejo"], 0.55), (sc["ouro"], 0.45), (tMerge, 0.35), (tMerge + 0.1, 0.85), (sc["viagem"], 0.7), (tVoce, 0.9),
                           (sc["fecho"], 0.6), (L["fecho"]["end"], 0.55), (sc["cta"], 0.6), (end - 1.2, 0.5), (end, 0.35)]),
        "choir": env_points([(0, 0.0), (Wt("hook", 8), 0.0), (boom, 0.6), (rew[0], 0.7), (rew[0] + 0.08, 0), (sc["hidrogenio"], 0), (sc["hidrogenio"] + 1, 0.35),
                             (tBang, 0.5), (tBang + 0.2, 0.9), (sc["carbono"], 0.55), (sc["oxigenio"], 0.4), (tBoomO, 0.7), (sc["caranguejo"], 0.7),
                             (tDay, 0.5), (tNow, 0.8), (sc["ouro"], 0.3), (tMerge, 0.3), (tMerge + 0.3, 1.0), (sc["viagem"], 0.7), (tVoce, 1.0),
                             (sc["fecho"], 0.75), (L["fecho"]["end"], 0.9), (sc["cta"], 0.3), (end, 0)]),
        "bells": env_points([(0, 0), (rew[1], 0), (rew[1] + 0.4, 0.55), (sc["hidrogenio"], 0.3), (tBang, 0.2), (tBang + 0.5, 0.45), (sc["carbono"], 0.55),
                             (sc["oxigenio"], 0.4), (sc["caranguejo"], 0.3), (tDay, 0.7), (tNow, 0.4), (sc["ouro"], 0.8), (tSpiral, 0.25), (tMerge, 0.1),
                             (tMerge + 0.5, 0.5), (sc["viagem"], 0.55), (tVoce, 0.7), (sc["fecho"], 0.0), (sc["cta"], 0), (sc["cta"] + 0.3, 0.6), (end - 0.6, 0.4), (end, 0)]),
        "bass": env_points([(0, 0), (boom, 0), (boom + 0.05, 0.7), (rew[0], 0.6), (rew[0] + 0.08, 0), (rew[1] + 0.5, 0.35), (sc["hidrogenio"], 0.1),
                            (tBang, 0.1), (tBang + 0.1, 0.7), (sc["carbono"], 0.45), (sc["oxigenio"], 0.6), (tBoomO, 0.8), (sc["caranguejo"], 0.4),
                            (sc["ouro"], 0.3), (tSpiral, 0.15), (tMerge, 0.1), (tMerge + 0.1, 0.8), (sc["viagem"], 0.6), (tVoce, 0.8),
                            (sc["fecho"], 0.2), (sc["cta"], 0.4), (end - 0.5, 0.3), (end, 0)]),
        "kick": env_points([(0, 0), (sc["oxigenio"], 0), (sc["oxigenio"] + 0.3, 0.45), (tBoomO, 0.6), (sc["caranguejo"], 0), (tMerge + 0.1, 0), (tMerge + 0.2, 0.5),
                            (sc["viagem"], 0.35), (Wt("viagem", 9), 0.55), (tVoce, 0.6), (tVoce + 0.1, 0), (end, 0)]),
        "shimmer": env_points([(0, 0), (sc["ouro"], 0), (sc["ouro"] + 0.3, 1), (tSpiral, 0.4), (tMerge, 0.2), (tMerge + 0.3, 0.9), (sc["viagem"], 0.6),
                               (tVoce, 1), (sc["fecho"], 0.3), (sc["cta"], 0), (end, 0)]),
    }
    stems = {"heart": make_heart(), "pad": make_pad(), "choir": make_choir(), "bells": make_bells(), "bass": make_bass(),
             "kick": make_kicks(), "shimmer": make_shimmer()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music = np.tanh(music * 1.2) / 1.2

    sfx = np.zeros((N + SR * 4, 2), np.float32)
    # transições
    for name, t0 in sc.items():
        if name in ("carbono", "ouro", "fecho"):   # íris
            add(sfx, whoosh(0.9, 200, 4000), t0 - 0.05, 0.2)
        elif name in ("oxigenio", "viagem"):        # clarão
            add(sfx, riser(0.4), t0 - 0.05, 0.12); add(sfx, whoosh(0.6, 500, 6000), t0 + 0.2, 0.15)
        else:
            add(sfx, whoosh(0.8, 150, 5000), t0 - 0.1, 0.22)
    # cartões de elementos: surgem (sino) e voam até o painel
    for line, w, fl, f in [("hook", 1, 7, 1174.7), ("hidrogenio", 3, 9, 1318.5), ("carbono", 1, 5, 1396.9), ("oxigenio", 1, 5, 1568.0),
                           ("oxigenio", 7, 11, 1760.0), ("ouro", 2, 5, 2093.0)]:
        add(sfx, ding(f), Wt(line, w), 0.08); add(sfx, ding(f * 1.5), Wt(line, w) + 0.1, 0.04)
        add(sfx, whoosh(0.5, 800, 6000), Wt(line, fl) + 0.05, 0.07, pan=-0.3)
    # gancho: o ferro brilha, a câmera mergulha no átomo, a estrela explode
    add(sfx, riser(boom - Wt("hook", 8)), Wt("hook", 8), 0.16)
    add(sfx, impact(1.2), boom, 0.26); add(sfx, rumble(2.5), boom, 0.1)
    add(sfx, rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.25)
    # tabela periódica: cada elemento do corpo acende (onda a partir do ferro)
    pos = {"H": (0, 0), "C": (1, 13), "N": (1, 14), "O": (1, 15), "Na": (2, 0), "Mg": (2, 1), "P": (2, 14), "S": (2, 15), "Cl": (2, 16),
           "K": (3, 0), "Ca": (3, 1), "Zn": (3, 11), "I": (4, 16)}
    tAll = Wt("tudo", 6)
    add(sfx, blip(1046.5), Wt("tudo", 5), 0.12)
    for k, (r, c) in enumerate(sorted(pos.values(), key=lambda rc: math.hypot(rc[0] - 3, rc[1] - 7))):
        d = math.hypot(r - 3, c - 7)
        add(sfx, blip(1046.5 * 2 ** ((k % 8) / 7)), tAll + d * 0.12 + 0.05, 0.06, pan=(c - 8.5) / 9)
    t = L["tudo"]["start"] - 0.2
    while t < L["hidrogenio"]["start"] - 0.4:
        add(sfx, tick(), t, 0.05); t += 0.42
    # hidrogênio: recuo e Big Bang
    add(sfx, riser(tBang - Wt("hidrogenio", 10)), Wt("hidrogenio", 10), 0.15)
    add(sfx, impact(1.6), tBang, 0.24); add(sfx, rumble(3.5), tBang, 0.11)
    add(sfx, whoosh(2.0, 80, 2500), tBang + 0.05, 0.18)
    # carbono: as partículas do DNA se espalham
    add(sfx, sparkle(1.6, 1760.0), Wt("carbono", 11), 0.25, pan=0.2)
    add(sfx, whoosh(1.4, 300, 6000), Wt("carbono", 11), 0.12)
    # oxigênio: a supernova
    add(sfx, riser(1.2), tBoomO - 1.2, 0.12)
    add(sfx, impact(1.0), tBoomO, 0.24); add(sfx, rumble(2.0), tBoomO, 0.08)
    # 1054
    add(sfx, gong(98.0, 4.5), Wt("caranguejo", 8), 0.18)
    add(sfx, whoosh(0.7, 800, 9000), tDay - 0.15, 0.18)
    add(sfx, wind(tNow - tDay + 0.6), tDay, 0.16)
    for k in range(5):
        add(sfx, bird(), tDay + 0.6 + k * 1.1 + rng.uniform(0, 0.4), 0.04, pan=rng.uniform(-0.7, 0.7))
    add(sfx, whoosh(1.0, 150, 4000), tNow - 0.1, 0.2)
    # ouro: brilho, espiral (chirp das ondas gravitacionais), fusão e tremor
    add(sfx, sparkle(1.5, 2093.0), Wt("ouro", 2) - 0.1, 0.4)
    add(sfx, gw_chirp(tSpiral, tMerge), tSpiral, 0.13)
    add(sfx, impact(1.4), tMerge, 0.28); add(sfx, rumble(3.0), tMerge, 0.12)
    add(sfx, rumble(1.8), tShake, 0.18); add(sfx, impact(0.6), tShake, 0.1)
    add(sfx, sparkle(2.0, 1568.0), tMerge + 0.3, 0.3)
    # viagem: o Sol, a Terra e a poeira que forma "você"
    add(sfx, whoosh(1.2, 120, 3000), Wt("viagem", 9), 0.15)
    add(sfx, ding(659.25), Wt("viagem", 13), 0.06)
    add(sfx, riser(tVoce - Wt("viagem", 14) + 0.6), Wt("viagem", 14) - 0.6, 0.12)
    for k, f in enumerate([587.33, 698.46, 880.0, 1174.66]):
        add(sfx, bell(f, 2.4, 1.2), tVoce + k * 0.06, 0.12)
    add(sfx, sparkle(1.8, 2349.3), tVoce, 0.3)
    # fecho e encerramento
    add(sfx, gong(73.42, 5.0), Wt("fecho", 7), 0.08)
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.35)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    add(sfx, whoosh(0.6, 300, 2500), T - 0.6, 0.2)
    sfx = sfx[:N]
    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
