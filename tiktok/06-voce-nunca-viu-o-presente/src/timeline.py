"""Linha do tempo do vídeo 06: falas, legendas e o "tempo de viagem da luz" (tau, em segundos) por quadro.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000
ANO = 365.25 * 86400

GAP = {"hook": 1.1, "luz": 0.4, "lua": 0.35, "sol": 0.4, "proxima": 0.4, "betelgeuse": 0.45, "andromeda": 0.45,
       "webb": 0.55, "virada": 0.6, "fecho": 0.8, "cta": 1.1}

LEGENDA = {
    "hook": "Se o Sol / desaparecesse / agora... / você continuaria / vendo ele / brilhar / por mais / 8 minutos.",
    "luz": "Porque a luz, / a coisa / mais rápida / do universo, / ainda leva / tempo / pra chegar / até os / seus olhos.",
    "lua": "A Lua / que você vê / é a Lua / de 1 segundo / atrás.",
    "sol": "O Sol? / É o Sol / de 8 minutos / e 20 segundos / atrás.",
    "proxima": "Proxima / Centauri, / a estrela / mais próxima: / você vê / como ela era / há mais de / 4 anos.",
    "betelgeuse": "Betelgeuse, / a estrela / vermelha / de Órion: / se ela / explodisse hoje, / a gente só / ia ver / daqui a / mais de / 500 anos.",
    "andromeda": "Andrômeda, / a galáxia / vizinha: / essa luz / saiu de lá / há 2,5_milhões{4} / de anos... / quando nossos / ancestrais / ainda nem / dominavam / o fogo.",
    "webb": "E o telescópio / James Webb / já captou / luz que / viajou / mais de / 13 bilhões / de anos... / quase desde / o começo / do universo.",
    "virada": "Mas não é / só no espaço. / Até a pessoa / do seu lado, / a 1 metro / de você... / você vê / como ela era / há 3 / bilionésimos / de segundo.",
    "fecho": "Tudo o que / você vê / já aconteceu. / Ninguém / nunca viu / o presente.",
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

    # tempo de viagem da luz (s); -1 = sem valor ("—"). Interpolação em escala logarítmica.
    rew = [L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95]
    keys = [  # (tempo do vídeo, tau)
        (0, 499.5), (rew[0], 499.5), (rew[1], -1), (L["lua"]["start"] - 0.4, -1), (L["lua"]["start"] - 0.39, 1e-3),
        (W("lua", 10, "t1"), 1.28),
        (L["sol"]["start"] - 0.2, 1.28), (W("sol", 10, "t1"), 499.5),
        (L["proxima"]["start"] - 0.2, 499.5), (W("proxima", 15, "t1"), 4.24 * ANO),
        (L["betelgeuse"]["start"] - 0.2, 4.24 * ANO), (W("betelgeuse", 20, "t1"), 550 * ANO),
        (L["andromeda"]["start"] - 0.2, 550 * ANO), (W("andromeda", 15, "t1"), 2.5e6 * ANO),
        (L["webb"]["start"] - 0.2, 2.5e6 * ANO), (W("webb", 15, "t1"), 13.0e9 * ANO),
        (W("virada", 17), 13.0e9 * ANO), (W("virada", 26, "t1"), 1 / 299792458),
        (L["cta"]["start"] - 0.3, 1 / 299792458), (L["cta"]["start"] - 0.29, -1),
        (total - 0.45, -1), (total - 0.44, 499.5),
    ]
    def tau_at(tt):
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            if t0 <= tt < t1:
                if v0 < 0 or v1 < 0:
                    return v0
                p = (tt - t0) / (t1 - t0)
                p = p * p * (3 - 2 * p)
                return math.exp(math.log(v0) + (math.log(v1) - math.log(v0)) * p)
        return keys[-1][1]

    n = int(math.ceil(total * FPS))
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages, "rew": rew,
          "tau": [tau_at(i / FPS) for i in range(n)]}
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
