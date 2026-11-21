# História #1 — "O vulcão que criou o Frankenstein"

Em abril de 1815, o Tambora, na Indonésia, teve a maior erupção da história registrada. O enxofre lançado na atmosfera esfriou o planeta, e 1816 virou "o ano sem verão": nevou em junho nos EUA e a Europa passou fome. Na Suíça, a chuva sem fim prendeu Lord Byron e os amigos na Villa Diodati, e um desafio de histórias de terror deu origem ao *Frankenstein*, de Mary Shelley, e a *O Vampiro*, de John Polidori. Na Alemanha, a falta de aveia matou cavalos, e alguns historiadores ligam isso à invenção da draisiana (1817), o avô da bicicleta. Na época, ninguém sabia que a culpa era de um vulcão.

| Item | Valor |
|---|---|
| Arquivo final | `output/video-10-o-vulcao-que-criou-frankenstein.mp4` |
| Capa | `output/capa.png` |
| Duração | ~72 s · 1080×1920 · 30 fps · -14 LUFS |
| Loop | termina na mesma imagem do primeiro quadro |

## Direção de arte: documentário de arquivo

- **Só imagens de época, todas de domínio público ou CC0**:
  - as gravuras da edição de 1831 de *Frankenstein*;
  - a primeira edição de *O Vampiro* (1819);
  - Mary Shelley, Byron e a Villa Diodati;
  - uma caricatura de 1819 cheia de draisianas;
  - um mapa-múndi de 1817;
  - a cratera do Tambora vista do espaço (NASA, 1988).

  Lista completa em `assets/CREDITOS.md`.
- **Etiquetas de museu**: título em serifada itálica, autor e acervo em mono. Pinturas que não mostram o fato em si (o Vesúvio de Volaire e a tempestade de neve de Turner) aparecem marcadas como "ilustrativo".
- **Ken Burns guiado por pontos focais**, páginas apresentadas como documentos sobre uma mesa escura e cartelas de data ("Abril de 1815", "1816 · O ano sem verão").
- **Mapa de 1817 animado**: o pino no Tambora, as ondas do estrondo até 2.000 km (em escala aproximada da própria gravura) e o véu de enxofre se espalhando e escurecendo o mundo.
- **Atmosfera**: brasas na erupção, neve sobre o Turner, chuva e relâmpagos na Villa Diodati e nas gravuras do monstro.
- **Película antiga**: tom sépia, tremulação, poeira, riscos, balanço de quadro e transições de "queima de filme".
- **Trilha de época em Ré menor**: cordas, violoncelo, piano abafado, coro e tímpanos. Para Mary Shelley entra uma caixinha de música; na bicicleta, um pizzicato leve. Há chuva e trovões sintetizados e o estalar de um projetor ao fundo.
- Mantém o padrão da série: voz dirigida, legendas palavra por palavra, rebobinar, tela da marca e loop.

## Para publicar

**Legenda sugerida**

> Um vulcão na Indonésia ajudou a criar o Frankenstein 🌋📖 (e ainda o primeiro vampiro chique e o avô da bicicleta 🚲). Você conhecia essa história? 👇
>
> #historia #curiosidades #frankenstein #maryshelley #literatura #vulcao #vocesabia #aprendanotiktok #fatoshistoricos

- **Comentário fixado**: "Qual dessas três coisas você mais se surpreendeu de ter vindo de um vulcão? 👀"
- **Créditos na descrição** (já estão na tela): *Imagens: Internet Archive, Rijksmuseum, Art Institute of Chicago, Library of Congress e NASA (domínio público / CC0).*
- Ative o rótulo de conteúdo gerado por IA (narração sintética).

## Fontes e números

| Dado | Valor usado | Observação |
|---|---|---|
| Erupção | Tambora, Sumbawa (Indonésia), abril de 1815 (auge em 10–11 de abril); IEV 7, a maior da história registrada | Oppenheimer, *Progress in Physical Geography* (2003) |
| Estrondo | ouvido a mais de 2.000 km (relatos chegaram a Sumatra) | relatos coletados por Stamford Raffles |
| Altura | ~4.300 m antes, ~2.850 m depois: quase 1,5 km a menos | Oppenheimer (2003) |
| Cratera | ~6 km de largura, ~1,1 km de profundidade | Smithsonian Global Volcanism Program |
| Clima | aerossóis de enxofre na estratosfera; 1816, "o ano sem verão"; neve em junho na Nova Inglaterra (6–7 de junho de 1816) | Stommel & Stommel (1983); Oppenheimer (2003) |
| Fome | 1816–1817, "a última grande crise de subsistência do mundo ocidental" | John D. Post, *The Last Great Subsistence Crisis in the Western World* (1977) |
| Villa Diodati | junho de 1816, Lago de Genebra; Byron propôs que cada um escrevesse uma história de fantasmas ("We will each write a ghost story") | introdução de Mary Shelley à edição de 1831 de *Frankenstein*, que também descreve o "verão úmido e inclemente" e a "chuva incessante" |
| Mary Shelley | nascida em 30/08/1797, tinha 18 anos em junho de 1816; passou dias sem ideia até a "visão" do estudante dando vida à criatura | mesma introdução de 1831 |
| *Frankenstein* | 1ª edição em 1º de janeiro de 1818, anônima | |
| *O Vampiro* | John Polidori, médico pessoal de Byron; publicado em abril de 1819 na *New Monthly Magazine* atribuído a Byron; o lorde Ruthven inaugurou o vampiro aristocrata e abriu caminho para o Drácula | |
| Draisiana | Karl Drais, primeira viagem em 12 de junho de 1817; sem pedais, empurrada com os pés | a ligação com a falta de aveia e a morte de cavalos é a hipótese de Hans-Erhard Lessing; por isso a narração diz "para alguns historiadores" |
| A descoberta da ligação | a relação entre o Tambora e o frio de 1816 foi proposta só no século XX (W. J. Humphreys, 1913/1920) | |

## Como regenerar

```bash
./build.sh                            # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh              # refaz a narração após editar roteiro.json
node src/render.js --preview 3,40     # quadros de prévia em build/preview/
```
