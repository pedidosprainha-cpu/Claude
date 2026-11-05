#!/usr/bin/env bash
# Gera o vídeo do zero: acervo -> narração -> linha do tempo -> trilha/efeitos -> animação -> mixagem (2 versões) -> capa.
# Requisitos: python3 (edge-tts, numpy, scipy), node 18+ (npm install), ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
python3 src/baixar_acervo.py                       # fotos e vídeo de arquivo (Wikimedia Commons, licenças livres)
mkdir -p build/confisco && rm -f build/confisco/*.jpg
# trecho do vídeo de TV de 1990 (EBC): 9 s a partir de 0:12, em 30 fps
ffmpeg -v error -y -ss 12 -t 9 -i assets/confisco_1990.webm -vf "fps=30,scale=1000:750:flags=lanczos" -q:v 3 build/confisco/%04d.jpg
[ -f build/tts/falas.json ] && [ "${REGERAR_VOZ:-0}" != "1" ] || python3 src/tts.py
python3 src/timeline.py
python3 src/audio.py
node src/render.js
python3 src/mix.py
node src/render.js --capa
