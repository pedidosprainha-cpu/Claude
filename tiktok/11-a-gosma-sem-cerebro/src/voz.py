"""Narração com direção por tomadas (Chatterbox Multilingual, licença MIT, rodando local).

Para cada frase do roteiro:
1. grava N tomadas (sementes diferentes);
2. o Whisper transcreve cada uma: tomada com palavra errada, faltando ou sobrando é descartada;
3. entre as corretas, fica a mais clara (maior confiança do Whisper) com entonação mais viva (variação de F0);
4. as frases são montadas com pausas de respiração variadas, como alguém falando.

A voz usa duas referências: uma brasileira nativa condiciona sotaque e entonação (T3) e outra dá o timbre
(S3Gen). As duas são vozes sintéticas (edge-tts), não de pessoas reais.
No fim, o Whisper marca o tempo de cada palavra (para as legendas) e alinha com o texto do roteiro.

Requer o ambiente com torch + chatterbox-tts + faster-whisper + praat-parselmouth (ver README).
Saída: build/tts/<id>.wav (48 kHz) e build/tts/falas.json, no mesmo formato da série.
"""
import difflib, json, re, sys, unicodedata
from pathlib import Path
import numpy as np
import librosa, parselmouth, torch, torchaudio
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "tts"
TOM = OUT / "tomadas"
SR = 48000


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    s = s.replace("physarum", "fisarum").replace("2000", "dois mil")
    return re.sub(r"[^a-z0-9 ]", " ", s).split()


def wer(ref, hyp):
    a, b = norm(ref), norm(hyp)
    d = np.arange(len(b) + 1)
    for i in range(1, len(a) + 1):
        p = d.copy(); d[0] = i
        for j in range(1, len(b) + 1):
            d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (a[i - 1] != b[j - 1]))
    return d[len(b)] / max(1, len(a))


def frases(texto):
    """divide nas pausas de frase, mantendo a pontuação (… conta como pausa longa)"""
    partes = re.findall(r".+?(?:\.\.\.|[.!?:]|$)(?=\s|$)", texto.strip())
    return [p.strip() for p in partes if p.strip()]


def aparar(y, sr, lim_db=-42):
    """corta silêncio e respiração residual nas pontas, com fade curto"""
    if len(y) == 0:
        return y
    e = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    db = 20 * np.log10(e / (e.max() + 1e-9) + 1e-9)
    on = np.flatnonzero(db > lim_db)
    if not len(on):
        return y
    a = max(0, on[0] * 256 - int(0.03 * sr)); b = min(len(y), (on[-1] + 4) * 256 + int(0.06 * sr))
    y = y[a:b].copy()
    f = int(0.012 * sr); y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y


def recortar_por_palavras(y, sr, palavras, margem0=0.09, margem1=0.16, max_pausa=0.45, pausa_nova=0.3):
    """corta a tomada do início da 1ª palavra ao fim da última e encurta pausas internas longas"""
    if not palavras:
        return y
    trechos = []
    ini = max(0.0, palavras[0].start - margem0)
    for a, b in zip(palavras, palavras[1:]):
        if b.start - a.end > max_pausa:
            trechos.append((ini, a.end + 0.12)); ini = b.start - 0.12 - (pausa_nova - 0.24)
    trechos.append((ini, min(len(y) / sr, palavras[-1].end + margem1)))
    partes = []
    for a, b in trechos:
        seg = y[int(a * sr):int(b * sr)].copy()
        f = min(len(seg) // 4, int(0.012 * sr))
        if f > 1: seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        partes.append(seg)
    return np.concatenate(partes)


def variacao_f0(y, sr):
    f0 = parselmouth.Sound(y, sr).to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=400).selected_array["frequency"]
    f0 = f0[f0 > 0]
    return float(np.std(12 * np.log2(f0 / np.median(f0)))) if len(f0) > 10 else 0.0


