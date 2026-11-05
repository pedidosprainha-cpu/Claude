# Vídeo 02 — "A história da Terra em 24 horas"

| Item | Valor |
|---|---|
| Arquivo final | `output/video-02-terra-em-24-horas.mp4` |
| Capa | `output/capa.png` |
| Duração | 65,9 s (acima de 1 min, requisito do Programa de Recompensas para Criadores) |
| Formato | 1080×1920, 30 fps, H.264 + AAC 256 kbps, -14 LUFS |
| Loop | termina à meia-noite e volta para a Terra de lava às 00:00:00, igual ao primeiro quadro |

## O que mudou em relação ao vídeo 01

- **Ilustrações profissionais**: Fluent Emoji da Microsoft, em vetor com gradientes e sombreado (licença MIT, uso comercial liberado). Ficam no lugar das formas geométricas do vídeo 1.
- **Planeta Terra renderizado pixel a pixel**: rotação, iluminação, atmosfera, brilho especular no oceano, nuvens próprias e 4 "peles" geológicas que se transformam (lava, oceano primitivo, continentes sem vida, Terra verde).
- **Colisão de Theia e formação da Lua**: centenas de detritos incandescentes que esfriam, entram em órbita e se juntam na Lua.
- **Cenários com profundidade (parallax)**: camadas de relevo, raios de luz subaquáticos, fumaça, brasas, bolhas, céu que muda de cor, além de um zoom lento de câmera em cada cena.
- **Transições "zoom-through"** com desfoque de movimento entre as eras.
- **Relógio da Terra** no topo: horário, mini-relógio colorido por era geológica e "há X anos".
- **Som**: os tiques do relógio aceleram de verdade quando o tempo dispara, há ambiente subaquático, passos de dinossauro, fogueira, pássaros, e batimentos cardíacos sincronizados com o pulso visual na reflexão final.

## Estrutura (retenção)

| Tempo | Bloco |
|---|---|
| 0–5 s | Gancho: "nós só apareceríamos nos últimos 6 segundos" + o relógio gira o dia inteiro e a Terra evolui na tela |
| 5–6 s | Rebobina (assinatura da série) |
| 6–21 s | 1 hora = 189 milhões de anos → Terra de lava → colisão que forma a Lua |
| 21–35 s | Primeira vida (micróbios), "horas de tédio" com avanço rápido, oxigênio |
| 35–47 s | Explosão de animais, dinossauros, asteroide, mamíferos |
| 47–56 s | Humanos aos 23:59:54, pirâmides a menos de 0,1 s da meia-noite |
| 56–62 s | Zoom de ×27 milhões até a sua vida: 1,5 milésimo de segundo + reflexão |
| 62–66 s | CTA com a marca do perfil e volta para o início (loop) |

## Para publicar

**Legenda sugerida**

> Se a história da Terra fosse um dia de 24h, a gente só aparece nos últimos 6 segundos 🌍⏱️ E a sua vida inteira? Um milésimo e meio de segundo. O que você vai fazer com o seu? 👇
>
> #curiosidades #ciencia #historia #terra #dinossauros #universo #fatoscuriosos #aprendanotiktok #vocesabia

- **Comentário fixado**: "Em que horário do relógio VOCÊ achou que os dinossauros apareciam? 🦖⏱️" (puxa respostas)
- Envie o arquivo original e ative o envio em alta qualidade. Não adicione música do app.
- Como a narração usa voz sintética, ative o rótulo de conteúdo gerado por IA.

## Fontes dos números

Escala: idade da Terra = 4,54 bilhões de anos = 24 h → 1 h = 189 milhões de anos; 1 s = 52.500 anos.

| Evento | Quando | No relógio |
|---|---|---|
| Formação da Terra | 4,54 bi anos | 00:00 |
| Impacto de Theia / formação da Lua (hipótese do grande impacto, a mais aceita) | ~4,5 bi | ~00:13 |
| Primeira vida (micróbios) | ~3,8 bi | ~04:00 |
| Grande Evento de Oxigenação | ~2,4 bi | ~11:19 |
| Explosão cambriana | ~539 mi | ~21:09 |
| Primeiros dinossauros | ~230–236 mi | ~22:45 |
| Asteroide (extinção K-Pg) | 66 mi | 23:39 |
| Homo sapiens | ~300 mil | 23:59:54 |
| Pirâmides de Gizé | ~4.500 anos | 23:59:59,91 |
| Vida de 80 anos | 80 anos | 1,5 ms antes da meia-noite |

## Créditos

Ilustrações: [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) © Microsoft, licença MIT. Trilha e efeitos: originais (síntese). Fontes: Inter e JetBrains Mono (SIL OFL).

## Como regenerar

```bash
./build.sh                          # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh            # refaz a narração após editar roteiro.json
node src/render.js --preview 3,44   # quadros de prévia em build/preview/
```
