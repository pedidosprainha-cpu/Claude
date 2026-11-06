"""Linha do tempo do vídeo 07: falas, legendas palavra por palavra e trecho do "rebobinar".

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 1.1, "tudo": 0.4, "hidrogenio": 0.45, "carbono": 0.4, "oxigenio": 0.35, "caranguejo": 0.45,
       "ouro": 0.5, "viagem": 0.6, "fecho": 0.9, "cta": 1.1}

# "/" separa as páginas de legenda; "{n}" junta n palavras faladas num só token; "_" vira espaço.
LEGENDA = {
    "hook": "O ferro / que corre / no seu sangue / agora... / foi fabricado / dentro de / estrelas / que explodiram / antes mesmo / de a Terra / existir.",
    "tudo": "E não é / só o ferro. / 90%{3} / da massa / do seu corpo / foi fabricada / dentro de / estrelas.",
    "hidrogenio": "O resto / é hidrogênio, / o átomo / mais antigo / do universo. / Ele surgiu / logo depois / do Big Bang, / há quase / 14 bilhões / de anos.",
    "carbono": "O carbono / do seu DNA / foi forjado / no coração / de estrelas... / e espalhado / pelo espaço / quando elas / morreram.",
    "oxigenio": "O oxigênio / que você / respira / e o cálcio / dos seus ossos / vieram de / estrelas / gigantes / que explodiram: / as supernovas.",
    "caranguejo": "Uma delas / foi vista / daqui da Terra / em 1054.{5} / Brilhou tanto / que dava / pra ver / de dia. / Hoje, / é esta nuvem.",
    "ouro": "E o ouro? / Ele pode / ter nascido / da colisão / de duas / estrelas / mortas, / tão violenta / que faz / o próprio / espaço tremer.",
    "viagem": "Essa poeira / de estrelas / viajou / por bilhões / de anos. / Formou o Sol, / a Terra... / e, um dia, / você.",
    "fecho": "Você não está / só olhando / pro universo. / Você é / o universo... / olhando / pra si mesmo.",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}


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

    rew = [L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95]
    n = int(math.ceil(total * FPS))
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages, "rew": rew}
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
        print(f"  {lid:10s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}")


if __name__ == "__main__":
    main()
