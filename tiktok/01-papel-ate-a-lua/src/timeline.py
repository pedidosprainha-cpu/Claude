"""Monta a linha do tempo do vídeo a partir das falas geradas.

Saídas:
  build/timeline.json  -> tudo que o render e o áudio precisam (tempos absolutos)
  build/voz.wav        -> faixa de narração já posicionada
"""
import json, math, re, subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS = 30
SR = 48000
PAPEL = 1e-4  # espessura de uma folha comum: 0,1 mm

# Respiro (s) entre o fim de uma fala e o início da próxima.
GAP = {
    "hook": 1.00, "mentira": 0.25, "espessura": 0.20, "dobra": 0.20, "comeco": 0.30,
    "f7": 0.25, "f10": 0.22, "f14": 0.22, "f17": 0.22, "f23": 0.22, "f27": 0.22,
    "f30": 0.22, "f32": 0.30, "f42": 0.50, "f51": 0.30, "f103": 0.55, "mito": 0.20,
    "errado": 0.35, "britney": 0.15, "rolo": 0.40, "licao": 0.35, "cta": 1.00,
}

# Legenda exibida. Um token consome 1 palavra falada; "TOKEN{n}" consome n palavras.
# "/" força quebra de página.
LEGENDA = {
    "hook": "Se você dobrar / uma folha de papel / 42{3} vezes... / ela chega / até a Lua.",
    "mentira": "Parece mentira. / Mas é pura / matemática.",
    "espessura": "Uma folha comum / tem só / 0,1_mm{4}",
    "dobra": "E cada dobra... / dobra / a espessura.",
    "comeco": "No começo, / parece que / nada acontece.",
    "f7": "7 dobras: / a grossura / de um caderno.",
    "f10": "10: / a altura / de uma xícara.",
    "f14": "14: / a altura / de uma pessoa.",
    "f17": "17: / um prédio / de 4 andares.",
    "f23": "23:{3} / passa o / Burj Khalifa, / o prédio / mais alto / do mundo.",
    "f27": "27:{3} / mais alta / que o Everest.",
    "f30": "30: / você chegou / ao espaço.",
    "f32": "32:{3} / passa a / Estação Espacial.",
    "f42": "E com 42...{3} / você toca / a Lua.",
    "f51": "Com 51,{3} / passa do Sol.",
    "f103": "E com 103...{3} / fica maior / que o universo / observável / inteiro.",
    "mito": "Mas dizem / que é impossível / dobrar uma folha / mais de 7 vezes.",
    "errado": "ERRADO.",
    "britney": "Em 2002,{4} / uma estudante / americana / dobrou papel / 12 vezes...",
    "rolo": "usando um rolo / de papel higiênico / de mais de / 1_km.{2}",
    "licao": "Isso é / crescimento / exponencial: / começa devagar... / e depois / EXPLODE.",
    "cta": "Segue pra mais / ciência que / parece mentira.",
}

# Alturas de referência (m) usadas para achar o instante exato em que a pilha cruza cada marco.
MARCOS = {
    "burj": 828.0, "everest": 8849.0, "karman": 100e3, "iss": 408e3,
    "lua": 384_400e3, "sol": 149.6e9, "universo": 8.8e26,
}


