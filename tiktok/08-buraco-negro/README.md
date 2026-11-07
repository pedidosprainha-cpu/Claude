# Ciência #6 — "O que acontece se você cair num buraco negro?"

O vídeo usa a simulação de supercomputador da NASA (Goddard, 2024) de uma câmera que cai num buraco negro igual ao do centro da nossa galáxia.
- A queda leva umas 3 horas, com quase duas voltas.
- Quem olha de longe vê você ficar lento, vermelho e congelar na beira.
- Para você, cruzar o horizonte passa despercebido; depois disso restam 12,8 segundos.
- Quem só passa raspando volta 36 minutos mais jovem.

| Item | Valor |
|---|---|
| Arquivo final | `output/video-08-buraco-negro.mp4` |
| Capa | `output/capa.png` |
| Duração | ~70 s · 1080×1920 · 30 fps · -14 LUFS |
| Loop | termina na mesma imagem do primeiro quadro |

## O que mudou na produção (padrão novo da série)

- **Imagem real de simulação científica**, não ilustração. As tomadas verticais são **câmeras virtuais dentro do filme 360° de 8K da NASA**: `src/shots.py` usa o filtro `v360` do ffmpeg com direção e campo de visão animados quadro a quadro. Isso permite inclinar a câmera para cima depois de cruzar o horizonte e fazer um chicote de 180° na reviravolta.
- **Plano-sequência**: cruzar o horizonte, lá dentro e o fim acontecem numa só tomada contínua.
- **Painel com os relógios reais da simulação**: os tempos "seu relógio" e "lá fora" foram lidos do filme de comparação de relógios da NASA, em 28 pontos, e interpolados. Quando você cruza o horizonte, o relógio de fora vira ∞, como na NASA.
- **Infográfico**: o horizonte de eventos tem 25 milhões de km, o que dá 18 sóis enfileirados (25,4 ÷ 1,39).
- **Panorama 360° da Via Láctea** (ESO) para voar até o centro da galáxia, com corte para a primeira imagem real de Sagitário A* (EHT).
- **Astronauta real** (Bruce McCandless, NASA, 1984) recortado: fica vermelho e congela visto de longe e é esticado na espaguetificação.
- **Piscar de olhos literal**: as pálpebras fecham na tela em "num piscar de olhos".
- **Tipografia de documentário**: IBM Plex Mono nos instrumentos e Cormorant Garamond nos títulos (ambas OFL, em `fonts/`). Acabamento com bloom, grão e vinheta.
- **Voz dirigida frase a frase**: velocidade e tom próprios no `roteiro.json`. Em "e congela na beira", a voz perde rotação como uma fita.
- **Som**:
  - Reverb de convolução (resposta ao impulso sintética).
  - "Braam" de trailer no gancho.
  - A trilha para como fita no "congela", e há silêncio total no instante de cruzar o horizonte.
  - Tom de Shepard (queda sem fim) lá dentro.
  - Tique-taque de dois relógios.
  - Cadeia de voz com de-esser, EQ, compressão e reverb curto de sala.

## Para publicar

**Legenda sugerida**

> Isso é uma simulação REAL da NASA do que você veria caindo num buraco negro 🕳️ E o mais estranho é o que acontece com o tempo ⏳ Você teria coragem? 👇
>
> #ciencia #buraconegro #espaco #astronomia #nasa #universo #fisica #curiosidades #aprendanotiktok #vocesabia

- **Comentário fixado**: "Se desse pra voltar 36 minutos mais jovem, você passaria raspando? 😅"
- **Créditos na descrição** (já estão na tela): *Simulação: NASA's Goddard Space Flight Center/J. Schnittman and B. Powell. Via Láctea: ESO/S. Brunier. Sagitário A\*: EHT Collaboration (CC BY 4.0). Foto: NASA.*
- Ative o rótulo de conteúdo gerado por IA (narração sintética).
- Não use o logotipo da NASA nem sugira parceria. O texto diz "simulação da NASA", que é um fato e não um endosso.

## Fontes e números

| Dado | Valor usado | Fonte |
|---|---|---|
| Buraco negro simulado | 4,3 milhões de massas solares, sem rotação, igual ao do centro da Via Láctea | NASA SVS 14576; science.nasa.gov ("New NASA Black Hole Visualization Takes Viewers Beyond the Brink", 6 maio 2024) |
| Horizonte de eventos | ~25 milhões de km de diâmetro (~17% da distância Terra–Sol) | idem |
| Distância inicial | ~640 milhões de km | idem |
| Duração da queda | ~3 h até o horizonte, com quase duas órbitas de 30 min (relógio da simulação: 3 h 15 min) | idem + filme "Plunge clock comparison" |
| Visto de longe | a imagem desacelera e congela pouco antes do horizonte ("estrelas congeladas") | idem |
| Depois do horizonte | destruição por espaguetificação em 12,8 s; 128 mil km até a singularidade | idem (citação de J. Schnittman) |
| Supermassivo × estelar | em buracos negros estelares, as forças de maré rasgam você antes do horizonte | idem |
| Voo rasante | ida e volta de 6 h, volta 36 min mais jovem; velocidade máxima de 60% da luz | idem + descrição do filme "flyby" |
| Supercomputador | Discover (NCCS): ~10 TB de dados, ~5 dias usando 0,3% dos 129 mil processadores | idem |
| Sagitário A* | primeira imagem em 2022; ~27 mil anos-luz | ESO eso2208-eht-mwa |
| "Disco por cima e por baixo" | a luz do lado de trás do disco se curva por cima e por baixo do buraco negro | descrição dos filmes SVS (imagens do disco que se duplicam) |
| Relógios no painel | valores lidos do filme de relógios da NASA em 28 pontos e interpolados; "lá fora" vira ∞ ao cruzar o horizonte | filme SVS "Plunge clock comparison" |

## Imagens e licenças

| Material | Crédito | Licença |
|---|---|---|
| Simulações (mergulho e voo rasante, 360° 8K) | NASA's Goddard Space Flight Center/J. Schnittman and B. Powell | domínio público (NASA). Só os filmes brutos, sem a trilha comercial dos vídeos "explainer" |
| `assets/via_lactea_360.jpg` | ESO/S. Brunier (eso0932a) | CC BY 4.0 |
| `assets/sgr_a.jpg` | EHT Collaboration (ESO eso2208-eht-mwa) | CC BY 4.0 |
| `assets/astronauta.png` | NASA (S84-27017, Bruce McCandless, STS-41B) | domínio público |
| `assets/sol.jpg` | NASA/SDO | domínio público |
| Fontes `fonts/` | IBM Plex Mono (IBM), Cormorant Garamond (Cormorant Project) | SIL OFL 1.1 |

## Como regenerar

```bash
./src/baixar.sh                       # baixa as simulações 8K da NASA (~1,6 GB) para ./footage
./build.sh                            # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh              # refaz a narração após editar roteiro.json
node src/render.js --preview 3,40     # quadros de prévia em build/preview/
```
