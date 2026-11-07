"""Linha do tempo do vídeo 08: falas, legendas palavra por palavra, rebobinar e o efeito "fita parando".

Em "…e congela na beira", a voz desacelera como uma fita que perde rotação (a velocidade cai até 68%),
o mesmo que um observador distante veria acontecer com quem cai no buraco negro.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 0.6, "nasa": 1.0, "destino": 0.35, "tamanho": 0.35, "queda": 0.25, "luz": 0.45, "tempo": 0.25,
       "congela": 0.75, "cruza": 0.45, "dentro": 0.35, "fim": 1.15, "twist": 0.45, "fecho": 0.9, "cta": 1.0}
FITA = ("congela", 7, 0.68)  # fala, primeira palavra afetada, velocidade final

# "/" separa as páginas de legenda; "{n}" junta n palavras faladas num só token.
LEGENDA = {
    "hook": "Isso é / o que você / veria / se caísse / num buraco / negro.",
    "nasa": "Não é / filme: / é uma / simulação / da NASA.",
    "destino": "O destino / é um / buraco negro / como o / do centro / da nossa / galáxia, / com mais de / 4 milhões / de vezes / a massa / do Sol.",
    "tamanho": "Só o ponto / sem volta, / o horizonte / de eventos, / tem 25{3} milhões / de quilômetros / de diâmetro.",
    "queda": "A queda / dura umas / 3 horas, / com quase / duas voltas / em torno dele.",
    "luz": "A luz / se curva / tanto / que você vê / o disco / de gás / por cima / e por baixo, / ao mesmo / tempo.",
    "tempo": "Mas, / pra quem / ficou olhando / de longe, / você nunca / chega.",
    "congela": "Sua imagem / fica / mais lenta... / mais vermelha... / e congela / na beira.",
    "cruza": "Já pra você, / nada de / especial / acontece. / Você cruza / o ponto / sem volta... / e nem / percebe.",
    "dentro": "Lá dentro, / o próprio / espaço / desaba / rumo ao centro. / Todo caminho / leva pra lá.",
    "fim": "A partir / daí, / faltam / 12,8{3} / segundos. / Seu corpo / é esticado / feito / espaguete... / e tudo / acaba / num piscar / de olhos.",
    "twist": "Mas, se você / só passasse / raspando / e voltasse, / estaria / 36{3} minutos / mais jovem / que quem / ficou / te esperando.",
    "fecho": "Perto de um / buraco negro, / o tempo / não passa / igual pra / todo mundo.",
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
        if f["id"] == FITA[0]:
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

    rew = [L["nasa"]["end"] + 0.15, L["nasa"]["end"] + 0.9]
    W = lambda lid, i, k="t0": L[lid]["words"][i][k]
    marks = {  # instantes compartilhados por imagem (render.js) e som (audio.py)
        "boom": W("hook", 10, "t1") - 0.04, "eht": W("destino", 12), "cross": W("cruza", 12, "t1"),
        "fita": W("congela", 7), "blink": W("fim", 18), "whip": W("twist", 7),
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
