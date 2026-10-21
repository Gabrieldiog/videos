"""Narração grátis e offline em português com Piper TTS.

Vozes pt-BR disponíveis: faber, cadu, jeff (baixadas na primeira vez para modelos-voz/).
"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_VOZES = RAIZ / "modelos-voz"
VOZES = ("faber", "cadu", "jeff")
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR"


def modelo_voz(voz: str) -> Path:
    if voz not in VOZES:
        sys.exit(f"Voz desconhecida '{voz}'. Opções: {', '.join(VOZES)}")
    nome = f"pt_BR-{voz}-medium"
    modelo = PASTA_VOZES / f"{nome}.onnx"
    for arquivo in (modelo, PASTA_VOZES / f"{nome}.onnx.json"):
        if not arquivo.exists():
            print(f"baixando voz {voz}...", flush=True)
            PASTA_VOZES.mkdir(exist_ok=True)
            urllib.request.urlretrieve(f"{BASE_URL}/{voz}/medium/{arquivo.name}", arquivo)
    return modelo


def gerar_fala(texto: str, voz: str, destino: Path) -> None:
    piper = Path(sys.executable).parent / "piper"
    subprocess.run([str(piper), "-m", str(modelo_voz(voz)), "-f", str(destino)],
                   input=texto, text=True, check=True, capture_output=True)
