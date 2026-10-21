# Projeto: tour realista de apartamento a partir de fotos

O usuário quer vídeos **realistas** (câmera se movendo pelo imóvel). A filmagem vem sempre dos clipes de IA;
motion graphics só como **camada por cima** (textos, nota, avaliações, chamada final), feita com **HyperFrames**
(skills em `.claude/skills/hyperframes*`, CLI `npx hyperframes@0.8.185`, projetos em `motion/<tour>/`). Não use Remotion.

- `scripts/gerar_clipes.py` — chama Wan 2.2 em Spaces do Hugging Face (ZeroGPU) via `gradio_client`.
  Precisa de `HF_TOKEN`. Foto única → `zerogpu-aoti/wan2-2-fp8da-aoti-faster`;
  `foto` + `foto_final` → `multimodalart/wan-2-2-first-last-frame`. Clipes ficam em `out/clipes/NN-<hash>.mp4`
  (hash dos parâmetros da cena) e não são regerados; erro de cota sai com código 2.
- `scripts/kaggle_gerar.py` + `kaggle/wan_i2v.py` — motor principal: GPU grátis do Kaggle (T4), ComfyUI headless com
  Wan 2.2 I2V 14B GGUF + LoRA lightx2v 4 passos (2 high + 2 low). Precisa de `KAGGLE_API_TOKEN` ou `~/.kaggle/access_token`.
  Usa os mesmos nomes de clipe que `gerar_clipes.py`, então `montar_video.py` funciona com os dois.
- `scripts/montar_video.py` — ffmpeg: interpola para 30 fps, escala para 1920x1080 ou 1080x1920, fade entre clipes,
  nome do ambiente, música opcional.
- `scripts/narracao.py` — Piper TTS offline (vozes pt-BR faber/cadu/jeff, baixadas para `modelos-voz/`). `scripts/storyboard.py` — folha de
  aprovação com 3 quadros por clipe; use-a para conferir os clipes antes de montar.
- `tour.json` — roteiro do vídeo. Ao receber a ideia + fotos do usuário: olhe cada foto, escolha a ordem do passeio,
  o movimento que menos deforma aquela foto e onde vale usar `foto_final` para ligar cômodos.
- Rode Python com `.venv/bin/python -I`. O venv é criado pelo hook `.claude/hooks/setup.sh`.
- Sempre confira os clipes gerados (extraia quadros com ffmpeg e olhe) antes de montar: a IA pode deformar paredes ou móveis.

## Preferências do usuário (definidas após o 1º teste)
- **Sem narração/voz.** Trilha: piano calmo em domínio público (`scripts/baixar_musicas.sh`, Chopin/Musopen CC0).
  Padrão: `chopin-noturno-op9-n2.mp3` com `inicio_musica: 1.1`. A normalização de volume (loudnorm) ainda não foi testada.
- **Transições sem cara de corte.** Encadeie as cenas com `foto_final` = foto da cena seguinte (a câmera "anda" de um
  cômodo ao outro) e use fade longo (`transicao_segundos` ~1.0). Evite cortes secos entre ambientes.
- Modelo decidido: manter Wan 2.2 (o usuário dispensou testar LTX). Ideia pendente: rodar 2 clipes em paralelo (o Kaggle dá 2× T4 e hoje usamos 1).
