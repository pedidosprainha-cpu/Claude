"""Mixagem final: voz tratada (de-esser, EQ, compressão e reverb curto de sala por convolução)
+ trilha com ducking + efeitos, normalizado para -14 LUFS e muxado com o vídeo."""
import json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build"
OUT = ROOT / "output"
NOME = "video-08-buraco-negro.mp4"

GRAPH = (
    "[0:a]highpass=f=80,deesser=i=0.45:m=0.5:f=0.55,equalizer=f=220:t=q:w=1:g=-2,equalizer=f=3300:t=q:w=1.2:g=2.5,"
    "treble=g=1.5:f=9000,acompressor=threshold=-22dB:ratio=3:attack=4:release=80:makeup=5dB,"
    "aformat=sample_rates=48000:channel_layouts=stereo,asplit=4[v][vsc][vsc2][vr];"
    "[3:a]aformat=sample_rates=48000:channel_layouts=stereo[ir];"
    "[vr][ir]afir=dry=1:wet=1,volume=-19dB[vrev];"
    "[1:a]volume=-6dB[m0];"
    "[m0][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=25:release=350:makeup=1[m];"
    "[2:a]volume=-7dB,alimiter=limit=0.7:attack=2:release=60[s0];"
    "[s0][vsc2]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=250:makeup=1[s];"
    "[v][vrev][m][s]amix=inputs=4:normalize=0:duration=first[mix]"
)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main():
    inputs = ["-i", str(B / "voz.wav"), "-i", str(B / "musica.wav"), "-i", str(B / "sfx.wav"), "-i", str(B / "ir_voz.wav")]
    r = run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex",
             GRAPH + ";[mix]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[out]", "-map", "[out]", "-f", "null", "-"])
    meas = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
    ln = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
          f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}")
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", GRAPH + f";[mix]{ln},aresample=48000[out]",
         "-map", "[out]", "-c:a", "pcm_s16le", str(B / "mix.wav")])
    OUT.mkdir(exist_ok=True)
    final = OUT / NOME
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(B / "video.mp4"), "-i", str(B / "mix.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
         "-movflags", "+faststart", str(final)])
    r = run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = r.stderr[r.stderr.rfind("Summary"):]
    print(final)
    print(re.sub(r"\n\s*\n", "\n", summary))


if __name__ == "__main__":
    main()
