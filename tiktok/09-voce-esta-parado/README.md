# Ciência #7 — "Você acha que está parado?"

Agora mesmo, você viaja a mais de 1,3 milhão de km/h:
- a Terra gira (1.670 km/h no Equador);
- ela corre em volta do Sol (107.000 km/h, 30 km a cada segundo);
- o Sol dá a volta na galáxia (828.000 km/h; uma volta leva 230 milhões de anos, e a última começou quando surgiam os dinossauros);
- em relação à luz mais antiga do universo, o Sistema Solar se move a 1.331.280 km/h.

Por que ninguém sente? Porque o corpo não sente velocidade, só a mudança dela. O fecho é "Você nunca esteve duas vezes no mesmo lugar do universo."

| Item | Valor |
|---|---|
| Arquivo final | `output/video-09-voce-esta-parado.mp4` |
| Capa | `output/capa.png` |
| Duração | ~69 s · 1080×1920 · 30 fps · -14 LUFS |
| Loop | termina na mesma imagem do primeiro quadro |

## O que tem de especial

- **Odômetro ao vivo**: do primeiro quadro ao fim, o painel do topo mostra quanto você já percorreu desde o início do vídeo, a 369,8 km/s. Quando a narração diz "mais de vinte mil quilômetros", o número real na tela é de cerca de 21.500 km.
- **Camadas de velocidade**: o painel troca de camada a cada trecho (rotação, órbita do Sol, galáxia, universo e Estação Espacial), sempre com o valor certo.
- **Imagens reais da NASA**:
  - a Terra vista da Estação Espacial em 4K, acelerada para dar sensação de velocidade;
  - a tripulação flutuando por dentro da Estação;
  - a Estação vista de fora;
  - a janela da Cúpula.

  O `src/shots.py` lê só os trechos usados direto do servidor da NASA, sem baixar os arquivos de 16 GB e 5,6 GB.
- **Globo noturno próprio** (`src/globo.py`): projeção ortográfica das luzes da Terra (Black Marble 2016), com atmosfera e um crescente iluminado. A linha do Equador "anda" para leste, como a rotação, e São Paulo aparece marcado. No fim, a metade visível do Equador é exatamente meia volta ao mundo (20.037 km).
- **Via Láctea vista de cima**: mostra onde estamos e a nossa órbita no sentido horário, como vista do polo norte galáctico.
- **Mapa do WMAP**: a luz mais antiga do universo, com a seta apontando para a direção real do nosso movimento (o dipolo, em longitude galáctica 264° e latitude 48°, projetada no mapa).
- **Trilha original em Ré menor a 96 BPM**: ganha uma camada e um impacto grave a cada nível de velocidade. Em "por que você não sente nada?", cai para quase nada, só o zumbido da Estação, e volta no odômetro.
- Mantém o padrão do episódio anterior: voz dirigida frase a frase, reverb de convolução, ducking de trilha e efeitos sob a voz, tipografia IBM Plex Mono e Cormorant Garamond, bloom, grão, rebobinar e loop.

## Para publicar

**Legenda sugerida**

> Você acha que está parado agora? 🌍💨 Enquanto assiste a este vídeo, você já percorreu mais de 20 mil km. Olha o contador! 👀
>
> #ciencia #espaco #universo #astronomia #fisica #nasa #curiosidades #aprendanotiktok #vocesabia #terra

- **Comentário fixado**: "Quantos km você já tinha percorrido quando chegou aqui nos comentários? 😅"
- **Créditos na descrição** (já estão na tela): *Imagens: NASA (4K Earth Views, Step Inside the Station, Black Marble 2016, SDO, WMAP); ilustração da Via Láctea: NASA/JPL-Caltech/R. Hurt.*
- Ative o rótulo de conteúdo gerado por IA (narração sintética).
- Não use o logotipo da NASA nem sugira parceria.

## Fontes e números

| Dado | Valor usado | Observação |
|---|---|---|
| Rotação da Terra no Equador | 1.670 km/h (465 m/s) | circunferência de 40.075 km ÷ 23 h 56 min (dia sideral) |
| Rotação em São Paulo (23,55° S) | ≈1.530 km/h | 1.670 × cos 23,55° |
| Órbita da Terra | 107.000 km/h (29,78 km/s) | "30 km a cada segundo" |
| Sol em volta da galáxia | ~828.000 km/h (~230 km/s) | estimativas entre 220 e 250 km/s; a narração diz "mais de 800 mil" |
| Ano galáctico | ~230 milhões de anos | estimativas entre 225 e 250 milhões |
| Primeiros dinossauros | ~230–245 milhões de anos atrás (Triássico) | por isso "estavam surgindo" |
| Sistema Solar × radiação cósmica de fundo | 369,8 km/s = 1.331.280 km/h, rumo a l = 264°, b = 48° | dipolo da radiação cósmica de fundo (Planck 2018) |
| Radiação cósmica de fundo | emitida ~380 mil anos após o Big Bang | |
| Estação Espacial | ~27.600 km/h; ~16 voltas na Terra por dia | NASA |
| Meia volta ao mundo | 20.037 km | metade da circunferência equatorial |
| Odômetro | 369,8 km/s × tempo desde o início do vídeo | aos 58,1 s (quando a narração diz "vinte mil"), o valor é 21.500 km |

A sensação: o corpo só percebe aceleração, ou seja, a mudança de velocidade. Uma velocidade constante não se sente.

## Imagens e licenças

| Material | Crédito | Licença |
|---|---|---|
| Terra vista da Estação (4K) | NASA/JSC, "4K Earth Views Extended Cut for Earth Day 2021" (jsc2021m000138) | domínio público |
| Tour por dentro da Estação (4K) | NASA, "Step Inside the Station 4K Clean" | domínio público |
| `assets/terra_noite.jpg` | NASA Earth Observatory, Black Marble 2016 | domínio público |
| `assets/sol_304.jpg` | NASA/SDO (AIA 304) | domínio público |
| `assets/via_lactea.jpg` | NASA/JPL-Caltech/R. Hurt (SSC-Caltech), PIA10748 | uso livre com crédito (NASA/JPL) |
| `assets/cmb_wmap.jpg` | NASA/WMAP Science Team (mapa ILC de 9 anos) | domínio público |
| Fontes `fonts/` | IBM Plex Mono, Cormorant Garamond | SIL OFL 1.1 |

## Como regenerar

```bash
./build.sh                            # tudo (tomadas lidas do servidor da NASA; reaproveita a narração)
REGERAR_VOZ=1 ./build.sh              # refaz a narração após editar roteiro.json
node src/render.js --preview 3,40     # quadros de prévia em build/preview/
```
