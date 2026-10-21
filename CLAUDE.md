# Projeto: tour realista de apartamento a partir de fotos

O usuário quer vídeos **realistas** (câmera se movendo pelo imóvel), não motion graphics.
Não use Remotion/HyperFrames aqui.

- `scripts/gerar_clipes.py` — chama Wan 2.2 em Spaces do Hugging Face (ZeroGPU) via `gradio_client`.
  Precisa de `HF_TOKEN`. Foto única → `zerogpu-aoti/wan2-2-fp8da-aoti-faster`;
  `foto` + `foto_final` → `multimodalart/wan-2-2-first-last-frame`. Clipes ficam em `out/clipes/NN-<hash>.mp4`
  (hash dos parâmetros da cena) e não são regerados; erro de cota sai com código 2.
- `scripts/montar_video.py` — ffmpeg: interpola para 30 fps, escala para 1920x1080 ou 1080x1920, fade entre clipes,
  nome do ambiente, música opcional.
- `tour.json` — roteiro do vídeo. Ao receber a ideia + fotos do usuário: olhe cada foto, escolha a ordem do passeio,
  o movimento que menos deforma aquela foto e onde vale usar `foto_final` para ligar cômodos.
- Rode Python com `.venv/bin/python -I`. O venv é criado pelo hook `.claude/hooks/setup.sh`.
- Sempre confira os clipes gerados (extraia quadros com ffmpeg e olhe) antes de montar: a IA pode deformar paredes ou móveis.
