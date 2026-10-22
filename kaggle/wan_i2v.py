"""Roda NO KAGGLE (GPU grátis). Enviado por scripts/kaggle_gerar.py — não rode localmente.

Instala ComfyUI + Wan 2.2 I2V 14B (GGUF + LoRA lightx2v de 4 passos), lê jobs.json do
dataset de entrada e salva um .mp4 por cena em /kaggle/working/clipes/.
"""

import glob
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

COMFY_TAG = "v0.42.3"
GGUF_NODES_COMMIT = "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"
COMFY = Path("/tmp/ComfyUI")
MODELOS = Path("/tmp/modelos")
SAIDA = Path("/kaggle/working")
PORTA_BASE = 8188
FPS_WAN = 16

T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def sh(cmd: str) -> None:
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def achar_entrada() -> Path:
    achados = glob.glob("/kaggle/input/**/jobs.json", recursive=True)
    if not achados:
        sys.exit("jobs.json não encontrado em /kaggle/input")
    return Path(achados[0]).parent


def instalar() -> None:
    sh(f"git clone -q --depth 1 --branch {COMFY_TAG} https://github.com/comfyanonymous/ComfyUI {COMFY}")
    nodes = COMFY / "custom_nodes" / "ComfyUI-GGUF"
    sh(f"git clone -q https://github.com/city96/ComfyUI-GGUF {nodes} && git -C {nodes} checkout -q {GGUF_NODES_COMMIT}")
    # Mantém o torch do Kaggle (já compilado para a GPU da máquina).
    reqs = [l for l in (COMFY / "requirements.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#") and l.strip() not in ("torch", "torchvision", "torchaudio")]
    (COMFY / "req-kaggle.txt").write_text("\n".join(reqs + ["gguf", "imageio-ffmpeg"]))
    sh(f"{sys.executable} -m pip install -q -r {COMFY / 'req-kaggle.txt'}")


def baixar_modelos(quant: str) -> None:
    from huggingface_hub import hf_hub_download

    arquivos = [
        ("QuantStack/Wan2.2-I2V-A14B-GGUF", f"HighNoise/Wan2.2-I2V-A14B-HighNoise-{quant}.gguf", "unet"),
        ("QuantStack/Wan2.2-I2V-A14B-GGUF", f"LowNoise/Wan2.2-I2V-A14B-LowNoise-{quant}.gguf", "unet"),
        ("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "loras"),
        ("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "loras"),
        ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders"),
        ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/vae/wan_2.1_vae.safetensors", "vae"),
    ]

    def um(item):
        repo, arquivo, pasta = item
        caminho = Path(hf_hub_download(repo, arquivo, local_dir=MODELOS))
        destino = COMFY / "models" / pasta / caminho.name
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists():
            destino.symlink_to(caminho)
        return caminho.name

    log("baixando modelos (~29 GB)...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        for nome in pool.map(um, arquivos):
            log(f"  ok {nome}")


def contar_gpus() -> int:
    r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
    return max(1, sum(1 for l in r.stdout.splitlines() if l.startswith("GPU ")))


def iniciar_comfy(gpu: int, varias: bool) -> tuple[subprocess.Popen, str] | None:
    """Um ComfyUI por GPU. Com mais de uma, desliga a memória fixa para caber na RAM do Kaggle."""
    porta = PORTA_BASE + gpu
    saida_log = open(SAIDA / f"comfyui-{gpu}.log", "w")
    extras = ["--disable-pinned-memory"] if varias else []
    proc = subprocess.Popen(
        [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(porta), "--disable-auto-launch",
         "--cuda-device", str(gpu), *extras],
        cwd=COMFY, stdout=saida_log, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{porta}"
    for _ in range(300):
        try:
            urllib.request.urlopen(f"{url}/system_stats", timeout=5)
            log(f"ComfyUI no ar na GPU {gpu}")
            return proc, url
        except Exception:
            if proc.poll() is not None:
                log(f"ComfyUI da GPU {gpu} morreu ao iniciar; veja comfyui-{gpu}.log")
                return None
            time.sleep(2)
    proc.terminate()
    log(f"ComfyUI da GPU {gpu} não respondeu")
    return None


def api(url: str, caminho: str, dados: dict | None = None) -> dict:
    req = urllib.request.Request(f"{url}{caminho}")
    if dados is not None:
        req.data = json.dumps(dados).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{caminho}: {e.code} {e.read().decode()[:3000]}") from None


def preparar_foto(origem: Path, nome: str, lado_maior: int, tamanho: tuple[int, int] | None = None):
    """Recorta/redimensiona para múltiplos de 16 e coloca na pasta input do ComfyUI."""
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(origem)).convert("RGB")
    if tamanho is None:
        w, h = img.size
        if w >= h:
            tw, th = lado_maior, max(480, round(lado_maior * h / w / 16) * 16)
        else:
            tw, th = max(480, round(lado_maior * w / h / 16) * 16), lado_maior
        tamanho = (tw, th)
    img = ImageOps.fit(img, tamanho, Image.LANCZOS)
    img.save(COMFY / "input" / nome, quality=95)
    return tamanho


def grafo(job: dict, foto: str, foto_final: str | None, w: int, h: int, quadros: int, seed: int) -> dict:
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": job["_high"]}},
        "2": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": job["_low"]}},
        "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "strength_model": 1.0,
              "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0], "strength_model": 1.0,
              "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"}},
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 5.0}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": 5.0}},
        "7": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
              "type": "wan", "device": "default"}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": job["prompt"]}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": job["negativo"]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": foto}},
        "13": {"class_type": "KSamplerAdvanced", "inputs": {
            "model": ["5", 0], "add_noise": "enable", "noise_seed": seed, "steps": 4, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1],
            "latent_image": ["12", 2], "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable"}},
        "14": {"class_type": "KSamplerAdvanced", "inputs": {
            "model": ["6", 0], "add_noise": "disable", "noise_seed": seed, "steps": 4, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1],
            "latent_image": ["13", 0], "start_at_step": 2, "end_at_step": 10000, "return_with_leftover_noise": "disable"}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["10", 0]}},
        "16": {"class_type": "SaveImage", "inputs": {"images": ["15", 0], "filename_prefix": job["nome"]}},
    }
    base = {"positive": ["8", 0], "negative": ["9", 0], "vae": ["10", 0], "width": w, "height": h,
            "length": quadros, "batch_size": 1, "start_image": ["11", 0]}
    if foto_final:
        g["17"] = {"class_type": "LoadImage", "inputs": {"image": foto_final}}
        g["12"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": {**base, "end_image": ["17", 0]}}
    else:
        g["12"] = {"class_type": "WanImageToVideo", "inputs": base}
    return g


def gerar(job: dict, entrada: Path, lado_maior: int, url: str) -> dict:
    nome = job["nome"]
    w, h = preparar_foto(entrada / job["foto"], f"{nome}-a.jpg", lado_maior)
    foto_final = None
    if job.get("foto_final"):
        preparar_foto(entrada / job["foto_final"], f"{nome}-b.jpg", lado_maior, (w, h))
        foto_final = f"{nome}-b.jpg"
    quadros = max(9, min(81, round(job["segundos"] * FPS_WAN / 4) * 4 + 1))

    inicio = time.time()
    resp = api(url, "/prompt", {"prompt": grafo(job, f"{nome}-a.jpg", foto_final, w, h, quadros, job["seed"]),
                           "client_id": str(uuid.uuid4())})
    pid = resp["prompt_id"]
    while True:
        hist = api(url, f"/history/{pid}")
        if pid in hist:
            status = hist[pid].get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status.get("messages"))[:3000])
            break
        time.sleep(3)
    segundos_gpu = time.time() - inicio

    quadros_png = sorted((COMFY / "output").glob(f"{nome}_*.png"))
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    destino = SAIDA / "clipes" / f"{nome}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS_WAN),
                    "-i", str(COMFY / "output" / f"{nome}_%05d_.png"),
                    "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(destino)], check=True)
    for q in quadros_png:
        q.unlink()
    return {"nome": nome, "ok": True, "segundos_gpu": round(segundos_gpu, 1),
            "resolucao": f"{w}x{h}", "quadros": quadros, "seed": job["seed"]}


