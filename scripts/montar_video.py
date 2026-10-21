#!/usr/bin/env python3
"""Junta os clipes de out/clipes/ no vídeo final, com ffmpeg.

- Ajusta tudo para 1920x1080 (16:9) ou 1080x1920 (9:16, com fundo desfocado)
- Suaviza para 30 fps (os modelos de IA geram ~16 fps)
- Transição em fade entre os ambientes
- Nome do ambiente discreto no canto (desligue com "legendas": false)
- Narração opcional por cena ("narracao" no tour.json), voz offline Piper
- Música opcional (arquivo em musica/), que abaixa sozinha durante a narração

Uso:
    python scripts/montar_video.py
    python scripts/montar_video.py --formato 9:16
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar_clipes import RAIZ, caminho_clipe, carregar_config  # noqa: E402
from narracao import gerar_fala  # noqa: E402

FPS = 30
TAMANHOS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}


def rodar(cmd: list[str]) -> None:
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        sys.exit(f"ffmpeg falhou:\n{' '.join(cmd)}\n\n{resultado.stderr[-3000:]}")


def sondar(arquivo: Path) -> tuple[float, float]:
    """Retorna (duração em segundos, fps) do vídeo."""
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate:format=duration", "-of", "json", str(arquivo)],
        capture_output=True, text=True, check=True,
    ).stdout
    dados = json.loads(saida)
    num, den = dados["streams"][0]["r_frame_rate"].split("/")
    return float(dados["format"]["duration"]), float(num) / float(den)


def sondar_audio(arquivo: Path) -> float:
    saida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
                           capture_output=True, text=True, check=True).stdout
    return float(saida)


def fonte_padrao() -> str:
    for nome in ("Inter:style=SemiBold", "DejaVu Sans:style=Bold"):
        caminho = subprocess.run(["fc-match", "-f", "%{file}", nome], capture_output=True, text=True).stdout
        if caminho:
            return caminho
    return ""


def filtro_cena(largura: int, altura: int, fps_origem: float, duracao: float,
                texto: Path | None, fonte: str) -> str:
    partes = []
    # Interpola quadros ainda na resolução original (bem mais rápido que em 1080p).
    if fps_origem < FPS - 1:
        partes.append(f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    else:
        partes.append(f"fps={FPS}")

    if largura > altura:
        partes.append(f"scale={largura}:{altura}:force_original_aspect_ratio=increase:flags=lanczos,crop={largura}:{altura}")
        grafo = ",".join(partes)
    else:
        # Vertical: foto inteira no centro, com a mesma foto desfocada preenchendo o fundo.
        base = ",".join(partes)
        grafo = (
            f"{base},split[a][b];"
            f"[a]scale={largura}:{altura}:force_original_aspect_ratio=increase,crop={largura}:{altura},boxblur=40:2[fundo];"
            f"[b]scale={largura}:-2:flags=lanczos[frente];"
            f"[fundo][frente]overlay=(W-w)/2:(H-h)/2"
        )

    if texto is not None:
        d = duracao
        alpha = f"if(lt(t,0.4),0,if(lt(t,1),(t-0.4)/0.6,if(lt(t,{d - 0.8:.2f}),1,if(lt(t,{d - 0.3:.2f}),({d - 0.3:.2f}-t)/0.5,0))))"
        y = "h*0.86" if largura > altura else "h*0.80"
        grafo += (
            f",drawtext=fontfile='{fonte}':textfile='{texto}':fontcolor=white:fontsize=h*{0.05 if largura > altura else 0.034}"
            f":x=w*0.05:y={y}:shadowcolor=black@0.55:shadowx=2:shadowy=2:alpha='{alpha}'"
        )
    return grafo + ",format=yuv420p"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tour.json")
    parser.add_argument("--formato", choices=TAMANHOS, help="sobrescreve o formato do tour.json")
    parser.add_argument("--saida", help="arquivo de saída (padrão: out/tour.mp4 ou out/tour-vertical.mp4)")
    args = parser.parse_args()

    config = carregar_config(RAIZ / args.config)
    formato = args.formato or config.get("formato", "16:9")
    largura, altura = TAMANHOS[formato]
    transicao = float(config.get("transicao_segundos", 0.6))
    pasta_clipes = RAIZ / "out" / "clipes"
    saida = Path(args.saida) if args.saida else RAIZ / "out" / ("tour.mp4" if formato == "16:9" else "tour-vertical.mp4")

    clipes = [caminho_clipe(pasta_clipes, i, c) for i, c in enumerate(config["cenas"], start=1)]
    faltando = [f"  cena {i}: {c['ambiente']}" for i, (c, p) in enumerate(zip(config["cenas"], clipes), 1) if not p.exists()]
    if faltando:
        sys.exit("Faltam clipes (rode scripts/gerar_clipes.py):\n" + "\n".join(faltando))

    fonte = fonte_padrao()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        normalizados, duracoes = [], []
        for i, (cena, clipe) in enumerate(zip(config["cenas"], clipes), start=1):
            duracao, fps_origem = sondar(clipe)
            texto = None
            if config.get("legendas", True) and cena.get("ambiente") and fonte:
                texto = tmp / f"{i:02d}.txt"
                texto.write_text(cena["ambiente"], encoding="utf-8")
            destino = tmp / f"{i:02d}.mp4"
            print(f"[{i}] ajustando {clipe.name} ({duracao:.1f}s, {fps_origem:.0f} fps)...", flush=True)
            rodar(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clipe), "-an",
                   "-filter_complex", filtro_cena(largura, altura, fps_origem, duracao, texto, fonte),
                   "-c:v", "libx264", "-preset", "medium", "-crf", "16", str(destino)])
            normalizados.append(destino)
            duracoes.append(sondar(destino)[0])

        entradas: list[str] = []
        for arquivo in normalizados:
            entradas += ["-i", str(arquivo)]

        cadeia, ultimo, acumulado = [], "0:v", duracoes[0]
        inicios = [0.0]
        for k in range(1, len(normalizados)):
            offset = acumulado - transicao
            rotulo = f"v{k}"
            cadeia.append(f"[{ultimo}][{k}:v]xfade=transition=fade:duration={transicao}:offset={offset:.3f}[{rotulo}]")
            ultimo, acumulado = rotulo, offset + duracoes[k]
            inicios.append(offset)
        total = acumulado

        cmd = ["ffmpeg", "-y", "-loglevel", "error", *entradas]
        proxima_entrada = len(normalizados)

        # Narração: uma fala por cena, começando logo depois da transição.
        falas = []
        voz = config.get("voz", "faber")
        for i, cena in enumerate(config["cenas"]):
            if not cena.get("narracao"):
                continue
            wav = tmp / f"fala-{i + 1:02d}.wav"
            print(f"[{i + 1}] narrando com a voz {voz}...", flush=True)
            gerar_fala(cena["narracao"], voz, wav)
            inicio = inicios[i] + (transicao if i else 0.3)
            fim_cena = inicios[i + 1] if i + 1 < len(inicios) else total
            sobra = fim_cena - inicio - sondar_audio(wav)
            if sobra < 0:
                print(f"    aviso: a fala da cena {i + 1} passa {-sobra:.1f}s do fim da cena; "
                      f"encurte o texto ou aumente 'segundos'", flush=True)
            cmd += ["-i", str(wav)]
            falas.append((proxima_entrada, inicio))
            proxima_entrada += 1

        trilhas = []
        if falas:
            for n, (entrada, inicio) in enumerate(falas):
                ms = int(inicio * 1000)
                cadeia.append(f"[{entrada}:a]aresample=48000,adelay={ms}|{ms}[f{n}]")
            juntas = "".join(f"[f{n}]" for n in range(len(falas)))
            cadeia.append(f"{juntas}amix=inputs={len(falas)}:normalize=0,"
                          f"volume={float(config.get('volume_narracao', 1.0))},apad[narr]")

        if config.get("musica"):
            musica = RAIZ / "musica" / config["musica"]
            if not musica.exists():
                sys.exit(f"Música não encontrada: {musica}")
            cmd += ["-stream_loop", "-1", "-i", str(musica)]
            volume = float(config.get("volume_musica", 0.5))
            cadeia.append(
                f"[{proxima_entrada}:a]aresample=48000,atrim=0:{total:.3f},volume={volume},"
                f"afade=t=in:d=1,afade=t=out:st={max(total - 2, 0):.3f}:d=2[mus]"
            )
            if falas:
                # Abaixa a música automaticamente enquanto a narração fala.
                cadeia.append("[narr]asplit[narr1][narr2]")
                cadeia.append("[mus][narr1]sidechaincompress=threshold=0.03:ratio=6:attack=50:release=600[musd]")
                trilhas = ["[musd]", "[narr2]"]
            else:
                trilhas = ["[mus]"]
        elif falas:
            trilhas = ["[narr]"]

        mapa_audio: list[str] = []
        if trilhas:
            if len(trilhas) > 1:
                cadeia.append(f"{''.join(trilhas)}amix=inputs={len(trilhas)}:normalize=0:duration=first,alimiter=limit=0.8:level=false[a]")
            else:
                cadeia.append(f"{trilhas[0]}alimiter=limit=0.8:level=false[a]")
            mapa_audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]

        mapa_video = ["-map", f"[{ultimo}]"] if len(normalizados) > 1 else ["-map", "0:v"]
        if cadeia:
            cmd += ["-filter_complex", ";".join(cadeia)]
        saida.parent.mkdir(parents=True, exist_ok=True)
        cmd += [*mapa_video, *mapa_audio, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", f"{total:.3f}", str(saida)]
        print("juntando...", flush=True)
        rodar(cmd)

    print(f"\nVídeo pronto: {saida.relative_to(RAIZ) if saida.is_relative_to(RAIZ) else saida} ({total:.1f}s)")


if __name__ == "__main__":
    main()
