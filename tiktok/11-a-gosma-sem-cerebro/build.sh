#!/usr/bin/env bash
# Gera o vídeo do zero: narração -> linha do tempo -> simulações -> trilha/efeitos -> animação -> mixagem -> capa.
# Requisitos: python3 (numpy, scipy, pillow, pyshp), node 18+ (npm install), ffmpeg.
# A narração usa um ambiente Python à parte (torch CPU + chatterbox-tts + faster-whisper + praat-parselmouth);
# aponte VOZ_PY para o python desse ambiente. Sem REGERAR_VOZ=1, a narração já gravada é reaproveitada.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
if [ ! -f build/tts/falas.json ] || [ "${REGERAR_VOZ:-0}" = "1" ]; then
  "${VOZ_PY:-python3}" src/voz.py
fi
python3 src/timeline.py
[ -f build/shots/macro/meta.json ] && [ "${REGERAR_CENAS:-0}" != "1" ] || python3 src/cenas.py
python3 src/audio.py
node src/render.js
python3 src/mix.py
node src/render.js --capa
