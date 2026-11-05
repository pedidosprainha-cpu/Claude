"""Mixagem final em duas versões, normalizadas para -14 LUFS e muxadas com o vídeo:

  output/video-05-a-musica-que-tiraram-do-ar.mp4            voz + trilha original + efeitos
  output/video-05-a-musica-que-tiraram-do-ar-SEM-TRILHA.mp4  voz + efeitos (para usar a música original
                                                             de 1992 pela biblioteca de sons do TikTok)
"""
import json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
OUT = ROOT / "output"
NOME = "video-05-a-musica-que-tiraram-do-ar"


def graph(music_db):
    m = f"[1:a]volume={music_db}dB[m0];[m0][vsc]sidechaincompress=threshold=0.02:ratio=7:attack=20:release=320:makeup=1[m];" if music_db is not None else "[1:a]anullsink;"
    mix = "[v][m][s]amix=inputs=3:normalize=0:duration=first[mix]" if music_db is not None else "[vsc]anullsink;[v][s]amix=inputs=2:normalize=0:duration=first[mix]"
    return ("[0:a]highpass=f=75,equalizer=f=200:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,"
            "acompressor=threshold=-22dB:ratio=3:attack=4:release=70:makeup=5dB,"
            "aformat=channel_layouts=stereo,asplit=2[v][vsc];" + m +
            "[2:a]volume=-7dB,alimiter=limit=0.7:attack=2:release=60[s];" + mix)


GRAPH = graph(-9)  # usado pelas análises de equilíbrio


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def make(music_db, final):
    inputs = ["-i", str(B / "voz.wav"), "-i", str(B / "musica.wav"), "-i", str(B / "sfx.wav")]
    g = graph(music_db)
    r = run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", g + ";[mix]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[out]", "-map", "[out]", "-f", "null", "-"])
    meas = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
    ln = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
          f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}")
    wav = B / (final.stem + ".wav")
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", g + f";[mix]{ln},aresample=48000[out]", "-map", "[out]", "-c:a", "pcm_s16le", str(wav)])
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(B / "video.mp4"), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(final)])
    r = run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"])
    s = r.stderr[r.stderr.rfind("Summary"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1); pk = re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1)
    print(f"{final.name}: {i} LUFS, pico {pk} dBFS")


def main():
    OUT.mkdir(exist_ok=True)
    make(-9, OUT / f"{NOME}.mp4")
    make(None, OUT / f"{NOME}-SEM-TRILHA.mp4")


if __name__ == "__main__":
    main()
