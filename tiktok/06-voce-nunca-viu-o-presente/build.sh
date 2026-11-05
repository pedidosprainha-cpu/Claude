#!/usr/bin/env bash
# Gera o vídeo do zero: narração -> linha do tempo -> trilha/efeitos -> animação -> mixagem -> capa.
# As imagens (NASA/ESA/ESO) já estão em assets/ com os créditos em assets/CREDITOS.md.
# Requisitos: python3 (edge-tts, numpy, scipy), node 18+ (npm install), ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
[ -f build/tts/falas.json ] && [ "${REGERAR_VOZ:-0}" != "1" ] || python3 src/tts.py
python3 src/timeline.py
python3 src/audio.py
node src/render.js
python3 src/mix.py
node src/render.js --capa
