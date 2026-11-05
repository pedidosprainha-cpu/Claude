"""Trilha original e efeitos do vídeo 02 (tudo sintetizado, sem samples de terceiros).

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
DIA = 86400.0
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


# ---------------------------------------------------------------- harmonia (Ré menor, cinematográfico)
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [  # Dm  Bb  Gm  A
    ([146.83, 174.61, 220.00], 36.71),
    ([146.83, 174.61, 233.08], 58.27),
    ([146.83, 196.00, 233.08], 49.00),
    ([138.59, 164.81, 220.00], 55.00),
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


def ratchet(sfx):
    """quando o relógio dispara, os tiques aceleram (catraca), guiados pela velocidade real do relógio"""
    clock = np.array(TL["clock"])
    spd = np.abs(np.gradient(clock)) * FPS
    phase, t = 0.0, 0.0
    dt = 1 / 600
    k = 0
    while t < T:
        i = min(int(t * FPS), len(spd) - 1)
        lg = math.log10(spd[i] + 1e-9)
        rate = 0 if spd[i] < 30 else 5 + 23 * min(1, max(0, (lg - 1.5) / 3))
        if rate > 0:
            phase += rate * dt
            if phase >= 1:
                phase -= 1; k += 1
                add(sfx, TICK if k % 2 else TOCK, t, 0.16 * min(1, (lg - 1.4)), pan=0.25 if k % 2 else -0.25)
        else:
            phase = 0.99
        t += dt


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
    hook_end = L["hook"]["end"]
    rew = (hook_end + 0.25, hook_end + 0.95)
    TI_lua = Wt("lua", 11)
    TA, TI_ast = Wt("asteroide", 7), Wt("asteroide", 12, "t1") - 0.05
    end = T
    sc = {  # inícios de cena (iguais ao render)
        "ocean": L["vida"]["start"] - 0.35, "reef": L["animais"]["start"] - 0.4, "jurassic": L["dinos"]["start"] - 0.3,
        "cenozoic": L["mamiferos"]["start"] - 0.4, "sunset": L["humanos"]["start"] - 0.35, "ringzoom": L["vidahum"]["start"] - 0.35,
        "cta": L["cta"]["start"] - 0.35,
    }
    refl = L["reflexao"]["start"]

    E = {
        "pad": env_points([(0, 0.55), (rew[0], 0.55), (rew[0] + 0.1, 0), (rew[1], 0), (rew[1] + 0.5, 0.55), (TI_lua, 0.7),
                           (sc["ocean"], 0.5), (sc["reef"], 0.6), (TI_ast - 0.05, 0.75), (TI_ast + 0.02, 0.2), (sc["cenozoic"], 0.55),
                           (sc["sunset"], 0.6), (sc["ringzoom"], 0.65), (refl, 0.45), (end - 1.0, 0.5), (end, 0.5)]),
        "choir": env_points([(0, 0), (TI_lua, 0), (TI_lua + 0.4, 0.8), (sc["ocean"], 0.2), (sc["reef"], 0.5), (sc["jurassic"], 0),
                             (sc["sunset"], 0), (sc["sunset"] + 0.6, 0.9), (sc["ringzoom"], 1), (refl, 1), (end - 1, 0.6), (end, 0)]),
        "arp_dark": env_points([(0, 0.7), (rew[0], 0.7), (rew[0] + 0.1, 0), (L["nasce"]["start"], 0), (L["nasce"]["start"] + 0.6, 0.7),
                                (sc["jurassic"], 0.4), (TI_ast, 0.2), (TI_ast + 0.05, 0), (sc["cenozoic"], 0), (sc["cenozoic"] + 0.3, 0.7),
                                (refl, 0.7), (refl + 0.3, 0), (sc["cta"], 0), (sc["cta"] + 0.2, 0.7), (end, 0.7)]),
        "arp_bright": env_points([(0, 0), (sc["reef"], 0), (sc["reef"] + 0.3, 0.6), (sc["jurassic"], 0.9), (TI_ast, 0.9), (TI_ast + 0.05, 0),
                                  (sc["sunset"], 0), (sc["sunset"] + 0.4, 0.7), (refl, 0.7), (refl + 0.3, 0), (sc["cta"], 0), (sc["cta"] + 0.2, 0.8), (end, 0.6)]),
        "bass": env_points([(0, 0), (L["lua"]["start"], 0), (L["lua"]["start"] + 0.3, 0.6), (sc["jurassic"], 0.9), (TI_ast, 0.9),
                            (TI_ast + 0.05, 0), (sc["cenozoic"] + 0.2, 0), (sc["cenozoic"] + 0.5, 0.6), (refl, 0.6), (refl + 0.3, 0),
                            (sc["cta"], 0), (sc["cta"] + 0.2, 0.6), (end - 0.4, 0.5), (end, 0.2)]),
        "kick": env_points([(0, 0), (sc["reef"] - 0.05, 0), (sc["reef"], 0.8), (TA - 0.1, 0.8), (TA, 0), (TI_ast, 0), (sc["cenozoic"], 0),
                            (sc["cenozoic"] + 0.05, 0.8), (sc["ringzoom"], 0.8), (sc["ringzoom"] + 0.05, 0), (sc["cta"], 0),
                            (sc["cta"] + 0.05, 0.9), (end - 0.5, 0.9), (end - 0.45, 0)]),
        "ticks": env_points([(0, 0.6), (refl - 0.3, 0.8), (refl, 0), (sc["cta"], 0), (sc["cta"] + 0.3, 0.5), (end, 0.6)]),
    }
    stems = {"pad": make_pad(), "choir": make_choir(), "arp_dark": make_arp(False), "arp_bright": make_arp(True),
             "bass": make_bass(), "kick": make_kicks(), "ticks": make_clock_ticks()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music = np.tanh(music * 1.2) / 1.2

    sfx = np.zeros((N + SR * 3, 2), np.float32)
    ratchet(sfx)
    # gancho
    h1, h16 = Wt("hook", 1), Wt("hook", 16)
    add(sfx, riser(h16 - h1), h1, 0.13)
    add(sfx, impact(0.7), h16, 0.14)
    add(sfx, ding(1760), h16 + 0.02, 0.12)
    add(sfx, rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.25)
    # 1 hora = 189 milhões
    add(sfx, whoosh(0.4, 400, 3000), Wt("acelera", 4) - 0.15, 0.3)
    add(sfx, ding(1318.5), Wt("acelera", 12), 0.1)
    # Terra nasce: ronco de lava
    add(sfx, rumble(L["lua"]["end"] - L["nasce"]["start"] + 0.5), L["nasce"]["start"] - 0.2, 0.16)
    # Theia
    l3 = Wt("lua", 3)
    add(sfx, riser(TI_lua - l3), l3, 0.15)
    add(sfx, whoosh(TI_lua - l3, 200, 2500), l3, 0.2)
    add(sfx, impact(1.4), TI_lua, 0.16)
    for k, f in enumerate([880, 1108.7, 1318.5, 1760]):  # Lua se formando
        add(sfx, ding(f), Wt("lua", 17) + k * 0.12, 0.06)
    # transições entre cenas
    for t0 in sc.values():
        add(sfx, whoosh(0.45, 300, 4000), t0 - 0.25, 0.3)
    # oceano: ambiente + bolhas + micróbios surgindo
    add(sfx, water_amb(sc["jurassic"] - sc["ocean"]), sc["ocean"], 0.5)
    add(sfx, pop(520), Wt("vida", 6) - 0.05, 0.2)
    for k in range(6):
        add(sfx, bubble(), Wt("vida", 7) - 0.1 + k * 0.16, 0.12, pan=rng.uniform(-0.5, 0.5))
    for k in range(20):
        add(sfx, bubble(), L["tedio"]["start"] + 0.6 + k * 0.22, 0.07, pan=rng.uniform(-0.6, 0.6))
    for k in range(24):
        add(sfx, bubble(), L["oxigenio"]["start"] + rng.uniform(0, 3.5), 0.1, pan=rng.uniform(-0.7, 0.7))
    add(sfx, ding(1046.5), Wt("oxigenio", 10) - 0.1, 0.1)
    # recife: animais aparecendo
    for k, tt in enumerate([Wt("animais", 3) - 0.1, Wt("animais", 3) + 0.15, Wt("animais", 5), Wt("animais", 5) + 0.1, Wt("animais", 7), Wt("animais", 7) + 0.25]):
        add(sfx, pop(500 + k * 90), tt, 0.16, pan=rng.uniform(-0.5, 0.5))
    # dinossauros: passos pesados
    for k in range(8):
        add(sfx, lp(kick(), 150), Wt("dinos", 3) + k * 0.62, 0.18)
    add(sfx, pop(380), Wt("dinos", 3) - 0.1, 0.15)
    add(sfx, pop(300), Wt("dinos", 5), 0.15)
    # asteroide
    add(sfx, riser(TI_ast - TA), TA, 0.16)
    add(sfx, whoosh(TI_ast - TA, 150, 6000), TA, 0.28)
    add(sfx, impact(1.2), TI_ast, 0.22)
    add(sfx, rumble(2.0), TI_ast + 0.1, 0.12)
    # mamíferos: pássaros e pops
    for k in range(7):
        add(sfx, chirp(), sc["cenozoic"] + 0.5 + k * 0.33 + rng.uniform(0, 0.1), 0.04, pan=rng.uniform(-0.8, 0.8))
    for k, w in enumerate([1, 2, 4]):
        add(sfx, pop(450 + k * 120), Wt("mamiferos", w), 0.15)
    # pôr do sol: fogueira
    add(sfx, crackle(sc["ringzoom"] - sc["sunset"]), sc["sunset"], 0.12)
    add(sfx, pop(420), Wt("humanos", 1), 0.12)
    add(sfx, ding(1568), Wt("humanos", 5), 0.1)
    add(sfx, whoosh(1.2, 200, 1500), L["piramides"]["start"] - 0.4, 0.3)
    # zoom: subida profunda até o "VOCÊ"
    z0, z1 = Wt("vidahum", 2), Wt("vidahum", 11, "t1")
    add(sfx, riser(z1 - z0), z0, 0.13)
    add(sfx, whoosh(z1 - z0, 100, 5000), z0, 0.35)
    add(sfx, ding(2093), Wt("vidahum", 9), 0.14)
    add(sfx, ding(2637), Wt("vidahum", 9) + 0.08, 0.08)
    # reflexão: batimentos sincronizados com o pulso visual
    k = 0
    while True:
        tb = refl + (0.25 + k) / 1.1 - 0.05
        if tb > L["cta"]["start"] - 0.3:
            break
        add(sfx, heartbeat(), tb, 0.3)
        k += 1
    # CTA
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.5)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    add(sfx, whoosh(0.6, 300, 2500), T - 0.6, 0.2)
    sfx = sfx[:N]

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
