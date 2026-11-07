#!/usr/bin/env bash
# Baixa as simulações 360° da NASA (SVS 14576, domínio público) usadas nas tomadas. ~1,6 GB.
# Destino: ./footage (ou a pasta em $FOOTAGE). São só vídeos, sem a trilha comercial dos "explainers".
set -euo pipefail
cd "$(dirname "$0")/.."
D="${FOOTAGE:-footage}"; mkdir -p "$D"
B=https://svs.gsfc.nasa.gov/vis/a010000/a014500/a014576
for f in 14576_BH_Plunge_Rectilinear_8192x4096_60.mp4 14576_BH_FlyBy_Rectilinear_8192x4096_60.mp4; do
  [ -s "$D/$f" ] || curl -L --retry 3 -o "$D/$f" "$B/$f"
done