def main():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS, Conditionals
    from faster_whisper import WhisperModel
    r = json.loads((ROOT / "roteiro.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True); TOM.mkdir(exist_ok=True)
    so = sys.argv[1:]  # opcional: regravar só algumas falas
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    m.prepare_conditionals(str(ROOT / r["referencia_sotaque"]), exaggeration=r["expressao"]); t3 = m.conds.t3
    m.prepare_conditionals(str(ROOT / r["referencia_timbre"]), exaggeration=r["expressao"])
    m.conds = Conditionals(t3, m.conds.gen)
    wm = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    antigo = {f["id"]: f for f in json.loads((OUT / "falas.json").read_text())} if so and (OUT / "falas.json").exists() else {}
    res, log = [], []
    for fala in r["falas"]:
        if so and fala["id"] not in so:
            res.append(antigo[fala["id"]]); continue
        texto_fala = fala.get("fala", fala["texto"])
        pedacos = frases(texto_fala)
        pausas = fala.get("pausas", [])
        audio = []
        for k, fr in enumerate(pedacos):
            melhores = []
            for s in range(fala.get("tomadas", r["tomadas"])):
                torch.manual_seed(1000 * k + 17 * s + len(fr))
                w = m.generate(fr, language_id=r["idioma"], exaggeration=fala.get("expressao", r["expressao"]),
                               cfg_weight=fala.get("cfg", r["cfg"]), temperature=0.75)
                y = w.squeeze(0).numpy()
                y16 = librosa.resample(y, orig_sr=m.sr, target_sr=16000)
                segs, _ = wm.transcribe(y16, language="pt", beam_size=3, word_timestamps=True)
                segs = list(segs)
                hyp = " ".join(x.text for x in segs)
                lp = float(np.mean([x.avg_logprob for x in segs])) if segs else -9
                y = recortar_por_palavras(y, m.sr, [p for x in segs for p in x.words])
                esperado = 0.36 * len(norm(fr)) + 0.5                       # ~2,8 palavras/s
                lento = max(0.0, len(y) / m.sr / esperado - 1.3)            # tomada arrastada ou com cauda
                nota = -wer(fr, hyp) * 10 - lento * 4 + lp + 0.03 * variacao_f0(y, m.sr)
                melhores.append((nota, s, y, hyp, lp))
                wavfile.write(TOM / f"{fala['id']}_{k}_{s}.wav", m.sr, (np.clip(y, -1, 1) * 32767).astype(np.int16))
                log.append(f"{fala['id']}/{k}/{s}: nota {nota:.3f} wer {wer(fr, hyp):.2f} logp {lp:.2f} dur {len(y) / m.sr:.2f}s (esp {esperado:.1f})  «{hyp.strip()}»")
                print(log[-1], flush=True)
            melhores.sort(key=lambda x: -x[0])
            y = melhores[0][2]
            audio.append(y)
            if k < len(pedacos) - 1:
                pz = pausas[k] if k < len(pausas) else (0.38 if fr.endswith("...") else 0.26)
                audio.append(np.zeros(int(pz * m.sr), np.float32))
        y = np.concatenate(audio)
        y48 = librosa.resample(y, orig_sr=m.sr, target_sr=SR)
        y48 = y48 / (np.abs(y48).max() + 1e-9) * 0.89
        wavfile.write(OUT / f"{fala['id']}.wav", SR, (y48 * 32767).astype(np.int16))
        # tempo de cada palavra do roteiro (texto da legenda), alinhado à transcrição
        segs, _ = wm.transcribe(librosa.resample(y48, orig_sr=SR, target_sr=16000), language="pt", word_timestamps=True, beam_size=5)
        ws = [w for x in segs for w in x.words]
        roteiro = fala["texto"].split()
        alvo = [norm(p) for p in roteiro]
        rec = [(norm(w.word), w.start, w.end) for w in ws]
        A = [" ".join(a) for a in alvo]; Bn = [" ".join(b[0]) for b in rec]
        sm = difflib.SequenceMatcher(a=A, b=Bn, autojunk=False)
        t = [None] * len(roteiro)
        for blk in sm.get_matching_blocks():
            for i in range(blk.size):
                t[blk.a + i] = (rec[blk.b + i][1], rec[blk.b + i][2])
        # palavras sem par: interpola entre vizinhas (ex.: "2000" falado como "dois mil")
        conhecidos = [i for i, x in enumerate(t) if x]
        for i in range(len(t)):
            if t[i] is None:
                a = max([j for j in conhecidos if j < i], default=None); b = min([j for j in conhecidos if j > i], default=None)
                t0 = t[a][1] if a is not None else 0.0
                t1 = t[b][0] if b is not None else len(y48) / SR
                ga = [j for j in range(i, len(t)) if t[j] is None and (b is None or j < b)]
                n = len([j for j in range(a + 1 if a is not None else 0, b if b is not None else len(t))])
                pos = i - (a + 1 if a is not None else 0)
                t[i] = (t0 + (t1 - t0) * pos / n, t0 + (t1 - t0) * (pos + 1) / n)
        words = [{"w": p, "t0": round(a, 3), "t1": round(b, 3)} for p, (a, b) in zip(roteiro, t)]
        res.append({"id": fala["id"], "texto": fala["texto"], "dur": round(len(y48) / SR, 3), "words": words})
        print(f"== {fala['id']}: {res[-1]['dur']:.2f}s, {len(words)} palavras, {len(roteiro) - len(conhecidos)} interpoladas", flush=True)
    (OUT / "falas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    (OUT / "tomadas.log").write_text("\n".join(log))
    print("total fala:", round(sum(x["dur"] for x in res), 2), "s")


if __name__ == "__main__":
    main()
