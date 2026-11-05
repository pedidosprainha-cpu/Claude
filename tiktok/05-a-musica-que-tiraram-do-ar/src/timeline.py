"""Linha do tempo do vídeo 05: falas e legendas.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 1.05, "fita": 0.3, "titulo": 0.55, "contexto": 0.35, "sucesso": 0.3, "pressao": 0.45, "mae": 0.45,
       "ruas": 0.3, "impeach": 0.45, "gabriel": 0.45, "final": 0.6, "cta": 1.1}

LEGENDA = {
    "hook": "Em 1992,{6} / essa música / foi tirada / das rádios... / porque falava / do presidente / da República.",
    "fita": "Em setembro / daquele ano, / um garoto / carioca / de 18 anos / gravou uma / fita demo / e mandou / pra uma rádio / do Rio.",
    "titulo": "A música / se chamava: / Tô Feliz, / Matei o / Presidente.",
    "contexto": "Era um / protesto contra / Fernando Collor, / o presidente / que tinha / confiscado / a poupança / dos brasileiros... / e que agora / estava no meio / de um escândalo / de corrupção.",
    "sucesso": "A rádio / tocou... / e em 5 dias / a música / já estava / entre as / mais pedidas.",
    "pressao": "Mas aí, / as rádios / que tocavam / a música / começaram a ser / pressionadas / pra tirar / ela do ar.",
    "mae": "E tem um / detalhe: / a mãe / do garoto / tinha trabalhado / na campanha / do próprio / Collor.",
    "ruas": "Enquanto isso, / milhares / de jovens, / os caras-pintadas, / tomavam / as ruas / pedindo o / impeachment.",
    "impeach": "Menos de / um mês depois / da estreia / da música, / a Câmara / aprovou o / impeachment. / Collor foi / afastado.",
    "gabriel": "E o garoto? / Virou / Gabriel / o Pensador. / A música / que tentaram / calar / abriu caminho / pra uma carreira / de mais de / 30 anos.",
    "final": "Ah... / e em 2025,{6} / o próprio / Collor / foi preso.",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}
EASES = {"inout": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2, "out": lambda p: 1 - (1 - p) ** 3,
         "linear": lambda p: p, "in": lambda p: p * p}


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

    n = int(math.ceil(total * FPS))
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages,
          "rew": [L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95]}
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
        print(f"  {lid:9s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}")


if __name__ == "__main__":
    main()
