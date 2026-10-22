#!/usr/bin/env python3
"""Prepara os clipes de IA para um projeto HyperFrames (motion/<tour>/assets/clips/NN.mp4).

- Interpola para 30 fps (ou 60 fps nas cenas que vão tocar em câmera lenta, --lento)
- Ajusta para 1080x1920 (vertical); fontes largas ganham uma panorâmica lenta em vez de corte no centro
- Keyframe a cada segundo, como o HyperFrames pede para buscar quadros sem travar

Sem o clipe ainda (Kaggle gerando), --provisorio cria um substituto a partir da foto,
só para montar e revisar o motion; depois é só rodar de novo.

Uso:
    python scripts/preparar_motion.py --config tours/casa-praia.json --destino motion/casa-praia/assets/clips --lento 8
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar_clipes import RAIZ, caminho_clipe, carregar_config  # noqa: E402
from montar_video import sondar  # noqa: E402

W, H = 1080, 1920


def largura_na_altura(clipe: Path) -> int:
    saida = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(clipe)], capture_output=True, text=True, check=True).stdout
    w, h = (int(x) for x in saida.strip().split(","))
    return round(w * H / h)


def provisorio(foto: Path, segundos: float, destino: Path) -> None:
    quadros = round(segundos * 16)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-i", str(foto),
                    "-vf", f"scale=-2:832,zoompan=z='1+0.0015*on':d=1:s=hd480:fps=16,scale=-2:832,setsar=1",
                    "-frames:v", str(quadros), "-r", "16", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(destino)],
                   check=True)


def preparar(origem: Path, destino: Path, fps: int) -> None:
    duracao, fps_origem = sondar(origem)
    largura = largura_na_altura(origem)
    if largura > W * 1.4:
        # Fonte larga (ex.: piscina quase quadrada): panorâmica da direita para a esquerda.
        x = f"(iw-ow)*(0.62-0.24*t/{duracao:.3f})"
    else:
        x = "(iw-ow)/2"
    interp = f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" if fps_origem < fps - 1 else f"fps={fps}"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(origem), "-an",
                    "-vf", f"{interp},scale=-2:{H}:flags=lanczos,crop={W}:{H}:{x}:0,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-g", str(fps),
                    "-movflags", "+faststart", str(destino)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--destino", required=True)
    parser.add_argument("--lento", type=int, action="append", default=[], help="cena tocada a 0,5x (gera em 60 fps)")
    parser.add_argument("--provisorio", action="store_true", help="usa a foto quando o clipe ainda não existe")
    args = parser.parse_args()

    config = carregar_config(RAIZ / args.config)
    destino = RAIZ / args.destino
    destino.mkdir(parents=True, exist_ok=True)
    if config.get("musica"):
        # A trilha do tour vai junto, como assets/audio/piano.mp3 do projeto HyperFrames.
        audio = destino.parent / "audio"
        audio.mkdir(exist_ok=True)
        shutil.copy(RAIZ / "musica" / config["musica"], audio / "piano.mp3")
    for i, cena in enumerate(config["cenas"], start=1):
        clipe = caminho_clipe(RAIZ / "out" / "clipes", i, cena)
        saida = destino / f"{i:02d}.mp4"
        fps = 60 if i in args.lento else 30
        if clipe.exists():
            print(f"[{i}] {cena['ambiente']}: {clipe.name} -> {saida.name} ({fps} fps)", flush=True)
            preparar(clipe, saida, fps)
        elif args.provisorio:
            print(f"[{i}] {cena['ambiente']}: PROVISÓRIO a partir de {cena['foto']}", flush=True)
            with tempfile.TemporaryDirectory() as tmp:
                falso = Path(tmp) / "falso.mp4"
                provisorio(RAIZ / "fotos" / cena["foto"], float(cena.get("segundos", 4)) + 0.06, falso)
                preparar(falso, saida, fps)
        else:
            sys.exit(f"Falta o clipe da cena {i} ({clipe.name}); use --provisorio ou gere no Kaggle.")


if __name__ == "__main__":
    main()
