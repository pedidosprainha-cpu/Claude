"""Linha do tempo do vídeo 04: falas, legendas, ano e contador de discos por quadro.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 1.05, "antes": 0.3, "fracasso": 1.25, "virada": 0.3, "nome": 0.35, "explosao": 0.3, "pilha": 0.35,
       "fenomeno": 0.4, "queda": 0.9, "legado": 0.45, "cta": 1.1}

LEGENDA = {
    "hook": "Uma banda / brasileira / vendeu mais de / 2_milhões{2} de discos / com um / único álbum... / e a fama / durou só / 8 meses.",
    "antes": "No comecinho / dos anos 90, / 5 amigos / de Guarulhos / tinham uma / banda de / rock sério: / a Utopia.",
    "fracasso": "Gravaram / um disco... / e quase / ninguém / comprou.",
    "virada": "Mas nos / shows, / a plateia / gostava mesmo / era quando / eles faziam / palhaçada / no palco.",
    "nome": "Então eles / mudaram tudo. / Viraram / uma banda / de humor... / e trocaram / o nome pra / Mamonas / Assassinas.",
    "explosao": "Em 1995,{6} / o primeiro / disco saiu / e explodiu: / mais de / 2_milhões{2} / de cópias.",
    "pilha": "Empilhando / esses CDs, / a pilha / teria / 20_km{2} / de altura. / Mais que / 2 vezes / o Everest.",
    "fenomeno": "Eles estavam / em todo / lugar: / na TV, / no rádio, / em festa / de criança / e de adulto.",
    "queda": "Até que, / em 2 de março / de 1996,{6} / o avião / que levava / a banda / caiu. / Nenhum / dos cinco / sobreviveu.",
    "legado": "Foram só / 8 meses / de sucesso. / Mas, / 30 anos / depois, / o Brasil / ainda sabe / as músicas / deles de cor.",
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

    def program(segs, v0):
        segs = sorted(segs)
        def at(tt):
            v = v0
            for (t0, t1, a, b, e) in segs:
                if tt < t0:
                    break
                v = b if tt >= t1 else a + (b - a) * EASES[e]((tt - t0) / (t1 - t0))
            return v
        return at

    rew0, rew1 = L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95
    ano = program([
        (rew0, rew1, 1995, 1990, "inout"),
        (W("antes", 1), W("antes", 4, "t1"), 1990, 1991, "out"),
        (L["fracasso"]["start"], L["fracasso"]["end"], 1991, 1992, "out"),
        (L["virada"]["start"], L["virada"]["end"], 1992, 1994, "linear"),
        (L["nome"]["start"], W("nome", 4), 1994, 1995, "out"),
        (W("fenomeno", 0), L["fenomeno"]["end"], 1995, 1995.9, "linear"),
        (W("queda", 7), W("queda", 12, "t1"), 1995.9, 1996, "out"),
        (W("legado", 6), W("legado", 9, "t1"), 1996, 2026, "inout"),
        (L["cta"]["end"] + 0.15, total - 0.45, 2026, 1995, "inout"),
    ], 1995)
    discos = program([
        (W("hook", 3), W("hook", 9, "t1"), 0, 2_000_000, "out"),
        (rew0, rew1, 2_000_000, 0, "inout"),
        (W("explosao", 12), W("explosao", 16, "t1"), 0, 2_000_000, "out"),
        (L["cta"]["end"] + 0.15, total - 0.45, 2_000_000, 0, "inout"),
    ], 0)
    n = int(math.ceil(total * FPS))
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages,
          "ano": [round(ano(i / FPS), 4) for i in range(n)], "discos": [round(discos(i / FPS)) for i in range(n)],
          "rew": [rew0, rew1]}
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
