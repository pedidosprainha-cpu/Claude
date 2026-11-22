# Ciência #8 — "A gosma sem cérebro"

O *Physarum polycephalum*, o "blob", é um bolor limoso. Não é fungo, planta nem animal: é uma única célula, que dá para ver a olho nu, com milhares de núcleos e nenhum neurônio. Mesmo assim:

1. resolve labirintos, ficando só com o caminho mais curto (Nakagaki, 2000);
2. com flocos de aveia no lugar de 36 cidades, liga a região de Tóquio com uma rede muito parecida com a dos trens (Tero et al., 2010);
3. usa o próprio rastro de muco como memória (Reid et al., 2012);
4. aprende a ignorar o que não faz mal (Boisseau et al., 2016);
5. passa o que aprendeu para outra ao se fundir com ela (Vogel & Dussutour, 2016).

| Item | Valor |
|---|---|
| Arquivo final | `output/video-11-a-gosma-sem-cerebro.mp4` |
| Capa | `output/capa.png` |
| Duração | ~75 s · 1080×1920 · 30 fps · -14 LUFS |
| Loop | termina na mesma imagem do primeiro quadro |

## Narração nova: mais natural

Os vídeos 1 a 10 usavam a voz pt-BR-AntonioNeural (Edge TTS), a voz sintética mais comum do TikTok brasileiro, com entonação regular demais. Este episódio usa outro motor e outro método.

