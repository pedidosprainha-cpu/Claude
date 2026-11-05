# Ciência #4 — "Você nunca viu o presente"

A luz demora para chegar, então tudo o que você vê já é passado: a Lua de 1,3 s atrás, o Sol de 8 min 20 s, Andrômeda de 2,5 milhões de anos e o James Webb captando luz de mais de 13 bilhões de anos. Até a pessoa a 1 metro de você é vista como era há 3 bilionésimos de segundo.

| Item | Valor |
|---|---|
| Arquivo final | `output/video-06-voce-nunca-viu-o-presente.mp4` |
| Capa | `output/capa.png` |
| Duração | 61,4 s · 1080×1920 · 30 fps · -14 LUFS |
| Loop | termina no Sol com a Terra, igual ao primeiro quadro |

## Direção de arte

- **Imagens reais do espaço**: NASA (domínio público) e ESA/Hubble, ESA/Webb e ESO (CC BY 4.0), com crédito discreto na tela. A lista completa está em `assets/CREDITOS.md`.
- **Composição**: os astros fotografados sobre fundo preto entram por mistura "screen" e se fundem a um céu estrelado gerado em três camadas de profundidade, com névoa de cor própria em cada cena (prata na Lua, laranja no Sol, vermelho em Betelgeuse, violeta em Andrômeda, dourado no Webb).
- **A luz como personagem**: feixes com pulsos viajando de cada astro até você. No gancho, o Sol some e a última "casca" de luz ainda atravessa o espaço até a Terra, com contagem regressiva.
- **Relógio da luz no topo**: "A LUZ SAIU HÁ" e "DISTÂNCIA" rolam em escala logarítmica de 1,3 s até 13 bilhões de anos e despencam para 3 bilionésimos de segundo na virada.
- **Órion desenhada com a geometria real** da constelação. A câmera aproxima até Betelgeuse.
- **Transições de "recuo pelo espaço"** com rastros de estrelas, granulação fina de filme e vinheta.
- **Tipografia**: números finos e grandes. O fecho poético vem em serifada itálica sobre a Via Láctea fotografada da Estação Espacial.
- **Trilha original** em Dó menor a 60 BPM: um tique de relógio por segundo, coro etéreo crescendo até o Webb, quase silêncio na virada e resolução no fecho.

## Para publicar

**Legenda sugerida**

> Se o Sol sumisse agora, você ainda veria ele brilhar por 8 minutos ☀️ Tudo o que você vê já é passado… até a pessoa do seu lado. 👀 Isso mexeu com você?
>
> #ciencia #espaco #astronomia #universo #jameswebb #curiosidades #fatoscuriosos #aprendanotiktok #vocesabia

- **Comentário fixado**: "Qual desses tempos te deixou mais impressionado? 🌌"
- **Créditos na descrição** (opcional, já estão na tela): *Imagens: NASA; ESA/Hubble; ESA/Webb; ESO/ALMA (CC BY 4.0).*
- Ative o rótulo de conteúdo gerado por IA (narração sintética).
- Não use o logotipo da NASA nem sugira patrocínio ou endosso da agência. As imagens são de domínio público, mas a marca não é.

## Fontes e números

| Dado | Valor |
|---|---|
| Velocidade da luz | 299.792 km/s (~300 mil km/s) |
| Terra–Lua | 384.400 km → 1,28 s |
| Terra–Sol | 149,6 milhões de km → 499 s ≈ 8 min 20 s |
| Proxima Centauri | 4,24 anos-luz |
| Betelgeuse | ~550 anos-luz (estimativas recentes ~548; antigas ~640). A narração diz "mais de 500 anos". |
| Andrômeda | ~2,5 milhões de anos-luz; o controle do fogo pelos hominídeos é bem posterior (~1 milhão de anos) |
| James Webb | já observou galáxias cuja luz viajou mais de 13 bilhões de anos (recorde ~13,5 bilhões) |
| 1 metro | 1 m ÷ c ≈ 3,3 nanossegundos (3 bilionésimos de segundo) |

## Como regenerar

```bash
./build.sh                           # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh             # refaz a narração após editar roteiro.json
node src/render.js --preview 3,40    # quadros de prévia em build/preview/
```
