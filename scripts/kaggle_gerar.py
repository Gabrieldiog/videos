#!/usr/bin/env python3
"""Gera os clipes do tour.json na GPU grátis do Kaggle (Wan 2.2 14B, 4 passos).

1. Sobe as fotos + roteiro como dataset privado no Kaggle
2. Roda kaggle/wan_i2v.py num notebook privado com GPU T4
3. Espera terminar e baixa os clipes para out/clipes/ (mesmos nomes que montar_video.py usa)

Precisa da variável KAGGLE_API_TOKEN (Kaggle → Settings → API Tokens).
A conta precisa estar com o celular verificado para liberar GPU.

Uso:
    python scripts/kaggle_gerar.py                 # gera o que falta
    python scripts/kaggle_gerar.py --cena 2        # refaz a cena 2 com outra seed
    python scripts/kaggle_gerar.py --resolucao 720 # mais nítido, mais lento
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar_clipes import NEGATIVO, RAIZ, caminho_clipe, carregar_config, montar_prompt  # noqa: E402

KAGGLE = str(Path(sys.executable).parent / "kaggle")
DATASET_SLUG = "tour-entrada"
KERNEL_SLUG = "tour-wan22"


def kaggle(*args: str, check: bool = True) -> str:
    r = subprocess.run([KAGGLE, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"kaggle {' '.join(args)} falhou:\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def usuario() -> str:
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api.get_config_value("username")


def subir_dataset(user: str, jobs: dict, fotos: set[str]) -> None:
    ident = f"{user}/{DATASET_SLUG}"
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        for foto in fotos:
            shutil.copy(RAIZ / "fotos" / foto, pasta / foto)
        (pasta / "jobs.json").write_text(json.dumps(jobs, indent=2, ensure_ascii=False))
        (pasta / "dataset-metadata.json").write_text(json.dumps(
            {"title": DATASET_SLUG, "id": ident, "licenses": [{"name": "CC0-1.0"}]}))
        existe = "ready" in kaggle("datasets", "status", ident, check=False).lower()
        if existe:
            kaggle("datasets", "version", "-p", str(pasta), "-m", time.strftime("%Y-%m-%d %H:%M"), "-q")
        else:
            kaggle("datasets", "create", "-p", str(pasta), "-q")
    print("dataset enviado; aguardando o Kaggle processar...", flush=True)
    for _ in range(60):
        if "ready" in kaggle("datasets", "status", ident, check=False).lower():
            return
        time.sleep(10)
    sys.exit("o dataset não ficou pronto a tempo")


def rodar_kernel(user: str) -> str:
    ident = f"{user}/{KERNEL_SLUG}"
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        shutil.copy(RAIZ / "kaggle" / "wan_i2v.py", pasta / "wan_i2v.py")
        (pasta / "kernel-metadata.json").write_text(json.dumps({
            "id": ident, "title": KERNEL_SLUG, "code_file": "wan_i2v.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
            "dataset_sources": [f"{user}/{DATASET_SLUG}"],
        }))
        print(kaggle("kernels", "push", "-p", str(pasta)).strip())
    inicio = time.time()
    while True:
        time.sleep(60)
        status = kaggle("kernels", "status", ident, check=False)
        minutos = (time.time() - inicio) / 60
        print(f"  {minutos:5.1f} min  {status.strip().splitlines()[-1]}", flush=True)
        baixo = status.lower()
        if "complete" in baixo or "error" in baixo or "cancel" in baixo:
            return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tour.json")
    parser.add_argument("--cena", type=int, action="append", help="número da cena (1, 2, ...) para refazer")
    parser.add_argument("--resolucao", type=int, choices=[480, 720], default=480)
    parser.add_argument("--quant", default="Q4_K_M", help="Q4_K_M (padrão), Q5_K_M ou Q6_K")
    args = parser.parse_args()

    config = carregar_config(RAIZ / args.config)
    pasta_clipes = RAIZ / "out" / "clipes"
    jobs, fotos = [], set()
    for i, cena in enumerate(config["cenas"], start=1):
        destino = caminho_clipe(pasta_clipes, i, cena)
        if args.cena and i not in args.cena:
            continue
        if destino.exists() and not args.cena:
            print(f"[{i}] {cena['ambiente']}: já existe")
            continue
        for chave in ("foto", "foto_final"):
            if cena.get(chave):
                if not (RAIZ / "fotos" / cena[chave]).exists():
                    sys.exit(f"Foto não encontrada: fotos/{cena[chave]}")
                fotos.add(cena[chave])
        jobs.append({
            "nome": destino.stem, "foto": cena["foto"], "foto_final": cena.get("foto_final"),
            "prompt": montar_prompt(cena), "negativo": NEGATIVO,
            "segundos": float(cena.get("segundos", 3.5)),
            "seed": int(cena["seed"]) if "seed" in cena and not args.cena else random.randint(1, 2**31 - 1),
        })
    if not jobs:
        print("Nada para gerar. Rode: python scripts/montar_video.py")
        return

    user = usuario()
    print(f"conta Kaggle: {user} — {len(jobs)} clipe(s) para gerar")
    subir_dataset(user, {"quant": args.quant, "resolucao": args.resolucao, "jobs": jobs}, fotos)
    status = rodar_kernel(user)

    with tempfile.TemporaryDirectory() as tmp:
        kaggle("kernels", "output", f"{user}/{KERNEL_SLUG}", "-p", tmp, "-o", check=False)
        saida = Path(tmp)
        for log in ("relatorio.json", "comfyui.log", f"{KERNEL_SLUG}.log"):
            if (saida / log).exists():
                (RAIZ / "out" / "kaggle").mkdir(parents=True, exist_ok=True)
                shutil.copy(saida / log, RAIZ / "out" / "kaggle" / log)
        pasta_clipes.mkdir(parents=True, exist_ok=True)
        for clipe in (saida / "clipes").glob("*.mp4") if (saida / "clipes").exists() else []:
            shutil.copy(clipe, pasta_clipes / clipe.name)
            print(f"  baixado out/clipes/{clipe.name}")

    relatorio = RAIZ / "out" / "kaggle" / "relatorio.json"
    if relatorio.exists():
        dados = json.loads(relatorio.read_text())
        for c in dados["clipes"]:
            print(f"  {c['nome']}: " + (f"ok, {c['segundos_gpu']}s de GPU, {c['resolucao']}" if c["ok"] else f"ERRO {c['erro'][:300]}"))
        if "segundos_total" in dados:
            print(f"tempo total da sessão: {dados['segundos_total'] / 60:.1f} min")
    if "complete" not in status.lower():
        sys.exit(f"O notebook terminou com problema:\n{status}\nLogs em out/kaggle/")
    print("\nPronto. Confira os clipes e rode: python scripts/montar_video.py")


if __name__ == "__main__":
    main()
