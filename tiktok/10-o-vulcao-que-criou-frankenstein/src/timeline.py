"""Linha do tempo do vídeo 10: falas, legendas palavra por palavra, rebobinar e marcos de imagem e som.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 0.3, "hook2": 1.0, "tambora": 0.35, "som": 0.35, "nuvem": 0.35, "verao": 0.5, "suica": 0.4,
       "mary": 0.5, "vampiro": 0.45, "bike": 0.5, "fecho": 0.9, "cta": 1.0}
FITA = None

# "/" separa as páginas de legenda; "{n}" junta n palavras faladas num só token; "_" vira espaço.
LEGENDA = {
    "hook": "Um vulcão / do outro lado / do mundo / ajudou a criar / o Frankenstein.",
    "hook2": "E também / o primeiro / vampiro / aristocrata... / e o avô / da bicicleta.",
    "tambora": "Abril de 1815. / Na Indonésia, / o monte / Tambora / explode, / na maior / erupção / da história / registrada.",
    "som": "O estrondo / foi ouvido / a mais de / 2_mil{2} / quilômetros.",
    "nuvem": "Uma nuvem / de enxofre / cobriu / o planeta / e bloqueou / parte da luz / do Sol.",
    "verao": "Em_1816,{1} / o mundo / ficou / sem verão: / nevou / em junho / nos Estados / Unidos, / e a Europa / passou fome.",
    "suica": "Na Suíça, / choveu / sem parar. / Presos / numa casa / à beira / de um lago, / Lord Byron / e os amigos / fizeram / um desafio: / escrever / histórias / de terror.",
    "mary": "Mary Shelley, / de 18{1} anos, / passou dias / sem ideia... / até imaginar / um cientista / dando vida / a um corpo. / Nasceu / Frankenstein.",
    "vampiro": "Ali também, / o médico / de Byron, / John Polidori, / criou / O Vampiro: / o primeiro / vampiro / aristocrata / da literatura.",
    "bike": "Na Alemanha, / sem aveia, / muitos cavalos / morreram. / E, para alguns / historiadores, / foi por isso / que Karl Drais / inventou / o avô / da bicicleta.",
    "fecho": "Na época, / ninguém sabia / que a culpa / era de / um vulcão. / Isso só / foi descoberto / um século / depois.",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}


def fita(x, words, k, v_end):
    """desacelera a fala a partir da palavra k (velocidade 1 → v_end), como fita perdendo rotação"""
    a = int(words[k]["t0"] * SR)
    rest = len(x) - a
    n_out = int(rest / ((1 + v_end) / 2)) + SR // 10
    s = 1 - (1 - v_end) * np.minimum(1, np.arange(n_out) / (rest / ((1 + v_end) / 2)))
    pos = a + np.concatenate([[0], np.cumsum(s)[:-1]])
    pos = pos[pos < len(x) - 1]
    y = np.concatenate([x[:a], np.interp(pos, np.arange(len(x)), x)]).astype(np.float32)
    remap = lambda ti: ti if ti * SR < a else (a + np.searchsorted(pos, ti * SR)) / SR
    new = [dict(w, t0=remap(w["t0"]), t1=remap(w["t1"])) for w in words]
    return y, new


def main():
    falas = json.loads((B / "tts" / "falas.json").read_text())
    clips = {}
    for f in falas:
        _, x = wavfile.read(B / "tts" / f"{f['id']}.wav")
        x = x.astype(np.float32) / 32768
        if FITA and f["id"] == FITA[0]:
            x, f["words"] = fita(x, f["words"], FITA[1], FITA[2])
        clips[f["id"]] = x
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

    rew = [L["hook2"]["end"] + 0.15, L["hook2"]["end"] + 0.9]
    W = lambda lid, i, k="t0": L[lid]["words"][i][k]
    marks = {  # instantes compartilhados por imagem (render.js) e som (audio.py)
        "boom": W("tambora", 8), "data": W("tambora", 0), "trovao": W("suica", 1), "byron": W("suica", 13),
        "visao": W("mary", 10), "frank": W("mary", 19), "drais": W("bike", 15), "monstro": W("hook", 11),
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
        print(f"  {lid:8s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}")


if __name__ == "__main__":
    main()