def main() -> None:
    entrada = achar_entrada()
    config = json.loads((entrada / "jobs.json").read_text())
    quant = config.get("quant", "Q4_K_M")
    lado_maior = 1280 if config.get("resolucao") == 720 else 832
    subprocess.run("nvidia-smi", shell=True)

    instalar()
    baixar_modelos(quant)
    gpus = min(int(config.get("gpus", 2)), contar_gpus(), len(config["jobs"]))
    servidores = [(g, *s) for g in range(gpus) if (s := iniciar_comfy(g, gpus > 1))]
    if not servidores:
        sys.exit("Nenhum ComfyUI subiu; veja comfyui-*.log")

    relatorio = {"quant": quant, "lado_maior": lado_maior, "gpus": len(servidores), "clipes": []}
    fila: queue.Queue = queue.Queue()
    for job in config["jobs"]:
        job["_high"] = f"Wan2.2-I2V-A14B-HighNoise-{quant}.gguf"
        job["_low"] = f"Wan2.2-I2V-A14B-LowNoise-{quant}.gguf"
        fila.put(job)
    trava = threading.Lock()

    def registrar(r: dict) -> None:
        with trava:
            relatorio["clipes"].append(r)
            (SAIDA / "relatorio.json").write_text(json.dumps(relatorio, indent=2, ensure_ascii=False))

    def trabalhador(gpu: int, proc: subprocess.Popen, url: str) -> None:
        while True:
            try:
                job = fila.get_nowait()
            except queue.Empty:
                return
            log(f"[GPU {gpu}] gerando {job['nome']} ({job['foto']}"
                f"{' -> ' + job['foto_final'] if job.get('foto_final') else ''})")
            try:
                r = gerar(job, entrada, lado_maior, url)
                r["gpu"] = gpu
                log(f"[GPU {gpu}]   ok em {r['segundos_gpu']}s ({r['resolucao']}, {r['quadros']} quadros)")
            except Exception as e:
                if proc.poll() is not None:
                    # O servidor desta GPU caiu (ex.: falta de RAM): devolve o clipe para a outra GPU.
                    log(f"[GPU {gpu}] ComfyUI caiu; devolvendo {job['nome']} para a fila")
                    fila.put(job)
                    return
                traceback.print_exc()
                r = {"nome": job["nome"], "ok": False, "erro": str(e)[:3000], "gpu": gpu}
            registrar(r)

    threads = [threading.Thread(target=trabalhador, args=s) for s in servidores]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    while not fila.empty():
        registrar({"nome": fila.get()["nome"], "ok": False, "erro": "nenhuma GPU disponível (todos os ComfyUI caíram)"})

    for _, proc, _ in servidores:
        proc.terminate()
    relatorio["segundos_total"] = round(time.time() - T0, 1)
    (SAIDA / "relatorio.json").write_text(json.dumps(relatorio, indent=2, ensure_ascii=False))
    shutil.rmtree(MODELOS, ignore_errors=True)
    log("fim")


if __name__ == "__main__":
    main()
