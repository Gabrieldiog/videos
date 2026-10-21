# Tour realista de apartamento a partir de fotos

Pipeline 100% gratuito e open source: cada foto vira um clipe de vídeo realista
gerado por IA (**Wan 2.2**, Apache 2.0) com a câmera se movendo pelo ambiente,
e depois tudo é montado com **ffmpeg** num vídeo só.

Não precisa de GPU: a IA roda nos Spaces gratuitos do Hugging Face (ZeroGPU).

```
fotos/*.jpg ──► scripts/gerar_clipes.py ──► out/clipes/*.mp4 ──► scripts/montar_video.py ──► out/tour.mp4
               (Wan 2.2 no Hugging Face)                         (ffmpeg: 1080p, 30 fps, fades,
                                                                  nome do ambiente, música)
```

## Preparar (uma vez)

1. Crie uma conta grátis em https://huggingface.co e gere um token do tipo **Read**
   em https://huggingface.co/settings/tokens
2. Salve o token como variável de ambiente `HF_TOKEN`
   (no Claude Code na web: menu do ambiente na barra de título → Edit → variáveis de ambiente).
3. O ambiente Python se instala sozinho ao abrir a sessão (`.claude/hooks/setup.sh`).
   Manualmente: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`

## Fazer um vídeo

1. Coloque as fotos em `fotos/`
2. Edite `tour.json` — uma entrada por cena, na ordem do passeio
3. Gere os clipes: `.venv/bin/python scripts/gerar_clipes.py`
4. Monte o vídeo: `.venv/bin/python scripts/montar_video.py` (ou `--formato 9:16` para Reels)

### Campos de cada cena (`tour.json`)

| Campo          | Exemplo             | O que faz |
|----------------|---------------------|-----------|
| `foto`         | `"sala.jpg"`        | Foto em `fotos/` |
| `foto_final`   | `"cozinha.jpg"`     | *(opcional)* A IA cria a passagem realista da `foto` até esta foto — ótimo para "andar" de um cômodo ao outro |
| `ambiente`     | `"Sala de estar"`   | Nome que aparece discreto no canto |
| `movimento`    | `"avancar"`         | `avancar`, `recuar`, `pan-esquerda`, `pan-direita`, `orbita-esquerda`, `orbita-direita`, `subir`, `parado`, `caminhar` |
| `segundos`     | `3.5`               | Duração do clipe (os Spaces aceitam de 0,5 a 5 s) |
| `prompt_extra` | `"curtains move gently in the breeze"` | *(opcional)* Instrução extra em inglês para a IA |
| `seed`         | `1234`              | *(opcional)* Fixa a variação; sem ela cada geração sai diferente |

Opções gerais: `formato` (`"16:9"` ou `"9:16"`), `legendas` (true/false),
`musica` (arquivo em `musica/`, ou `null`), `volume_musica`, `transicao_segundos`.

### Dicas

- **Cota grátis**: ~5 min de GPU por dia na conta free (≈ 5–10 clipes). Clipes prontos
  ficam salvos; se a cota acabar, rode de novo no dia seguinte que continua de onde parou.
- Os Spaces geram em 832x480 a 16 fps; a montagem interpola para 30 fps e amplia para 1080p.
  Para mais nitidez, rode o Wan 2.2 em 720p no ComfyUI (ver alternativas abaixo).
- Não gostou de um clipe? `scripts/gerar_clipes.py --cena 3` gera outra variação só dele.
- A IA pode "inventar" detalhes. Para anúncio de imóvel, revise cada clipe e
  prefira movimentos curtos e lentos (`avancar`, `pan-*`), que deformam menos.
- Fotos boas = vídeo bom: horizontais, bem iluminadas, sem pessoas, tiradas da porta/canto do cômodo.
- Música livre: YouTube Audio Library ou Pixabay Music (confira a licença de cada faixa).

## Alternativas pesquisadas

| Caminho | Quando usar | Custo |
|---|---|---|
| **Wan 2.2 via HF Spaces** (este repo) | Fotos soltas, sem GPU | Grátis (cota diária) |
| **Wan 2.2 / LTX-2 / HunyuanVideo 1.5 no ComfyUI** local ou Colab/Kaggle | Mais controle e sem cota, se tiver GPU NVIDIA ≥ 12–24 GB ou usar Colab/Kaggle grátis | Grátis (hardware próprio) |
| **Gaussian Splatting** (InstantSplat, nerfstudio, Brush, apps como Scantic/SplatKing) | Passeio 3D 100% fiel ao imóvel real — mas precisa de muitas fotos/vídeo do local | Grátis, precisa de GPU ou iPhone |
| Stable Virtual Camera, GEN3C, HunyuanWorld-Voyager | Câmera 3D precisa a partir de 1 foto | Pesquisa / licença restrita, GPU grande |
