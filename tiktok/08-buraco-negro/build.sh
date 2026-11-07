#!/usr/bin/env bash
# Gera o vídeo do zero: narração -> linha do tempo -> tomadas 8K -> trilha/efeitos -> animação -> mixagem -> capa.
# Requisitos: python3 (edge-tts, numpy, scipy, pillow), node 18+ (npm install), ffmpeg com v360.
# Antes, rode src/baixar.sh (simulações da NASA, ~1,6 GB) ou aponte $FOOTAGE para a pasta delas.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
[ -f build/tts/falas.json ] && [ "${REGERAR_VOZ:-0}" != "1" ] || python3 src/tts.py
python3 src/timeline.py
[ -d build/shots/escape ] || python3 src/shots.py
python3 src/audio.py
node src/render.js
python3 src/mix.py
node src/render.js --capa