def ease_in_out_cubic(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_in_out_sine(p):
    return -(math.cos(math.pi * p) - 1) / 2


EASES = {"inout": ease_in_out_cubic, "out": ease_out_cubic, "sine": ease_in_out_sine,
         "linear": lambda p: p, "in": lambda p: p * p}


def main():
    falas = json.loads((B / "tts" / "falas.json").read_text())

    # ---- posiciona as falas ------------------------------------------------
    lines, t = {}, 0.0
    order = []
    for f in falas:
        lead = f["words"][0]["t0"]
        start = t - lead  # início do clipe de áudio
        if start < 0:
            t, start = lead, 0.0
        words = [{"w": w["w"], "t0": round(start + w["t0"], 3), "t1": round(start + w["t1"], 3)}
                 for w in f["words"]]
        lines[f["id"]] = {"clip": start, "start": words[0]["t0"], "end": words[-1]["t1"], "words": words}
        order.append(f["id"])
        t = words[-1]["t1"] + GAP[f["id"]]
    total = round(t, 3)

    def W(line, i, k="t0"):
        return lines[line]["words"][i][k]

    # ---- legendas ----------------------------------------------------------
    pages = []
    for lid in order:
        words = lines[lid]["words"]
        wi = 0
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

    # ---- programa de dobras --------------------------------------------------
    # mode "steps": dobra a dobra (cada passo anima a duplicação); "smooth": contínuo.
    R = []

    def run(a, b, t0, t1, mode="steps", ease="out", anim=None):
        R.append({"a": a, "b": b, "t0": round(t0, 3), "t1": round(t1, 3), "mode": mode, "ease": ease, "anim": anim})

    L = lines
    # gancho: duas dobras "de verdade" na folha, depois o foguete até a Lua
    run(0, 1, W("hook", 2) + 0.05, W("hook", 2) + 0.45, anim=0.4, ease="inout")
    run(1, 2, W("hook", 5), W("hook", 6, "t1"), anim=0.4, ease="inout")
    run(2, 42, W("hook", 7), W("hook", 15) + 0.08, mode="smooth", ease="in")
    # rebobina
    run(42, 0, L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95, mode="smooth", ease="inout")
    # dobras iniciais
    run(0, 1, W("dobra", 3), W("dobra", 3) + 0.35, anim=0.35)
    run(1, 2, W("dobra", 5), W("dobra", 5) + 0.35, anim=0.35)
    run(2, 3, W("dobra", 5, "t1") - 0.1, W("dobra", 5, "t1") + 0.25, anim=0.35)
    for i, wi in enumerate([1, 2, 4, 5]):
        run(3 + i, 4 + i, W("comeco", wi), W("comeco", wi) + 0.35, anim=0.4)
    run(6, 7, W("f7", 0), W("f7", 0) + 0.35, anim=0.35)

    def milestone(lid, a, b, wi, lead=0.35):
        # termina junto com a palavra do número; nunca começa antes da fala anterior acabar
        t1 = W(lid, wi, "t1") - 0.05
        prev_end = L[order[order.index(lid) - 1]]["end"]
        t0 = max(prev_end + 0.03, min(L[lid]["start"] - lead, t1 - 0.12 * (b - a)))
        run(a, b, t0, t1, anim=0.3)

    milestone("f10", 7, 10, 0)
    milestone("f14", 10, 14, 0)
    milestone("f17", 14, 17, 0)
    milestone("f23", 17, 23, 2)
    milestone("f27", 23, 27, 2)
    milestone("f30", 27, 30, 0)
    milestone("f32", 30, 32, 2, lead=0.1)
    run(32, 41, W("f42", 2), W("f42", 4), anim=0.25)
    run(41, 42, W("f42", 4), W("f42", 8) + 0.12, anim="full", ease="in")
    run(42, 51, W("f51", 0), W("f51", 3) + 0.05, anim=0.22)
    run(51, 103, L["f103"]["start"] - 0.1, W("f103", 5), mode="smooth", ease="sine")
    # mito: volta tudo até 7 dobras
    run(103, 7, W("mito", 0), W("mito", 0) + 1.0, mode="smooth", ease="inout")
    # recorde: 12 dobras
    run(7, 12, W("britney", 8), W("britney", 10) + 0.05, anim=0.25)
    # fim: volta para a folha inteira (loop perfeito com o primeiro frame)
    run(12, 0, L["cta"]["end"] + 0.15, total - 0.35, mode="smooth", ease="inout")

    R.sort(key=lambda r: r["t0"])

    def fold_at(tt):
        f, cnt = 0.0, 0
        for r in R:
            if tt < r["t0"]:
                break
            a, b = r["a"], r["b"]
            if tt >= r["t1"]:
                f, cnt = float(b), b
                continue
            if r["mode"] == "smooth":
                p = (tt - r["t0"]) / (r["t1"] - r["t0"])
                f = a + (b - a) * EASES[r["ease"]](p)
                cnt = int(math.floor(f + 1e-6)) if b > a else int(math.ceil(f - 1e-6))
            else:
                n, s = abs(b - a), (1 if b > a else -1)
                sd = (r["t1"] - r["t0"]) / n
                i = min(int((tt - r["t0"]) / sd), n - 1)
                anim = sd if r["anim"] == "full" else min(sd * 0.95, r["anim"] or 0.3)
                p = min(1.0, (tt - r["t0"] - i * sd) / anim)
                f = a + s * (i + EASES[r["ease"]](p))
                cnt = a + s * (i + 1)
        return f, cnt

    n_frames = int(math.ceil(total * FPS))
    F, C = [], []
    for i in range(n_frames):
        f, c = fold_at(i / FPS)
        F.append(round(f, 5))
        C.append(c)

    # instantes de cada passo de dobra (para o "whoosh")
    steps = []
    for r in R:
        if r["mode"] == "steps":
            n = abs(r["b"] - r["a"])
            sd = (r["t1"] - r["t0"]) / n
            for i in range(n):
                steps.append({"t": round(r["t0"] + i * sd, 3), "gap": round(sd, 3)})

    # instantes em que a pilha cruza os marcos (subindo)
    cross = {}
    fine = np.arange(0, total, 1 / 600)
    ff = np.array([fold_at(x)[0] for x in fine])
    for k, h in MARCOS.items():
        lim = math.log2(h / PAPEL)
        idx = np.where((ff[:-1] < lim) & (ff[1:] >= lim))[0]
        cross[k] = [round(float(fine[j]), 3) for j in idx]

    tl = {
        "fps": FPS, "total": total, "frames": n_frames, "order": order, "lines": lines,
        "pages": pages, "runs": R, "fold": F, "count": C, "steps": steps, "cross": cross,
    }
    (B / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))

    # ---- faixa de voz ------------------------------------------------------
    voz = np.zeros(int((total + 1) * SR), dtype=np.float32)
    for lid in order:
        sr, x = wavfile.read(B / "tts" / f"{lid}.wav")
        x = x.astype(np.float32) / 32768.0
        s = int(round(lines[lid]["clip"] * SR))
        voz[s:s + len(x)] += x[: len(voz) - s]
    voz = voz[: int(total * SR)]
    wavfile.write(B / "voz.wav", SR, (np.clip(voz, -1, 1) * 32767).astype(np.int16))

    print(f"duração total: {total:.2f}s  frames: {n_frames}")
    for lid in order:
        print(f"  {lid:10s} {lines[lid]['start']:6.2f} → {lines[lid]['end']:6.2f}")
    print("cruzamentos:", cross)


if __name__ == "__main__":
    main()
