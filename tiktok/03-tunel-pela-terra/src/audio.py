"""Trilha original e efeitos do vídeo 03 (tudo sintetizado, sem samples de terceiros).

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


# ---------------------------------------------------------------- harmonia (Mi menor, aventura)
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
CHORDS = [  # Em  C  G  D
    ([164.81, 196.00, 246.94], 41.20),
    ([130.81, 164.81, 196.00], 32.70),
    ([146.83, 196.00, 246.94], 49.00),
    ([146.83, 185.00, 220.00], 36.71),
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



def wind(vis_env):
    """vento da queda: mistura ruído grave/agudo conforme a velocidade (0..1)"""
    noise = rng.normal(0, 1, (N, 2)).astype(np.float32)
    dark = lp(noise, 350, 2) * 2.2
    bright = bp(noise, 900, 5000, 2) * 0.9
    v = vis_env[:, None]
    gust = (1 + 0.25 * np.sin(2 * np.pi * 0.4 * np.arange(N)[:, None] / SR + np.array([0, 1.3])[None, :]))
    return (dark * v * (0.5 + 0.5 * (1 - v)) + bright * v ** 2) * gust


def lava_gurgle(dur):
    n = int(dur * SR); v = np.zeros(n, np.float32)
    for _ in range(int(dur * 6)):
        s = rng.integers(0, max(1, n - 6000)); m = int(SR * rng.uniform(0.05, 0.12)); tt = np.arange(m) / SR
        f = rng.uniform(60, 140) * (1 + 0.8 * tt / tt[-1])
        v[s:s + m] += (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1])).astype(np.float32)
    return lp(v, 400).astype(np.float32)


def hum(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = sum(np.sin(2 * np.pi * 120 * k * tt) / k for k in (1, 2, 3, 5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 6 * tt))
    return (v * adsr(n, 0.25, 0.4) * 0.5).astype(np.float32)


def splash():
    n = int(1.0 * SR); tt = np.arange(n) / SR
    return (bp(rng.normal(0, 1, n), 300, 4000) * np.exp(-tt / 0.18) + lp(rng.normal(0, 1, n), 200) * np.exp(-tt / 0.3) * 2).astype(np.float32)


def fall_whistle(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 1400 * np.power(300 / 1400, tt / dur)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * adsr(n, 0.05, 0.2) * 0.5).astype(np.float32)


def stateAt_factory():
    q = TL["queda"]; TQ = q["total"]; am = q["amostras"] + [{"t": TQ, "prof": 12742, "v": 0, "temp": 15}]
    dt = am[1]["t"] - am[0]["t"]; v = np.array([a["v"] for a in am]); prof = np.array([a["prof"] for a in am])
    def f(s):
        P = 2 * TQ; u = s % P
        if u > TQ: u = P - u
        x = u / dt; k = min(len(am) - 2, int(x)); w = x - k
        return prof[k] * (1 - w) + prof[k + 1] * w, v[k] * (1 - w) + v[k + 1] * w
    return f, TQ


def main():
    stf, TQ = stateAt_factory()
    sim = np.array(TL["sim"])
    hook_end = L["hook"]["end"]
    rew = (hook_end + 0.25, hook_end + 0.95)
    jump = TL["jump"]
    end = T
    sc = {"jump": L["pulo"]["start"] - 0.35, "shaft": jump + 0.75, "onde": L["onde"]["start"] - 0.35,
          "volta": L["volta"]["start"] - 0.35, "cta": L["cta"]["start"] - 0.35}
    arrive = Wt("hook", 19, "t1") + 0.1
    t_center = None
    for i, s in enumerate(sim):
        if i / FPS > jump and stf(s)[0] >= 6371:
            t_center = i / FPS; break

    E = {
        "pad": env_points([(0, 0.5), (rew[0], 0.5), (rew[0] + 0.1, 0), (rew[1], 0), (rew[1] + 0.4, 0.5), (sc["shaft"], 0.6),
                           (t_center, 0.8), (sc["onde"], 0.6), (sc["volta"], 0.6), (end - 1, 0.55), (end, 0.5)]),
        "choir": env_points([(0, 0), (sc["shaft"], 0), (L["nucleo"]["start"], 0.5), (t_center, 1), (L["freio"]["end"], 0.6),
                             (sc["onde"], 0.8), (sc["volta"], 0.4), (end - 1, 0.5), (end, 0)]),
        "arp_dark": env_points([(0, 0.7), (rew[0], 0.7), (rew[0] + 0.1, 0), (L["pulo"]["start"], 0), (L["pulo"]["start"] + 0.3, 0.7),
                                (L["freio"]["end"], 0.6), (sc["onde"], 0.6), (end, 0.7)]),
        "arp_bright": env_points([(0, 0), (L["manto"]["start"], 0), (L["manto"]["start"] + 0.3, 0.5), (t_center, 0.9),
                                  (L["freio"]["end"], 0.4), (sc["onde"], 0.6), (sc["volta"], 0.8), (end, 0.6)]),
        "bass": env_points([(0, 0), (L["pulo"]["start"], 0), (L["pulo"]["start"] + 0.3, 0.5), (t_center, 0.9),
                            (L["freio"]["end"], 0.4), (sc["onde"], 0.6), (end - 0.4, 0.5), (end, 0.2)]),
        "kick": env_points([(0, 0), (L["crosta"]["start"] - 0.05, 0), (L["crosta"]["start"], 0.7), (t_center - 1.0, 0.9),
                            (t_center - 0.9, 0), (t_center, 0), (t_center + 0.05, 1), (L["freio"]["start"] + 1, 0.8),
                            (L["freio"]["end"], 0), (sc["volta"], 0), (sc["volta"] + 0.05, 0.8), (end - 0.5, 0.8), (end - 0.45, 0)]),
        "ticks": env_points([(0, 0.35), (end, 0.35)]),
    }
    stems = {"pad": make_pad(), "choir": make_choir(), "arp_dark": make_arp(False), "arp_bright": make_arp(True),
             "bass": make_bass(), "kick": make_kicks(), "ticks": make_clock_ticks()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music = np.tanh(music * 1.2) / 1.2

    sfx = np.zeros((N + SR * 3, 2), np.float32)
    # vento guiado pela velocidade real da queda (só dentro do túnel)
    tt = np.arange(N) / SR
    fr = np.clip((tt * FPS).astype(int), 0, len(sim) - 1)
    vel = np.array([stf(s)[1] for s in sim])[fr]
    vis = np.clip(np.log10(1 + vel / 120) / 2.5, 0, 1)
    inside = ((tt > sc["shaft"] - 0.3) & (tt < sc["onde"] + 0.2)).astype(np.float32)
    inside = np.convolve(inside, np.ones(SR // 5) / (SR // 5), mode="same")
    # o vento abaixa quando o narrador fala (ducking próprio, já que o ruído mascara a voz)
    _, vz = wavfile.read(B / "voz.wav")
    vz = np.abs(vz.astype(np.float32) / 32768)[:N]
    vz = np.pad(vz, (0, max(0, N - len(vz))))
    k = SR // 20
    envv = np.convolve(vz, np.ones(k) / k, mode="same")
    envv = np.maximum.accumulate(envv[::-1])[::-1] * 0 + envv  # (mantém forma)
    rel = np.copy(envv)
    a_rel = math.exp(-1 / (0.35 * SR))
    for i in range(1, N):
        if rel[i] < rel[i - 1] * a_rel:
            rel[i] = rel[i - 1] * a_rel
    duck = 1 - 0.7 * np.clip(rel / 0.04, 0, 1)
    sfx[:N] += wind((0.12 + 0.88 * vis) * inside) * (0.07 * duck)[:, None]
    # gancho
    add(sfx, riser(arrive - Wt("hook", 10)), Wt("hook", 10), 0.13)
    add(sfx, impact(0.6), arrive, 0.13)
    add(sfx, ding(1760), arrive + 0.02, 0.12)
    add(sfx, whoosh(0.9, 300, 2500), Wt("hook", 3), 0.22)
    add(sfx, rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.25)
    # pulo
    add(sfx, pop(380), jump, 0.18)
    add(sfx, fall_whistle(0.9), jump + 0.35, 0.12)
    for t0 in sc.values():
        add(sfx, whoosh(0.45, 300, 4000), t0 - 0.25, 0.28)
    add(sfx, ding(1318.5), Wt("pulo", 13), 0.08)
    # entradas nas camadas
    prev = 0.0
    for i, s in enumerate(sim):
        t0 = i / FPS
        if t0 < sc["shaft"] or t0 > sc["onde"]:
            continue
        d = stf(s)[0]
        for b in (35, 2890, 5150):
            if prev < b <= d:
                add(sfx, impact(0.4), t0, 0.1); add(sfx, whoosh(0.5, 200, 3000), t0 - 0.2, 0.25)
        prev = d
    # núcleo: borbulhar de ferro líquido; campo magnético: zumbido elétrico
    add(sfx, lava_gurgle(L["centro"]["end"] - L["nucleo"]["start"]), L["nucleo"]["start"], 0.14)
    add(sfx, hum(L["nucleo"]["end"] - Wt("nucleo", 13) + 0.5), Wt("nucleo", 13) - 0.1, 0.03)
    add(sfx, ding(1046.5), Wt("nucleo", 16), 0.08)
    # Sol x Terra
    add(sfx, pop(520), Wt("centro", 8) - 0.1, 0.15)
    add(sfx, ding(1568), Wt("centro", 13), 0.1)
    # centro: velocidade máxima
    add(sfx, impact(0.9), t_center, 0.09)
    add(sfx, whoosh(1.2, 200, 7000), Wt("centro", 20) - 0.2, 0.18)
    # saída e onde: giro do globo + splash
    add(sfx, ding(2093), Wt("freio", 12), 0.1)
    add(sfx, whoosh(1.2, 200, 3000), Wt("onde", 7), 0.3)
    add(sfx, splash(), Wt("onde", 13), 0.25)
    for k in range(6):
        add(sfx, bubble(), Wt("onde", 13) + 0.2 + k * 0.1, 0.08, pan=rng.uniform(-0.5, 0.5))
    add(sfx, pop(600), Wt("onde", 16), 0.12); add(sfx, pop(700), Wt("onde", 19), 0.12)
    # indo e voltando: um whoosh a cada passagem pelo centro
    prev = None
    for i in range(int(sc["volta"] * FPS), int(sc["cta"] * FPS)):
        d = stf(sim[i])[0]
        side = d > 6371
        if prev is not None and side != prev:
            add(sfx, whoosh(0.35, 400, 5000), i / FPS - 0.15, 0.22)
        prev = side
    for k, f in enumerate([659.3, 830.6, 987.8, 1318.5]):
        add(sfx, ding(f), Wt("volta", 14) + k * 0.1, 0.07)
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.5)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    add(sfx, whoosh(0.6, 300, 2500), T - 0.6, 0.2)
    sfx = sfx[:N]

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
