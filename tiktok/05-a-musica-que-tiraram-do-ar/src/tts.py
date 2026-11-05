"""Gera a narração (uma faixa por fala) com marcação de tempo por palavra."""
import asyncio, json, ssl, subprocess, sys
from pathlib import Path
import edge_tts
from edge_tts import communicate

# O contêiner usa um proxy com CA própria; o edge-tts fixa o certifi, então
# trocamos o contexto SSL pelo bundle do ambiente quando ele existir.
CA = Path("/root/.ccr/ca-bundle.crt")
if CA.exists():
    communicate._SSL_CTX = ssl.create_default_context(cafile=str(CA))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "tts"


async def falar(fala, voz, rate, pitch):
    mp3 = OUT / f"{fala['id']}.mp3"
    words = []
    c = edge_tts.Communicate(fala["texto"], voz, rate=rate, pitch=pitch, boundary="WordBoundary")
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"w": ch["text"], "t0": ch["offset"] / 1e7,
                              "t1": (ch["offset"] + ch["duration"]) / 1e7})
    wav = OUT / f"{fala['id']}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1", str(wav)], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(wav)]).decode())
    return {"id": fala["id"], "texto": fala["texto"], "dur": dur, "words": words}


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = json.loads((ROOT / "roteiro.json").read_text())
    res = []
    for fala in r["falas"]:
        res.append(await falar(fala, r["voz"], r["velocidade"], r["tom"]))
        print(f"{fala['id']:10s} {res[-1]['dur']:.2f}s  {len(res[-1]['words'])} palavras")
    (OUT / "falas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("total fala:", round(sum(x["dur"] for x in res), 2), "s")


asyncio.run(main())