- **Motor**: [Chatterbox Multilingual](https://github.com/resemble-ai/chatterbox) (Resemble AI, licença MIT), rodando local, sem serviço pago.
- **Voz em duas camadas**:
  - uma referência brasileira nativa condiciona sotaque e entonação;
  - outra dá um timbre mais grave e quente.

  As duas são vozes sintéticas (`voz/LEIA-ME.md`), não de pessoas reais.
- **Roteiro escrito para ser falado**: frases curtas, "pra", "Ah,", "botou ela", "me diz" e uma pergunta no fim, em vez de texto de redação.
- **Direção por tomadas** (`src/voz.py`): cada frase é gravada 2 ou 3 vezes. O Whisper transcreve cada tomada e descarta as que trocam, repetem ou engolem palavras. Entre as corretas fica a mais clara e com a entonação mais viva. Os cortes seguem as palavras reconhecidas, e pausas longas demais são encurtadas.
- **Montagem com pausas variadas**: as frases são montadas com pausas diferentes (curtas entre ideias ligadas, longas antes da virada), em vez do ritmo uniforme de um TTS comum.

Teste com a mesma frase de abertura:

| Voz | Confiança do Whisper | Variação de entonação | Ritmo |
|---|---|---|---|
| Antonio (Edge, usada até o vídeo 10) | −0,21 (errou "nem um" → "nenhum") | 4,5 semitons | 2,0 palavras/s |
| Nova (Chatterbox, sotaque BR + timbre grave) | −0,10 (sem erros) | 4,3 semitons | 2,3 palavras/s |

A confiança é medida por um reconhecedor treinado em fala humana; quanto mais perto de zero, mais a voz soa como gente falando.

## Direção de arte: laboratório

- **A gosma é simulada, não é filmagem**. `src/cenas.py` usa os modelos matemáticos dos próprios pesquisadores:
  - o modelo de Tero et al. (2007) para o labirinto;
  - o modelo de Tero et al. (2010) para Tóquio, em que cada tubo engrossa com o fluxo e some sem uso: dD/dt = f(|Q|) − D.

  O crescimento acontece em malha orgânica, com uma frente em leque e veias atrás. Toda cena simulada traz a etiqueta "SIMULAÇÃO".
- **Sombreamento de gel** (`src/gel.py`): relevo, luz rasante, brilho úmido, translucidez, citoplasma granulado e sombra no ágar, como numa macrofotografia.
- **Pulsação**: a espessura das veias pulsa em ondas que saem da origem, imitando o vaivém do protoplasma (*shuttle streaming*).
- **Mapa real**:
  - litoral e ferrovias da Natural Earth;
  - 36 flocos de aveia nas cidades da região;
  - no fim, os trilhos de verdade aparecem por cima da rede da gosma.
- **Interface de câmera de laboratório**: relógio de time-lapse, barra de escala e a referência de cada artigo no canto.
- **Trilha original** em Fá lídio, com marimba, kalimba e um pulso grave que "respira". Efeitos de bolhas, tique de relógio, aveia caindo, sal e um carrilhão genérico de estação.
- Mantém o padrão da série: legendas palavra por palavra, rebobinar, tela da marca e loop.

## Para publicar

**Legenda sugerida**

> Essa gosma não tem cérebro… e refez a rede de trens de Tóquio 🟡🚆 Ela também resolve labirintos, aprende e até ensina outra. O que é inteligência, afinal? 👇
>
> #ciencia #biologia #curiosidades #physarum #blob #vocesabia #aprendanotiktok #natureza #inteligencia

- **Comentário fixado**: "Bônus: esses experimentos ganharam DOIS prêmios Ig Nobel (2008 e 2010) 🏆 Inteligência precisa de cérebro? 🤔"
- **Créditos na descrição**: *Simulações próprias com os modelos de Tero et al. (2007, 2010). Mapa: Natural Earth (domínio público).*
- Ative o rótulo de conteúdo gerado por IA (narração sintética).

## Fontes e números

| Dado | Valor usado | Fonte |
|---|---|---|
| O que é | *Physarum polycephalum*, bolor limoso (amebozoário); uma célula gigante com milhares de núcleos, sem neurônios | revisões e EMBL |
| Labirinto | pedaços espalhados no labirinto se fundem e ocupam tudo; com aveia na entrada e na saída, os tubos dos becos sem saída somem e fica o caminho mais curto (em 4 h quase todo; em ~8 h só o mais curto) | Nakagaki, Yamada & Tóth, *Nature* 407:470 (2000) |
| Tóquio | aveia no lugar de 36 cidades, gosma começando em Tóquio; em ~26 h, rede com eficiência, tolerância a falhas e custo comparáveis aos da rede ferroviária real | Tero et al., *Science* 327:439 (2010) |
| A regra | dD/dt = f(\|Q\|) − D: tubo com mais fluxo engrossa, tubo sem uso some | Tero, Kobayashi & Nakagaki, *J. Theor. Biol.* (2007); Tero et al. (2010) |
| Rastro | evita áreas já cobertas de muco extracelular: uma memória espacial externa (escapou de uma armadilha em U em 96% dos testes) | Reid et al., *PNAS* (2012) |
| Sal / habituação | aprende a atravessar pontes com substâncias repelentes (quinina, cafeína); no trabalho da fusão, com sal | Boisseau, Vogel & Dussutour, *Proc. R. Soc. B* (2016) |
| Fusão | ao se fundir (por cerca de 3 h) com uma gosma habituada ao sal, uma gosma "ingênua" passa a se comportar como habituada; basta uma habituada na fusão | Vogel & Dussutour, *Proc. R. Soc. B* (2016) |
| Ig Nobel | 2008 (ciência cognitiva, labirinto) e 2010 (planejamento de transportes, Tóquio) | improbable.com |

Cuidados de precisão:
- A narração diz "muito parecida com a dos trens de verdade", e não "igual" nem "melhor".
- As imagens são simulações e estão marcadas como tal.
- As ferrovias da Natural Earth mostram só as linhas principais, por isso a comparação é visual.

## Imagens, dados e licenças

| Material | Crédito | Licença |
|---|---|---|
| Gosma, labirinto, pontes, arena | simulação própria (`src/cenas.py`, `src/tero.py`, `src/molde.py`, `src/gel.py`) | deste projeto |
| Litoral e ferrovias (`assets/mapa/`) | Natural Earth, 1:10m (recorte da região) | domínio público |
| Posição das 36 cidades (`assets/cidades.json`) | coordenadas aproximadas das estações centrais | — |
| Fontes `fonts/` | IBM Plex Mono, Cormorant Garamond | SIL OFL 1.1 |
| Motor de voz | Chatterbox Multilingual (Resemble AI) | MIT |
| Reconhecimento de fala (checagem) | Whisper large-v3-turbo via faster-whisper | MIT |

## Como regenerar

```bash
# ambiente da voz (uma vez)
python3 -m venv ../.venv-voz && ../.venv-voz/bin/pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
../.venv-voz/bin/pip install chatterbox-tts faster-whisper praat-parselmouth

./build.sh                                          # tudo (reaproveita narração e simulações)
VOZ_PY=../.venv-voz/bin/python REGERAR_VOZ=1 ./build.sh   # regrava a narração
REGERAR_CENAS=1 ./build.sh                          # refaz as simulações
node src/render.js --preview 3,40                   # quadros de prévia em build/preview/
```
