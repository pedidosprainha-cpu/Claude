"""Linha do tempo do vídeo 02: posiciona as falas, legendas e o "relógio da Terra".

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000
DIA = 86400.0
IDADE = 4.54e9  # anos

GAP = {"hook": 1.05, "acelera": 0.3, "nasce": 0.3, "lua": 0.5, "vida": 0.3, "tedio": 0.3, "oxigenio": 0.35,
       "animais": 0.35, "dinos": 0.3, "asteroide": 0.55, "mamiferos": 0.3, "humanos": 0.35, "piramides": 0.35,
       "vidahum": 0.45, "reflexao": 0.55, "cta": 1.1}

# "TOKEN{n}" consome n palavras; "_" vira espaço; "/" quebra página
LEGENDA = {
    "hook": "Se toda / a história / da Terra / coubesse em / um único dia... / nós só / apareceríamos / nos últimos / 6_segundos.{2}",
    "acelera": "Bora acelerar / o tempo. / Cada hora / vale / 189{5} milhões / de anos.",
    "nasce": "Meia-noite: / a Terra nasce. / Uma bola / de rocha / derretida.",
    "lua": "Meia-noite e 13, / um planeta / do tamanho / de Marte / bate em cheio / na Terra... / e os destroços / formam a Lua.",
    "vida": "4 da manhã: / surge a / primeira vida. / Micróbios / minúsculos, / no oceano.",
    "tedio": "E aí... / por horas / e horas, / quase nada / muda. / A vida continua / microscópica.",
    "oxigenio": "Perto do / meio-dia, / bactérias / começam a / encher o ar / de oxigênio.",
    "animais": "9 da noite: / finalmente, / os mares / se enchem / de animais.",
    "dinos": "15 pras 11, / chegam os / dinossauros.",
    "asteroide": "E às / 23:39...{5} / um asteroide / acaba com / a festa.",
    "mamiferos": "Os mamíferos / assumem / o planeta.",
    "humanos": "E nós? / Só aparecemos / 6_segundos{2} / antes da / meia-noite.",
    "piramides": "As pirâmides / do Egito? / Menos de / um décimo / de segundo / atrás.",
    "vidahum": "E uma vida / inteira de / 80 anos... / dura / 1,5_milésimo{4} / de segundo.",
    "reflexao": "Então / pensa bem / no que você / vai fazer / com o seu.",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}

EASES = {
    "inout": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2,
    "out": lambda p: 1 - (1 - p) ** 3,
    "out5": lambda p: 1 - (1 - p) ** 5,
    "linear": lambda p: p,
    "sine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
}


def hms(c):
    c = c % DIA
    h, r = divmod(c, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def main():
    falas = json.loads((B / "tts" / "falas.json").read_text())
    lines, order, t = {}, [], 0.0
    for f in falas:
        lead = f["words"][0]["t0"]
        start = max(0.0, t - lead)
        words = [{"w": w["w"], "t0": round(start + w["t0"], 3), "t1": round(start + w["t1"], 3)} for w in f["words"]]
        lines[f["id"]] = {"clip": start, "start": words[0]["t0"], "end": words[-1]["t1"], "words": words}
        order.append(f["id"])
        t = words[-1]["t1"] + GAP[f["id"]]
    total = round(t, 3)
    L = lines

    def W(line, i, k="t0"):
        return L[line]["words"][i][k]

    # ---- legendas
    pages = []
    for lid in order:
        words, wi = L[lid]["words"], 0
        for chunk in LEGENDA[lid].split("/"):
            toks = []
            for tok in chunk.split():
                m = re.match(r"^(.*)\{(\d+)\}$", tok)
                txt, n = (m.group(1), int(m.group(2))) if m else (tok, 1)
                ws = words[wi:wi + n]
                assert ws, (lid, tok)
                toks.append({"txt": txt.replace("_", " "), "t0": ws[0]["t0"], "t1": ws[-1]["t1"]})
                wi += n
            pages.append({"line": lid, "t0": toks[0]["t0"], "toks": toks})
        assert wi == len(words), (lid, wi, len(words))
    for i, p in enumerate(pages):
        nxt = pages[i + 1]["t0"] if i + 1 < len(pages) else total
        p["t1"] = min(nxt, p["toks"][-1]["t1"] + 0.6)

    # ---- relógio (segundos do "dia" da Terra)
    H = 3600.0
    segs = []

    def seg(c0, c1, t0, t1, ease="inout"):
        segs.append((round(t0, 3), round(t1, 3), c0, c1, ease))

    seg(0, DIA - 6, W("hook", 1), W("hook", 16) + 0.05, "inout")
    seg(DIA - 6, 0, L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95, "inout")              # rebobina
    seg(0, 13 * 60, W("lua", 0), W("lua", 2, "t1"), "out")
    seg(13 * 60, 4 * H, L["vida"]["start"] - 0.3, W("vida", 0, "t1"), "out")
    seg(4 * H, 10.6 * H, W("tedio", 2), L["tedio"]["end"], "linear")
    seg(10.6 * H, 11 * H + 19 * 60, L["oxigenio"]["start"] - 0.1, W("oxigenio", 2, "t1"), "out")
    seg(11 * H + 19 * 60, 21 * H + 9 * 60, L["animais"]["start"] - 0.35, W("animais", 2, "t1"), "inout")
    seg(21 * H + 9 * 60, 22 * H + 45 * 60, L["dinos"]["start"] - 0.25, W("dinos", 2, "t1"), "out")
    seg(22 * H + 45 * 60, 23 * H + 39 * 60, W("asteroide", 1), W("asteroide", 6, "t1"), "out")
    seg(23 * H + 39 * 60, DIA - 60, W("mamiferos", 0), L["mamiferos"]["end"] + 0.25, "linear")
    seg(DIA - 60, DIA - 6, W("humanos", 2), W("humanos", 5, "t1"), "out5")
    seg(DIA - 6, DIA - 4500 / IDADE * DIA, W("piramides", 4), W("piramides", 7, "t1"), "out5")
    seg(DIA - 4500 / IDADE * DIA, DIA - 80 / IDADE * DIA, W("vidahum", 7), W("vidahum", 11, "t1"), "out5")
    seg(DIA - 80 / IDADE * DIA, DIA, L["cta"]["end"] + 0.15, total - 0.45, "inout")           # meia-noite -> loop
    segs.sort()

    def clock_at(tt):
        c = 0.0
        for (t0, t1, c0, c1, e) in segs:
            if tt < t0:
                break
            c = c1 if tt >= t1 else c0 + (c1 - c0) * EASES[e]((tt - t0) / (t1 - t0))
        return c

    n = int(math.ceil(total * FPS))
    clock = [clock_at(i / FPS) for i in range(n)]

    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages,
          "clock": clock, "segs": segs}
    (B / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))

    voz = np.zeros(int((total + 1) * SR), np.float32)
    for lid in order:
        _, x = wavfile.read(B / "tts" / f"{lid}.wav")
        s = int(round(L[lid]["clip"] * SR))
        x = x.astype(np.float32) / 32768
        voz[s:s + len(x)] += x[: len(voz) - s]
    wavfile.write(B / "voz.wav", SR, (np.clip(voz[: int(total * SR)], -1, 1) * 32767).astype(np.int16))

    print(f"duração: {total:.2f}s  quadros: {n}")
    for lid in order:
        print(f"  {lid:10s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}   relógio no fim: {hms(clock_at(L[lid]['end']))}")


if __name__ == "__main__":
    main()
