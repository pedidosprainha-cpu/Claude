"""Linha do tempo do vídeo 11: falas, legendas palavra por palavra, rebobinar e marcos de imagem e som.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 0.35, "hook2": 1.0, "nome": 0.45, "labirinto": 0.5, "toquio": 0.55, "regra": 0.45,
       "memoria": 0.6, "fecho": 0.9, "cta": 1.0}

# "/" separa as páginas de legenda; "{n}" junta n palavras faladas num só token; "_" vira espaço.
LEGENDA = {
    "hook": "Essa gosma / amarela / não tem / cérebro. / Nem um / neurônio. / E mesmo assim, / ela redesenhou / a rede / de trens / de Tóquio.",
    "hook2": "Ah, e ela / aprende. / E ensina.",
    "nome": "O nome dela / é Physarum. / E não, / não é fungo. / Nem planta, / nem bicho. / É uma / célula só... / que dá pra ver / a olho nu.",
    "labirinto": "Em 2000, / um cientista / japonês / botou ela / num labirinto, / com comida / na entrada / e na saída. / Ela se espalhou / por tudo... / depois largou / os becos / sem saída, / e sobrou só / o caminho / mais curto.",
    "toquio": "Anos depois, / a equipe dele / fez um mapa / de Tóquio / com flocos / de aveia, / um em cada / cidade. / Em pouco mais / de um dia, / ela ligou / todas... / numa rede / muito parecida / com a dos trens / de verdade.",
    "regra": "O segredo? / Tubo que leva / mais fluxo / engrossa. / Tubo que quase / ninguém usa... / vai sumindo.",
    "memoria": "E fica mais / estranho: / ela deixa / um rastro / pra lembrar / onde já passou, / aprende / a atravessar / o sal, / que ela odeia... / e se você / junta ela / com outra / que nunca / viu sal, / a outra / aprende também.",
    "fecho": "Tudo isso / sem um único / neurônio. / Então me diz: / o que é / inteligência, / afinal?",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}


def main():
    falas = json.loads((B / "tts" / "falas.json").read_text())
    clips = {}
    for f in falas:
        _, x = wavfile.read(B / "tts" / f"{f['id']}.wav")
        clips[f["id"]] = x.astype(np.float32) / 32768
    lines, order, t = {}, [], 0.25
    for f in falas:
        lead = f["words"][0]["t0"]
        start = max(0.0, t - lead)
        words = [{"w": w["w"], "t0": round(start + w["t0"], 3), "t1": round(start + w["t1"], 3)} for w in f["words"]]
        lines[f["id"]] = {"clip": start, "start": words[0]["t0"], "end": words[-1]["t1"], "words": words}
        order.append(f["id"])
        t = start + f["dur"] + GAP[f["id"]]
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

    rew = [L["hook2"]["end"] + 0.15, L["hook2"]["end"] + 0.9]
    W = lambda lid, i, k="t0": L[lid]["words"][i][k]
    marks = {  # instantes compartilhados por imagem (render.js) e som (audio.py)
        "toquio_hook": W("hook", 13), "ensina": W("hook2", 4),
        "lab_bota": W("labirinto", 5), "lab_comida": W("labirinto", 10), "lab_largou": W("labirinto", 21), "lab_curto": W("labirinto", 31),
        "aveia": W("toquio", 11), "liga": W("toquio", 18), "trilhos": W("toquio", 33),
        "engrossa": W("regra", 7), "some": W("regra", 13),
        "rastro": W("memoria", 4), "sal": W("memoria", 13), "junta": W("memoria", 21), "aprende": W("memoria", 34),
        "zero": W("fecho", 5), "pergunta": W("fecho", 6),
    }
    n = int(math.ceil(total * FPS))
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages, "rew": rew, "marks": marks}
    (B / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))

    voz = np.zeros(int((total + 2) * SR), np.float32)
    for lid in order:
        x = clips[lid]; s = int(round(L[lid]["clip"] * SR))
        voz[s:s + len(x)] += x[: len(voz) - s]
    wavfile.write(B / "voz.wav", SR, (np.clip(voz[: int(total * SR)], -1, 1) * 32767).astype(np.int16))
    print(f"duração: {total:.2f}s  quadros: {n}")
    for lid in order:
        print(f"  {lid:10s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}")


if __name__ == "__main__":
    main()
