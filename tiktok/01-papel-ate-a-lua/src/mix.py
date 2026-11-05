"""Mixagem final: voz tratada + trilha com ducking + efeitos, normalizado para -14 LUFS
(padrão de plataformas como TikTok/Reels/Shorts) e muxado com o vídeo."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
OUT = ROOT / "output"

GRAPH = (
    "[0:a]highpass=f=75,equalizer=f=200:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,"
    "acompressor=threshold=-22dB:ratio=3:attack=4:release=70:makeup=5dB,"
    "aformat=channel_layouts=stereo,asplit=2[v][vsc];"
    "[1:a]volume=-4dB[m0];"
    "[m0][vsc]sidechaincompress=threshold=0.02:ratio=7:attack=20:release=320:makeup=1[m];"
    "[2:a]volume=-7dB,alimiter=limit=0.7:attack=2:release=60[s];"
    "[v][m][s]amix=inputs=3:normalize=0:duration=first[mix]"
)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main():
    inputs = ["-i", str(B / "voz.wav"), "-i", str(B / "musica.wav"), "-i", str(B / "sfx.wav")]
    # passada 1: medir
    r = run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex",
             GRAPH + ";[mix]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[out]", "-map", "[out]", "-f", "null", "-"])
    meas = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
    ln = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
          f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}")
    # passada 2: aplicar e salvar
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", GRAPH + f";[mix]{ln},aresample=48000[out]",
         "-map", "[out]", "-c:a", "pcm_s16le", str(B / "mix.wav")])
    OUT.mkdir(exist_ok=True)
    final = OUT / "video-01-papel-ate-a-lua.mp4"
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(B / "video.mp4"), "-i", str(B / "mix.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", str(final)])
    r = run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = r.stderr[r.stderr.rfind("Summary"):]
    print(final)
    print(re.sub(r"\n\s*\n", "\n", summary))


if __name__ == "__main__":
    main()
