"""Trilha original no estilo pop-rock anos 90 + efeitos (tudo sintetizado; nenhuma música real é usada).

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
rng = np.random.default_rng(90)


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
    return 2 * ((f * np.arange(n) / SR + phase) % 1.0) - 1


def adsr(n, a, r, sus=1.0):
    e = np.ones(n, np.float32) * sus
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, sus, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


# ---------------------------------------------------------------- harmonia
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
FUN = [([196.0, 246.94, 293.66], 98.0), ([146.83, 185.0, 220.0], 73.42), ([164.81, 196.0, 246.94], 82.41), ([130.81, 164.81, 196.0], 65.41)]   # G D Em C
SERIO = [([164.81, 196.0, 246.94], 82.41), ([130.81, 164.81, 196.0], 65.41), ([220.0, 261.63, 329.63], 55.0 * 2), ([246.94, 311.13, 369.99], 61.74)]  # Em C Am B
T_FUN = Wt("nome", 4)  # vira banda de humor


def chord_at(t):
    prog = FUN if (t < L["hook"]["end"] + 0.3 or t >= T_FUN) else SERIO
    return prog[int(t // BAR) % 4]


# ---------------------------------------------------------------- instrumentos
def kick():
    n = int(0.45 * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * np.cumsum(48 + 110 * np.exp(-tt / 0.03)) / SR) * np.exp(-tt / 0.2)
    v[:150] += rng.normal(0, 0.4, 150) * np.linspace(1, 0, 150)
    return v.astype(np.float32)


def snare():
    n = int(0.3 * SR); tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, n), 1200, 7000) * np.exp(-tt / 0.12) * 0.9 + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt / 0.06) * 0.8
    return v.astype(np.float32)


def hat(open_=False):
    n = int((0.25 if open_ else 0.05) * SR); tt = np.arange(n) / SR
    return (hp(rng.normal(0, 1, n), 7000) * np.exp(-tt / (0.09 if open_ else 0.015))).astype(np.float32)


K, S, HH, HO = kick(), snare(), hat(), hat(True)


def drums():
    kk = np.zeros((N, 2), np.float32); ss = np.zeros((N, 2), np.float32); hh = np.zeros((N, 2), np.float32)
    for b in range(int(T / BEAT) + 1):
        t0 = b * BEAT
        add(kk, K, t0, 0.5 if b % 2 == 0 else 0.35)
        if b % 2 == 1: add(ss, S, t0, 0.42)
        add(hh, HH, t0, 0.16, pan=0.3); add(hh, HH, t0 + BEAT / 2, 0.11, pan=0.3)
        if b % 8 == 7: add(hh, HO, t0 + BEAT / 2, 0.12, pan=0.3)
    return kk, ss, hh


def bass():
    out = np.zeros((N, 2), np.float32)
    pat = [1, 1, 2, 1, 1, 1, 2, 1.5]
    for k in range(int(T / (BEAT / 2)) + 1):
        t0 = k * BEAT / 2
        _, root = chord_at(t0)
        f = root * pat[k % 8]
        n = int(0.26 * SR); tt = np.arange(n) / SR
        v = np.tanh(2.5 * (0.6 * saw(f, n) + 0.6 * np.sin(2 * np.pi * f * tt))) * np.exp(-tt / 0.22) * adsr(n, 0.004, 0.04)
        add(out, v.astype(np.float32), t0, 0.22)
    return lp(out, 900)


def guitar(chug):
    """acordes de potência distorcidos (dois canais levemente defasados)"""
    out = np.zeros((N, 2), np.float32)
    step = BEAT / 2
    for k in range(int(T / step) + 1):
        t0 = k * step
        _, root = chord_at(t0)
        f = root * 2
        dur = 0.16 if chug else step * 1.02
        n = int(dur * SR); tt = np.arange(n) / SR
        for ch, det in ((0, 0.997), (1, 1.003)):
            v = sum(saw(f * m * det, n, rng.random()) for m in (1, 1.5, 2)) / 3
            v = np.tanh(5 * v) * (np.exp(-tt / 0.08) if chug else adsr(n, 0.005, 0.03))
            x = np.zeros((n, 2), np.float32); x[:, ch] = v * 0.12
            add(out, x, t0 + ch * 0.008)
    return lp(out, 3200)


def organ():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, _ = chord_at(b * BAR + 0.01)
        n = int((BAR + 0.3) * SR); tt = np.arange(n) / SR; e = adsr(n, 0.08, 0.3)
        v = sum(np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(4 * np.pi * f * tt) + 0.25 * np.sin(6 * np.pi * f * tt) for f in notes)
        v = v * (1 + 0.15 * np.sin(2 * np.pi * 6 * tt)) * e * 0.05
        add(out, v.astype(np.float32), b * BAR)
    return out


def piano():
    out = np.zeros((N, 2), np.float32)
    for k in range(int(T / (BEAT / 2)) + 1):
        t0 = k * BEAT / 2
        notes, _ = chord_at(t0)
        f = [notes[0] * 2, notes[1] * 2, notes[2] * 2, notes[1] * 2][k % 4]
        n = int(1.2 * SR); tt = np.arange(n) / SR
        v = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt) * np.exp(-tt / 0.3) + 0.15 * np.sin(6 * np.pi * f * tt) * np.exp(-tt / 0.15)) * np.exp(-tt / 0.6)
        add(out, v.astype(np.float32), t0, 0.08, pan=0.3 if k % 2 else -0.3)
    return out


def pad():
    out = np.zeros((N, 2), np.float32)
    for b in range(int(math.ceil(T / BAR)) + 1):
        notes, _ = chord_at(b * BAR + 0.01)
        n = int((BAR + 0.8) * SR); e = adsr(n, 0.6, 0.8)
        for f in notes:
            for ch, det in ((0, -0.004), (1, 0.004)):
                v = sum(saw(f * (1 + det * q), n, rng.random()) for q in (-1, 1)) / 2
                x = np.zeros((n, 2), np.float32); x[:, ch] = v * e * 0.08
                add(out, x, b * BAR)
    return lp(out, 1500)


# ---------------------------------------------------------------- efeitos
def whoosh(dur=0.3, lo=400, hi=3500):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur; noise = rng.normal(0, 1, n)
    return ((bp(noise, lo, lo * 2.5) * (1 - p) + bp(noise, hi / 2.5, hi) * p) * np.sin(np.pi * p) ** 1.5).astype(np.float32)


def riser(dur):
    n = int(dur * SR); tt = np.arange(n) / SR; p = tt / dur; noise = rng.normal(0, 1, n)
    nz = hp(noise, 300) * (1 - p) * 0.5 + hp(noise, 3000) * p
    tone = np.sin(2 * np.pi * np.cumsum(160 * np.power(1500 / 160, p)) / SR)
    return ((0.5 * nz + 0.5 * tone) * np.power(p, 2.2)).astype(np.float32)


def impact(size=1.0):
    n = int(2.4 * SR); tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(34 + 60 * np.exp(-tt / 0.08)) / SR) * np.exp(-tt / (0.8 * size))
    crash = hp(rng.normal(0, 1, n), 3000) * np.exp(-tt / (0.6 * size)) * 0.4
    return np.tanh(1.5 * (boom + crash)).astype(np.float32)


def tape_rewind(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = 900 + 600 * np.sin(2 * np.pi * 13 * tt) + 400 * np.sin(2 * np.pi * 3.1 * tt)
    v = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + rng.normal(0, 0.4, n)
    return (bp(v, 600, 5000) * (0.6 + 0.4 * np.sin(2 * np.pi * 21 * tt)) * adsr(n, 0.05, 0.12)).astype(np.float32)


def sad_trombone():
    out = []
    for k, (f, d) in enumerate([(293.66, 0.24), (277.18, 0.24), (261.63, 0.24), (246.94, 0.75)]):
        n = int(d * SR); tt = np.arange(n) / SR
        vib = 1 + (0.012 * np.sin(2 * np.pi * 6 * tt) if k == 3 else 0)
        v = saw(1, n) * 0
        ph = np.cumsum(f * vib) / SR
        v = np.tanh(2 * (2 * (ph % 1) - 1)) * adsr(n, 0.04, 0.12)
        out.append(lp(v, 1400))
    return np.concatenate(out).astype(np.float32)


def cricket(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    gate = (np.sin(2 * np.pi * 28 * tt) > 0.2) * (np.sin(2 * np.pi * 1.6 * tt) > -0.1)
    return (np.sin(2 * np.pi * 4600 * tt) * gate * adsr(n, 0.2, 0.3) * 0.5).astype(np.float32)


def claps(dur, density=40):
    n = int(dur * SR); v = np.zeros(n, np.float32)
    for _ in range(int(dur * density)):
        s = rng.integers(0, n - 2000); m = int(SR * 0.02)
        v[s:s + m] += (rng.normal(0, 1, m) * np.exp(-np.arange(m) / (m / 5))).astype(np.float32)
    return (bp(v, 800, 6000) * adsr(n, 0.3, 0.6)).astype(np.float32)


def cheer(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    v = bp(rng.normal(0, 1, n), 400, 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    return (v * adsr(n, 0.4, 0.8)).astype(np.float32)


def clunk():
    n = int(0.6 * SR); tt = np.arange(n) / SR
    v = np.sin(2 * np.pi * np.cumsum(60 + 40 * np.exp(-tt / 0.02)) / SR) * np.exp(-tt / 0.12) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.008) * 0.6
    return v.astype(np.float32)


def ding(f=1318.5):
    n = int(0.8 * SR); tt = np.arange(n) / SR
    return ((np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt / 0.2)).astype(np.float32)


def pop(f=600):
    n = int(0.12 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-tt / 0.02))) / SR) * np.exp(-tt / 0.035)).astype(np.float32)


def click():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01) + hp(rng.normal(0, 1, n), 2000) * np.exp(-tt / 0.004)).astype(np.float32)


def kaching():
    n = int(0.9 * SR); tt = np.arange(n) / SR
    bell = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, d in [(2637, 0.4), (3520, 0.3), (5274, 0.15)])
    coins = hp(rng.normal(0, 1, n), 5000) * np.exp(-tt / 0.05) * 0.5
    return (bell * 0.6 + coins).astype(np.float32)


def main():
    rew = TL["rew"]
    end = T
    queda0, off0 = L["queda"]["start"], Wt("queda", 19)
    leg0, later = L["legado"]["start"], Wt("legado", 7)
    nm = Wt("nome", 14)
    sc = {"garagem": L["antes"]["start"] - 0.35, "loja": L["fracasso"]["start"] - 0.3, "palco": L["virada"]["start"] - 0.35,
          "nome": L["nome"]["start"] - 0.3, "explosao": L["explosao"]["start"] - 0.3, "pilha": L["pilha"]["start"] - 0.3,
          "fenomeno": L["fenomeno"]["start"] - 0.3, "cta": L["cta"]["start"] - 0.35}
    fr0, fr1 = Wt("fracasso", 3), L["virada"]["start"] - 0.2

    full = [(0, 1), (rew[0], 1), (rew[0] + 0.08, 0), (rew[1] + 0.1, 0)]
    E = {
        "kick": env_points(full + [(sc["garagem"] + 0.3, 0.95), (fr0, 0.95), (fr0 + 0.05, 0), (fr1, 0), (fr1 + 0.05, 0.7), (nm - 1.2, 0.7), (nm - 1.15, 0),
                                  (nm, 0), (nm + 0.02, 1), (queda0 + 0.6, 1), (queda0 + 1.4, 0), (later, 0), (later + 0.3, 0.6), (end - 0.4, 0.8), (end, 0.6)]),
        "snare": env_points(full + [(sc["garagem"] + 0.3, 0.9), (fr0, 0.9), (fr0 + 0.05, 0), (fr1, 0), (fr1 + 0.05, 0.6), (nm - 1.2, 0.6), (nm - 1.15, 0),
                                   (nm, 0), (nm + 0.02, 1), (queda0 + 0.6, 1), (queda0 + 1.4, 0), (later, 0), (later + 0.3, 0.6), (end, 0.7)]),
        "hats": env_points(full + [(sc["garagem"] + 0.3, 0.6), (fr0, 0.6), (fr0 + 0.05, 0), (fr1, 0), (fr1 + 0.05, 0.8), (nm, 0.8), (nm + 0.02, 1),
                                  (queda0 + 0.6, 1), (queda0 + 1.4, 0), (later, 0), (later + 0.3, 0.7), (end, 0.8)]),
        "bass": env_points(full + [(sc["garagem"] + 0.3, 1.0), (fr0, 1.0), (fr0 + 0.05, 0), (fr1, 0), (fr1 + 0.05, 0.7), (nm, 0.7), (nm + 0.02, 1),
                                  (queda0 + 0.6, 1), (queda0 + 1.4, 0), (later, 0), (later + 0.3, 0.7), (end, 0.8)]),
        "gtr_chug": env_points([(0, 0), (sc["garagem"] + 0.3, 0), (sc["garagem"] + 0.4, 1.3), (fr0, 1.3), (fr0 + 0.05, 0), (fr1, 0), (fr1 + 0.05, 0.6), (nm - 0.1, 0.6), (nm, 0), (end, 0)]),
        "gtr_full": env_points(full + [(nm, 0), (nm + 0.02, 0.8), (queda0 + 0.6, 0.8), (queda0 + 1.4, 0), (later, 0), (later + 0.4, 0.5), (sc["cta"], 0.8), (end, 0.8)]),
        "organ": env_points([(0, 0.6), (rew[0], 0.6), (rew[0] + 0.08, 0), (fr1, 0), (fr1 + 0.3, 0.6), (nm, 0.7), (queda0 + 0.6, 0.7), (queda0 + 1.4, 0), (end - 1, 0), (end, 0.5)]),
        "piano": env_points([(0, 0), (queda0 + 1.0, 0), (queda0 + 2.0, 0.0), (leg0 - 0.4, 0), (leg0, 1), (later + 1, 1), (sc["cta"], 0.5), (end, 0.3)]),
        "pad": env_points([(0, 0.3), (queda0, 0.3), (queda0 + 1.5, 0.7), (off0, 0.6), (off0 + 3, 0.25), (leg0, 0.6), (end, 0.4)]),
    }
    kk, ss, hh = drums()
    stems = {"kick": kk, "snare": ss, "hats": hh, "bass": bass(), "gtr_chug": guitar(True), "gtr_full": guitar(False),
             "organ": organ(), "piano": piano(), "pad": pad()}
    music = np.zeros((N, 2), np.float32)
    for k, x in stems.items():
        music += x[:N] * E[k][:, None]
    music = np.tanh(music * 1.3) / 1.3

    sfx = np.zeros((N + SR * 3, 2), np.float32)
    # gancho: contador disparando
    add(sfx, riser(Wt("hook", 9, "t1") - Wt("hook", 3)), Wt("hook", 3), 0.12)
    add(sfx, kaching(), Wt("hook", 9), 0.22)
    for k in range(8):
        add(sfx, pop(500 + k * 60), Wt("hook", 16) + k * (Wt("hook", 19) - Wt("hook", 16)) / 8, 0.08)
    add(sfx, tape_rewind(rew[1] - rew[0] + 0.15), rew[0] - 0.05, 0.28)
    for t0 in sc.values():
        add(sfx, whoosh(0.45, 300, 4000), t0 - 0.25, 0.25)
    add(sfx, ding(1046.5), Wt("antes", 8), 0.08)
    # fracasso: grilos + trombone triste
    add(sfx, cricket(fr1 - fr0 + 0.4), fr0 + 0.1, 0.05)
    add(sfx, sad_trombone(), Wt("fracasso", 6, "t1") + 0.05, 0.2)
    # virada: risadas/aplausos
    add(sfx, cheer(L["virada"]["end"] - Wt("virada", 9) + 0.6), Wt("virada", 9), 0.22)
    add(sfx, claps(L["virada"]["end"] - Wt("virada", 10) + 0.8, 50), Wt("virada", 10), 0.14)
    # nome novo
    add(sfx, riser(nm - Wt("nome", 9)), Wt("nome", 9), 0.12)
    add(sfx, impact(0.6), nm, 0.14)
    for k in range(10):
        add(sfx, pop(600 + k * 40), nm + k * 0.06, 0.07, pan=rng.uniform(-0.6, 0.6))
    # explosão de vendas
    ex = Wt("explosao", 12)
    add(sfx, impact(0.8), ex, 0.18)
    add(sfx, kaching(), Wt("explosao", 16), 0.2)
    add(sfx, cheer(2.0), ex, 0.18)
    # pilha
    for k in range(10):
        add(sfx, pop(300 + k * 50), L["pilha"]["start"] + 0.1 + k * 0.3, 0.06)
    add(sfx, ding(1568), Wt("pilha", 6), 0.08); add(sfx, ding(2093), Wt("pilha", 12), 0.08)
    # fenômeno
    for w in (5, 7, 9):
        add(sfx, pop(520), Wt("fenomeno", w) - 0.15, 0.15)
    # homenagem: as luzes se apagam uma a uma
    for k in range(5):
        add(sfx, clunk(), off0 + 0.15 + k * 0.42, 0.22, pan=(-0.6, -0.3, 0, 0.3, 0.6)[k])
    # legado
    for k, f in enumerate([783.99, 987.77, 1174.66, 1567.98, 1975.53]):
        add(sfx, ding(f), leg0 + k * 0.18, 0.05)
    add(sfx, cheer(L["legado"]["end"] - later + 0.8), later, 0.16)
    add(sfx, click(), Wt("cta", 0) + 0.6, 0.5)
    add(sfx, ding(1568), Wt("cta", 0) + 0.63, 0.12)
    add(sfx, whoosh(0.6, 300, 2500), T - 0.6, 0.2)
    sfx = sfx[:N]

    wavfile.write(B / "musica.wav", SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
    wavfile.write(B / "sfx.wav", SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
    print("musica.wav e sfx.wav prontos", T, "s")


if __name__ == "__main__":
    main()
