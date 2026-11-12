#!/usr/bin/env bash
# Gera o vídeo do zero: narração -> linha do tempo -> tomadas 4K e globo -> trilha/efeitos -> animação -> mixagem -> capa.
# Requisitos: python3 (edge-tts, numpy, scipy, pillow), node 18+ (npm install), ffmpeg.
# As tomadas 4K são lidas direto do servidor da NASA (só os trechos usados); o globo é gerado por src/globo.py.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
[ -f build/tts/falas.json ] && [ "${REGERAR_VOZ:-0}" != "1" ] || python3 src/tts.py
python3 src/timeline.py
[ -d build/shots/estacao ] || python3 src/shots.py
[ -f build/shots/volta/params.json ] || python3 src/globo.py
python3 src/audio.py
node src/render.js
python3 src/mix.py
node src/render.js --capa
