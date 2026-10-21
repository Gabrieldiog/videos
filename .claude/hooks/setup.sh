#!/bin/bash
# Prepara o ambiente Python do pipeline de vídeo (idempotente).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
command -v ffmpeg >/dev/null || echo "Aviso: ffmpeg não encontrado (necessário para montar o vídeo)." >&2
