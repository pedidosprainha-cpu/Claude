"""Trilha original e efeitos do vídeo 06 (Ciência #4) (tudo sintetizado, sem samples de terceiros).

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
FPS = TL["fps"]
rng = np.random.default_rng(7)


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


# ---------------------------------------------------------------- harmonia (Dó menor, cinematográfico, 60 BPM = um tique por segundo)
BPM = 60
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [  # Cm(add9)  Ab  Eb  Bb
    ([130.81, 155.56, 196.00], 32.70),
    ([130.81, 155.56, 207.65], 51.91),
    ([155.56, 196.00, 233.08], 38.89),
    ([146.83, 174.61, 233.08], 58.27),
]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


def make_pad():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, root = CHORDS[b % 4]
        n = int((BAR + 0.9) * SR)
        e = adsr(n, 0.6, 0.9)
        for f in notes + [root * 4]:
            for ch, det in ((0, -0.0045), (1, 0.0045)):
                v = sum(saw(f * (1 + det * k), n, rng.random()) for k in (-1, 0, 1)) / 3
                x = np.zeros((n, 2), np.float32); x[:, ch] = v * e * 0.16
                add(out, x, b * BAR)
    return lp(out, 1300)


def make_choir():  # "aaah" etéreo: senos com vibrato, oitava acima
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, _ = CHORDS[b % 4]
        n = int((BAR + 1.2) * SR); tt = np.arange(n) / SR; e = adsr(n, 0.9, 1.1)
        for i, f in enumerate(notes):
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * tt + i)
            ph = 2 * np.pi * np.cumsum(f * 2 * vib) / SR
            v = (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)) * e * 0.07
            add(out, v.astype(np.float32), b * BAR, pan=(-0.5, 0.0, 0.5)[i])
    return lp(out, 2500)


def make_arp(bright):
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    pattern = [0, 1, 2, 3, 2, 1, 0, 2]
    for k in range(int(T / step) + 1):
        t0 = k * step
        notes, _ = chord_at(t0)
        seq = [notes[0] * 2, notes[1] * 2, notes[2] * 2, notes[0] * 4]
        f = seq[pattern[k % 8]]
        n = int(0.45 * SR); tt = np.arange(n) / SR
        v = (0.55 * saw(f, n) + 0.45 * np.sin(2 * np.pi * f * tt)) * np.exp(-tt / (0.18 if bright else 0.13))
        add(out, v.astype(np.float32), t0, 0.9 if not bright else 0.45, pan=0.35 if k % 2 else -0.35)
    return lp(out, 4500 if bright else 1100)


def make_bass():
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    for k in range(int(T / step) + 1):
        t0 = k * step
        _, root = chord_at(t0)
        n = int(0.32 * SR); tt = np.arange(n) / SR
        v = np.tanh(2.2 * np.sin(2 * np.pi * root * 2 * tt)) * np.exp(-tt / 0.16) * adsr(n, 0.005, 0.05)
        add(out, v.astype(np.float32), t0, 0.15)
    return lp(out, 480)


def kick():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    f = 46 + 100 * np.exp(-tt / 0.035)
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.22)
    v[:200] += rng.normal(0, 0.3, 200) * np.linspace(1, 0, 200)
    return v.astype(np.float32)


def make_kicks():
    out = np.zeros((N, 2), np.float32)
    k = kick()
    for b in range(int(T / BEAT) + 1):
        add(out, k, b * BEAT, 0.25)
    return out


def tick(f=2600, dur=0.05, decay=0.008):
    n = int(dur * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * tt) * np.exp(-tt / decay) + 0.6 * np.sin(2 * np.pi * f * 0.62 * tt) * np.exp(-tt / (decay * 1.6))
    click = hp(rng.normal(0, 1, n), 3000) * np.exp(-tt / 0.002) * 0.6
    return (body + click).astype(np.float32)


TICK, TOCK = tick(2600), tick(1900)


def make_clock_ticks():
    """tique-taque do relógio no tempo da música (base)"""
    out = np.zeros((N, 2), np.float32)
    for b in range(int(T / BEAT) + 1):
        add(out, TICK if b % 2 == 0 else TOCK, b * BEAT, 0.14, pan=-0.2 if b % 2 == 0 else 0.2)
    return out


# ---------------------------------------------------------------- efeitos
def riser(dur):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur
    noise = rng.normal(0, 1, n)
    nz = hp(noise, 300) * (1 - p) * 0.5 + hp(noise, 3000) * p
    f = 160 * np.power(1500 / 160, p)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return ((0.5 * nz + 0.5 * tone) * np.power(p, 2.2)).astype(np.float32)


def impact(size=1.0):
    n = int(2.6 * SR); tt = np.arange(n) / SR
    f = 32 + 60 * np.exp(-tt / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (0.9 * size))
    crash = lp(rng.normal(0, 1, n), 5000) * np.exp(-tt / (0.35 * size)) * 0.5
    return np.tanh(1.5 * (boom + crash)).astype(np.float32)


def rumble(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = lp(rng.normal(0, 1, n), 120, 4) * 6 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    return (v * adsr(n, 0.4, 0.8)).astype(np.float32)


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


def pop(f=600):
    n = int(0.12 * SR); tt = np.arange(n) / SR
    fr = f * (1 + 1.5 * np.exp(-tt / 0.02))
    return (np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-tt / 0.035)).astype(np.float32)


def bubble():
    n = int(0.09 * SR); tt = np.arange(n) / SR
    f = 500 + 1400 * tt / tt[-1]
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.03)).astype(np.float32)


def click():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.004)).astype(np.float32)


def heartbeat():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    def thump(t0, a):
        x = np.zeros(n); s = int(t0 * SR); m = n - s; t2 = np.arange(m) / SR
        x[s:] = a * np.sin(2 * np.pi * (48 + 40 * np.exp(-t2 / 0.03)) * t2) * np.exp(-t2 / 0.09)
        return x
    return lp(thump(0, 1.0) + thump(0.17, 0.7), 300).astype(np.float32)


def chirp():
    n = int(0.16 * SR); tt = np.arange(n) / SR
    f = 3200 + 1600 * np.sin(np.pi * tt / tt[-1])
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2).astype(np.float32)


def crackle(dur):
    n = int(dur * SR); v = np.zeros(n, np.float32)
    for _ in range(int(dur * 18)):
        s = rng.integers(0, n - 400); m = rng.integers(60, 300)
        v[s:s + m] += (rng.normal(0, 1, m) * np.exp(-np.arange(m) / (m / 4))).astype(np.float32)
    return (bp(v, 800, 6000) * adsr(n, 0.3, 0.5)).astype(np.float32)


def water_amb(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = lp(rng.normal(0, 1, n), 500, 2) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.15 * tt))
    return (v * adsr(n, 0.5, 0.6)).astype(np.float32)



def main():
    rew = TL["rew"]
    end = T
    gone = Wt("hook", 3) + 0.1
    sc = {k: L[k]["start"] - d for k, d in [("luz", 0.4), ("lua", 0.4), ("sol", 0.35), ("proxima", 0.35), ("betelgeuse", 0.35), ("andromeda", 0.4), ("webb", 0.4), ("virada", 0.45), ("fecho", 0.5), ("cta", 0.4)]}
    E = {
        "pad": env_points([(0, 0.6), (gone, 0.6), (gone + 0.05, 0.25), (rew[0], 0.3), (rew[0] + 0.08, 0), (rew[1], 0), (rew[1] + 0.6, 0.55),
                           (sc["andromeda"], 0.7), (sc["webb"], 0.8), (L["webb"]["end"], 0.85), (sc["virada"], 0.35), (sc["fecho"], 0.7), (end - 1, 0.6), (end, 0.6)]),
        "choir": env_points([(0, 0.2), (gone, 0.2), (gone + 0.1, 0.6), (rew[0], 0.5), (rew[0] + 0.08, 0), (sc["andromeda"], 0), (sc["andromeda"] + 0.8, 0.6),
                             (sc["webb"], 0.8), (L["webb"]["end"], 1), (sc["virada"], 0.2), (sc["fecho"], 0.4), (L["fecho"]["end"], 1), (end, 0.6)]),
        "arp_dark": env_points([(0, 0.6), (rew[0], 0.6), (rew[0] + 0.08, 0), (L["luz"]["start"], 0), (L["luz"]["start"] + 0.5, 0.6),
                                (sc["virada"], 0.6), (sc["virada"] + 0.2, 0.15), (sc["fecho"], 0.15), (sc["cta"], 0.6), (end, 0.6)]),
        "arp_bright": env_points([(0, 0), (sc["proxima"], 0), (sc["proxima"] + 0.5, 0.5), (sc["webb"], 0.8), (L["webb"]["end"], 0.9), (sc["virada"], 0),
                                  (sc["cta"], 0), (sc["cta"] + 0.3, 0.6), (end, 0.5)]),
        "bass": env_points([(0, 0.4), (rew[0], 0.4), (rew[0] + 0.08, 0), (sc["sol"], 0), (sc["sol"] + 0.4, 0.5), (sc["webb"], 0.8), (L["webb"]["end"], 0.8),
                            (sc["virada"], 0), (sc["cta"], 0), (sc["cta"] + 0.2, 0.6), (end, 0.4)]),
        "kick": env_points([(0, 0), (sc["betelgeuse"], 0), (sc["betelgeuse"] + 0.05, 0.5), (sc["webb"], 0.8), (L["webb"]["end"], 0.8), (sc["virada"], 0), (end, 0)]),
        "ticks": env_points([(0, 0.7), (rew[0], 0.7), (rew[0] + 0.08, 0), (rew[1], 0), (rew[1] + 0.3, 0.6), (sc["webb"], 0.5), (sc["virada"], 0.9), (sc["fecho"], 0.9),
                             (L["fecho"]["end"], 0), (sc["cta"], 0), (sc["cta"] + 0.3, 0.4), (end, 0.6)]),
    }
    stems = {"pad": make_pad(), "choir": make_choir(), "arp_dark": make_arp(False), "arp_bright": make_arp(True),
             "bass": make_bass(), "kick": make_kicks(), "ticks": make_clock_ticks()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music = np.tanh(music * 1.2) / 1.2

    sfx = np.zeros((N + SR * 3, 2), np.float32)
    # gancho: o Sol some (impacto grave), e a última luz segue até a Terra
    add(sfx, impact(1.0), gone, 0.18)
    add(sfx, whoosh(rew[0] - gone, 150, 2500), gone, 0.2)
    add(sfx, rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.25)
    for t0 in sc.values():
        add(sfx, whoosh(0.8, 150, 5000), t0 - 0.1, 0.24)
    # brilho quando cada valor aparece
    for line, w, f in [("lua", 9, 1318.5), ("sol", 6, 1174.7), ("proxima", 14, 1046.5), ("betelgeuse", 17, 987.8), ("andromeda", 10, 880.0),
                       ("webb", 12, 783.99), ("virada", 22, 1567.98)]:
        add(sfx, ding(f), Wt(line, w) + 0.15, 0.07)
        add(sfx, ding(f * 1.5), Wt(line, w) + 0.27, 0.04)
    add(sfx, riser(Wt("webb", 12) - L["webb"]["start"]), L["webb"]["start"], 0.1)
    add(sfx, impact(0.7), Wt("webb", 12) + 0.05, 0.1)
    # virada: quase silêncio; o pulso do relógio fica sozinho
    add(sfx, whoosh(1.2, 100, 1200), Wt("virada", 6) - 0.2, 0.15)
    for k, f in enumerate([523.25, 622.25, 783.99, 1046.5]):
        add(sfx, ding(f), Wt("fecho", 7) + k * 0.16, 0.05)
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.5)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    add(sfx, whoosh(0.6, 300, 2500), T - 0.6, 0.2)
    sfx = sfx[:N]
    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
