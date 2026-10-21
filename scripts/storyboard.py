#!/usr/bin/env python3
"""Folha de aprovação: 3 quadros (início, meio, fim) de cada clipe numa imagem só.

Serve para conferir se a IA deformou paredes/móveis antes de montar o vídeo,
e para mandar ao cliente escolher as cenas.

Uso:
    python scripts/storyboard.py              # out/storyboard.jpg
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar_clipes import RAIZ, caminho_clipe, carregar_config  # noqa: E402
from montar_video import fonte_padrao, sondar  # noqa: E402

LARGURA_QUADRO = 480


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tour.json")
    parser.add_argument("--saida", default=str(RAIZ / "out" / "storyboard.jpg"))
    args = parser.parse_args()

    config = carregar_config(RAIZ / args.config)
    fonte = fonte_padrao()
    linhas = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, cena in enumerate(config["cenas"], start=1):
            clipe = caminho_clipe(RAIZ / "out" / "clipes", i, cena)
            if not clipe.exists():
                print(f"[{i}] {cena['ambiente']}: clipe ainda não gerado, pulando")
                continue
            duracao, _ = sondar(clipe)
            quadros = []
            for j, t in enumerate((0.05, duracao / 2, max(duracao - 0.1, 0))):
                q = tmp / f"{i:02d}-{j}.png"
                subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(clipe),
                                "-frames:v", "1", "-vf", f"scale={LARGURA_QUADRO}:-2", str(q)], check=True)
                quadros.append(q)
            rotulo = tmp / f"{i:02d}.txt"
            rotulo.write_text(f"{i}. {cena['ambiente']}  ({clipe.name})", encoding="utf-8")
            linha = tmp / f"linha-{i:02d}.png"
            entradas = sum((["-i", str(q)] for q in quadros), [])
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *entradas, "-filter_complex",
                            f"[0][1][2]hstack=3,pad=iw+20:ih+70:10:60:color=white,"
                            f"drawtext=fontfile='{fonte}':textfile='{rotulo}':fontsize=28:x=12:y=18:fontcolor=black",
                            str(linha)], check=True)
            linhas.append(linha)
        if not linhas:
            sys.exit("Nenhum clipe gerado ainda.")
        entradas = sum((["-i", str(l)] for l in linhas), [])
        filtro = f"{''.join(f'[{k}]' for k in range(len(linhas)))}vstack={len(linhas)}" if len(linhas) > 1 else "null"
        Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro,
                        "-q:v", "3", args.saida], check=True)
    print(f"Storyboard: {args.saida}")


if __name__ == "__main__":
    main()
