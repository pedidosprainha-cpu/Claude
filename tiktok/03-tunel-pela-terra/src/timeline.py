"""Linha do tempo do vídeo 03: falas, legendas e o "tempo de queda" simulado (sim) por quadro.

Saídas: build/timeline.json e build/voz.wav
"""
import json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
FPS, SR = 30, 48000

GAP = {"hook": 1.05, "pulo": 0.3, "crosta": 0.3, "manto": 0.3, "nucleo": 0.3, "centro": 0.4,
       "freio": 0.45, "onde": 0.45, "volta": 0.5, "cta": 1.1}

LEGENDA = {
    "hook": "Se você / pulasse num / túnel que / atravessa a / Terra inteira... / chegaria do / outro lado / em só / 38_minutos.{4}",
    "pulo": "Bora pular. / Sem ar / no túnel, / você cai / cada vez / mais rápido... / e flutua, / sem peso / nenhum, / o caminho / todo.",
    "crosta": "Em 1min30,{4} / você atravessa / a crosta. / Uma casquinha / de 35_km.{4}",
    "manto": "Depois, / quase 3_mil_km{3} / de manto: / rocha tão / quente que / se move, / bem devagar, / como massinha.",
    "nucleo": "Aos 13 / minutos, / você entra / no núcleo / externo: / um oceano / de ferro / derretido, / que cria / o campo / magnético / da Terra.",
    "centro": "E no centro, / uma bola / de ferro / sólido, / tão quente / quanto a / superfície / do Sol. / Você passa / por ela / a mais de / 35_mil_km§h.{7}",
    "freio": "A partir daí, / a gravidade / te freia... / até você / parar, / exatamente / na saída / do outro / lado.",
    "onde": "E se você / pulasse aqui / do Brasil? / Ia sair / no meio / do oceano / Pacífico... / entre o / Japão / e as Filipinas.",
    "volta": "Mas se / ninguém / te segurar... / você cai / de volta. / E fica / indo e / voltando, / pra sempre.",
    "cta": "Segue pra mais / curiosidades / aleatórias.",
}

EASES = {
    "inout": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2,
    "out": lambda p: 1 - (1 - p) ** 3,
    "in": lambda p: p ** 2,
    "linear": lambda p: p,
    "sine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
}


def main():
    falas = json.loads((B / "tts" / "falas.json").read_text())
    queda = json.loads((B / "queda.json").read_text())
    TQ = queda["total"]
    cz = queda["cruz"]
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
                toks.append({"txt": txt.replace("_", " ").replace("§", "/"), "t0": ws[0]["t0"], "t1": ws[-1]["t1"]})
                wi += n
            pages.append({"line": lid, "t0": toks[0]["t0"], "toks": toks})
        assert wi == len(words), (lid, wi, len(words))
    for i, p in enumerate(pages):
        nxt = pages[i + 1]["t0"] if i + 1 < len(pages) else total
        p["t1"] = min(nxt, p["toks"][-1]["t1"] + 0.6)

    # ---- tempo simulado de queda (s) em função do tempo do vídeo
    segs = []

    def seg(s0, s1, t0, t1, ease="inout"):
        segs.append((round(t0, 3), round(t1, 3), s0, s1, ease))

    jump = W("pulo", 1) + 0.25
    seg(0, TQ, W("hook", 10), W("hook", 19, "t1") + 0.1, "inout")
    seg(TQ, 0, L["hook"]["end"] + 0.25, L["hook"]["end"] + 0.95, "inout")            # rebobina
    seg(0, 55, jump + 0.5, L["pulo"]["end"] + 0.2, "in")
    seg(55, cz["crosta"], L["crosta"]["start"], W("crosta", 8), "linear")
    seg(cz["crosta"], 210, W("crosta", 8), L["crosta"]["end"] + 0.25, "linear")
    seg(210, 700, L["manto"]["start"] - 0.05, L["manto"]["end"] + 0.25, "linear")
    seg(700, cz["manto"], L["nucleo"]["start"] - 0.05, W("nucleo", 6), "linear")
    seg(cz["manto"], 985, W("nucleo", 6), L["nucleo"]["end"] + 0.25, "linear")
    seg(985, cz["nucleo_int"], L["centro"]["start"] - 0.05, W("centro", 4), "linear")
    seg(cz["nucleo_int"], cz["centro"], W("centro", 4), W("centro", 22), "linear")
    seg(cz["centro"], 1300, W("centro", 22), L["centro"]["end"] + 0.35, "linear")
    seg(1300, TQ, L["freio"]["start"] - 0.05, W("freio", 12), "out")
    seg(TQ, TQ * 5, W("volta", 5), L["volta"]["end"] + 0.4, "inout")                 # ida e volta, 2x
    seg(TQ * 5, 0, L["cta"]["end"] + 0.15, total - 0.45, "inout")               # volta ao início (loop)
    segs.sort()

    def sim_at(tt):
        s = 0.0
        for (t0, t1, s0, s1, e) in segs:
            if tt < t0:
                break
            s = s1 if tt >= t1 else s0 + (s1 - s0) * EASES[e]((tt - t0) / (t1 - t0))
        return s

    n = int(math.ceil(total * FPS))
    sim = [round(sim_at(i / FPS), 3) for i in range(n)]
    tl = {"fps": FPS, "total": total, "frames": n, "order": order, "lines": lines, "pages": pages, "sim": sim,
          "jump": jump, "queda": queda}
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
        print(f"  {lid:8s} {L[lid]['start']:6.2f} → {L[lid]['end']:6.2f}   tempo de queda no fim: {sim_at(L[lid]['end']) / 60:5.1f} min")


if __name__ == "__main__":
    main()
