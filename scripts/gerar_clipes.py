#!/usr/bin/env python3
"""Gera um clipe realista (IA, Wan 2.2) para cada cena do tour.json.

Usa Spaces gratuitos do Hugging Face (ZeroGPU), então não precisa de GPU local.
Precisa da variável de ambiente HF_TOKEN (token gratuito, permissão "read").

A cota gratuita é curta (alguns minutos de GPU por dia). Por isso cada clipe
gerado fica salvo em out/clipes/ e não é refeito: se a cota acabar no meio,
é só rodar de novo no dia seguinte que ele continua de onde parou.

Uso:
    python scripts/gerar_clipes.py                # gera o que falta
    python scripts/gerar_clipes.py --cena 2       # refaz só a cena 2 (nova variação)
    python scripts/gerar_clipes.py --config outro.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Space para foto -> vídeo e Space para foto inicial + foto final -> vídeo.
# Podem ser trocados no tour.json ("space_i2v" / "space_flf") se algum sair do ar.
SPACE_I2V = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
SPACE_FLF = "multimodalart/wan-2-2-first-last-frame"

MOVIMENTOS = {
    "avancar": "the camera slowly dollies forward into the room",
    "recuar": "the camera slowly pulls back, revealing more of the room",
    "pan-esquerda": "the camera slowly pans to the left",
    "pan-direita": "the camera slowly pans to the right",
    "orbita-esquerda": "the camera slowly arcs to the left around the room",
    "orbita-direita": "the camera slowly arcs to the right around the room",
    "subir": "the camera slowly cranes up",
    "parado": "static locked-off camera, only subtle natural light movement",
    "caminhar": "first-person walkthrough, the camera smoothly walks from the first view to the next room",
}

PROMPT_BASE = (
    "Real estate video tour of an apartment interior, {movimento}. "
    "Smooth steady gimbal shot at constant slow speed. "
    "Walls, windows, floor and furniture stay exactly the same and keep their shape. "
    "No people. Photorealistic, natural daylight, sharp details."
)

NEGATIVO = (
    "people, person, hands, morphing, warping walls, melting, distorted furniture, "
    "objects appearing or disappearing, text, watermark, logo, fast motion, shaky camera, "
    "cartoon, painting, blurry, low quality, overexposed, static frame"
)


def carregar_config(caminho: Path) -> dict:
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def montar_prompt(cena: dict) -> str:
    movimento = cena.get("movimento", "avancar")
    if movimento not in MOVIMENTOS:
        opcoes = ", ".join(MOVIMENTOS)
        sys.exit(f"Movimento desconhecido '{movimento}'. Opções: {opcoes}")
    prompt = PROMPT_BASE.format(movimento=MOVIMENTOS[movimento])
    if cena.get("prompt_extra"):
        prompt += " " + cena["prompt_extra"]
    return prompt


def chave_cena(cena: dict) -> str:
    """Identifica a cena pelos parâmetros que mudam o resultado."""
    relevante = {k: cena.get(k) for k in ("foto", "foto_final", "movimento", "segundos", "prompt_extra", "seed")}
    return hashlib.sha1(json.dumps(relevante, sort_keys=True).encode()).hexdigest()[:8]


def caminho_clipe(pasta: Path, indice: int, cena: dict) -> Path:
    return pasta / f"{indice:02d}-{chave_cena(cena)}.mp4"


def gerar(cena: dict, config: dict, token: str, destino: Path) -> int:
    from gradio_client import Client, handle_file

    foto = RAIZ / "fotos" / cena["foto"]
    if not foto.exists():
        sys.exit(f"Foto não encontrada: {foto}")

    comum = dict(
        prompt=montar_prompt(cena),
        negative_prompt=NEGATIVO,
        duration_seconds=float(cena.get("segundos", 3.5)),
        seed=int(cena.get("seed", 42)),
        randomize_seed="seed" not in cena,
        api_name="/generate_video",
    )

    if cena.get("foto_final"):
        foto_final = RAIZ / "fotos" / cena["foto_final"]
        if not foto_final.exists():
            sys.exit(f"Foto não encontrada: {foto_final}")
        cliente = Client(config.get("space_flf", SPACE_FLF), token=token, verbose=False)
        video, seed = cliente.predict(
            start_image_pil=handle_file(str(foto)),
            end_image_pil=handle_file(str(foto_final)),
            steps=8,
            **comum,
        )
    else:
        cliente = Client(config.get("space_i2v", SPACE_I2V), token=token, verbose=False)
        video, seed = cliente.predict(input_image=handle_file(str(foto)), steps=6, **comum)

    arquivo = video["video"] if isinstance(video, dict) else video
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(arquivo, destino)
    return int(seed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tour.json")
    parser.add_argument("--cena", type=int, action="append", help="número da cena (1, 2, ...) para refazer")
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit(
            "Falta a variável HF_TOKEN.\n"
            "Crie um token grátis (tipo 'read') em https://huggingface.co/settings/tokens\n"
            "e adicione como variável de ambiente HF_TOKEN nas configurações do ambiente."
        )

    config = carregar_config(RAIZ / args.config)
    pasta = RAIZ / "out" / "clipes"
    registro_path = pasta / "seeds.json"
    registro = json.loads(registro_path.read_text()) if registro_path.exists() else {}

    for i, cena in enumerate(config["cenas"], start=1):
        destino = caminho_clipe(pasta, i, cena)
        refazer = args.cena and i in args.cena
        if destino.exists() and not refazer:
            print(f"[{i}] {cena['ambiente']}: já existe ({destino.name})")
            continue
        if args.cena and not refazer:
            continue

        tipo = "foto inicial -> foto final" if cena.get("foto_final") else "foto -> vídeo"
        print(f"[{i}] {cena['ambiente']}: gerando ({tipo}, {cena.get('movimento', 'avancar')})...", flush=True)
        try:
            seed = gerar(cena, config, token, destino)
        except Exception as erro:  # o gradio_client só expõe a mensagem do Space
            texto = str(erro)
            if "quota" in texto.lower() or "limit" in texto.lower():
                print(
                    f"\nCota gratuita do Hugging Face acabou por hoje:\n  {texto}\n"
                    "Os clipes já gerados estão salvos em out/clipes/. Rode de novo depois que a cota renovar.",
                    file=sys.stderr,
                )
                sys.exit(2)
            raise
        registro[destino.name] = seed
        registro_path.write_text(json.dumps(registro, indent=2))
        print(f"    ok -> out/clipes/{destino.name} (seed {seed})")

    print("\nPronto. Agora rode: python scripts/montar_video.py")


if __name__ == "__main__":
    main()
