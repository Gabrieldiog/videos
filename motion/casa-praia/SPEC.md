# SPEC — Casa de praia (mistura dos 3 roteiros)

GOAL:    o anfitrião assiste e pensa "eu quero esse vídeo no meu Instagram"; o hóspede termina querendo reservar.
OUTPUT:  HyperFrames, 1080 x 1920, 30 fps
TIME:    32.6 s x 30 = 978 frames. Piano (Chopin, Noturno Op. 9 nº 2, ~60 BPM livre): sem grade de batida,
         as frases entram nas respirações da música.
LOOK:    a filmagem real (clipes Wan 2.2) é o fundo do começo ao fim; nada de fundo liso até o cartão final.
         Tinta: branco #FFFFFF com sombra 0 2px 24px rgba(0,0,0,.35); scrim no topo rgba(0,0,0,.45) → 0 em 900 px.
         Acento: marca-texto areia #E9D3B0 atrás de UMA expressão por frase, texto da marca em verde #1E3D38.
         Verde da fachada #1E3D38 como cor do final (tinta multiply sobre a piscina, depois chão sólido).
         Títulos: Playfair Display 700, 112 px (5,8% da altura), tracking -1%, alinhados à esquerda em x = 108.
         Texto: Montserrat 500/600, 40–48 px. Horários: Playfair Display 500, 168 px.
         Faixa segura vertical: todo texto entre y = 300 e y = 1330.
OBJECTS: a casa real (piscina, sala, varanda, quartos) só pela filmagem; estrelas ★ em areia; a nota "4,97".
MOTION:  entrada de título: palavra por palavra, blur 6 px → 0 e opacidade 0 → 1 em 0,13 s, 0,067 s entre palavras;
         marca-texto: scaleX 0 → 1 em 0,35 s expo.out; saída: blur-out 0,18 s power2.in (40% mais curta);
         contagem 0 → 4,97 em 1,4 s power3.out; estrelas 0,08 s entre si, scale 0,6 → 1 back.out(1.4);
         inundação de cor 0,4 s power2.inOut; grupo da nota sobe 0,6 s power3.inOut.
SHOTS:
  1  0.0–4.2   piscina (câmera avança)       "Você quer um lugar / muito bom?" já na tela no quadro 0; 2.6 s "Pra descansar / de verdade?"   → dip
  2  4.2–8.0   entrada → sala de jantar      "Espaço pra / família toda?"                                                                  → corte casado (mesmo quadro)
  3  8.0–11.8  sala de jantar → varanda      "08:00 / café da manhã na varanda"                                                           → corte casado
  4  11.8–14.6 varanda → jardim               "17:30 / fim de tarde no jardim"                                                             → dip
  5  14.6–17.4 sala íntima                    (sem texto: a imagem respira)                                                                → corte no movimento
  6  17.4–20.1 quarto                         "E um quarto / muito bom?" (eco do gancho)                                                   → corte no movimento
  7  20.1–22.8 suíte                          (texto do 6 sai em 20.4)                                                                     → dip
  8  22.8–32.6 piscina (câmera recua, 0,5x)   "Então é aqui." → 4,97 com a piscina DENTRO dos números + ★★★★★ + "103 avaliações"
                                              → verde inunda → cartão: nome, cidade, "Reserve no Airbnb" (segura 2,5 s)
BANNED:  fundo escuro liso com elementos flutuando; brilho/glow/partículas; gradientes roxos/azuis; cartões de vidro;
         tudo centralizado; tudo entrando com fade + slide-up; texto que se mexe enquanto é lido; pílulas e botões;
         rótulos "01 / 02"; logo no canto; crossfade entre ambientes; filtros CSS na filmagem.
QA:      quadro 0 (gancho legível = thumbnail) · 1.0 (marca-texto completa) · 9.5 (horário legível sobre a sala) ·
         18.5 (eco "muito bom?") · 26.5 (piscina visível dentro do 4,97) · 31.5 (cartão final completo).
DADOS:   nota, nº de avaliações, nome e cidade são PROVISÓRIOS até o usuário confirmar (variáveis em compositions/final.html).
