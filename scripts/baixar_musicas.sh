#!/bin/bash
# Baixa piano calmo em domínio público (CC0) para musica/.
# Fonte: Musopen — "The Complete Works of Frédéric Chopin", liberado em CC0 1.0
# https://archive.org/details/musopen-chopin-complete-works-flac
# CC0 = uso comercial livre, sem pagar e sem precisar dar crédito.
set -euo pipefail
cd "$(dirname "$0")/../musica"

BASE="https://archive.org/download/musopen-chopin-complete-works-flac"
baixar() {
  local destino="$1" origem="$2"
  if [ ! -s "$destino" ]; then
    echo "baixando $destino..."
    curl -sSfL -o "$destino" "$BASE/$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$origem")"
  fi
}

baixar chopin-noturno-op9-n2.mp3 "Nocturne in E flat major, Op. 9 no. 2.mp3"
baixar chopin-berceuse-op57.mp3 "Berceuse in D-flat major, Op. 57 .mp3"
baixar chopin-noturno-op27-n2.mp3 "Nocturne in D flat major, Op. 27 no. 2.mp3"
ls -la *.mp3
