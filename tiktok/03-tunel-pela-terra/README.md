# Vídeo 03 — "E se você pulasse num túnel que atravessa a Terra?"

| Item | Valor |
|---|---|
| Arquivo final | `output/video-03-tunel-pela-terra.mp4` |
| Capa | `output/capa.png` |
| Duração | 61,9 s (acima de 1 min) |
| Formato | 1080×1920, 30 fps, H.264 + AAC 256 kbps, -14 LUFS |
| Loop | termina no globo com o "VOCÊ AQUI" no Brasil, igual ao primeiro quadro |

## O que este vídeo traz de novo

- **Física de verdade**: a queda foi simulada numericamente (`src/fisica.py`) com a densidade real de cada camada da Terra (modelo em camadas baseado no PREM). Resultado: **38,4 minutos** até o outro lado e **35.287 km/h** no centro. É o mesmo resultado dos estudos científicos, e não os "42 minutos" que circulam na internet (esse valor supõe uma Terra de densidade uniforme).
- **Painel ao vivo**: tempo de queda, profundidade, velocidade e temperatura mudam a cada quadro conforme a simulação.
- **Mapa-múndi real** (Natural Earth) no globo 3D, com o Brasil destacado. O antípoda de Brasília cai de fato no mar das Filipinas, entre o Japão e as Filipinas.
- **Túnel em perspectiva**: as paredes mudam de material conforme a camada real em que você está (rocha, manto incandescente, ferro líquido, núcleo branco de tão quente) e terminam na luz da saída.
- **Mini-mapa** com a sua posição dentro do corte da Terra. Ele cresce para explicar o campo magnético.
- **Som guiado pela física**: o vento acompanha a velocidade real da queda e abaixa sozinho quando o narrador fala. Há ainda borbulhas no núcleo, zumbido elétrico no campo magnético e um whoosh a cada passagem pelo centro.

## Estrutura (retenção)

| Tempo | Bloco |
|---|---|
| 0–5 s | Gancho: globo com "VOCÊ AQUI" no Brasil → corte da Terra → túnel → "38 minutos" |
| 5–6 s | Rebobina (assinatura da série) |
| 6–8 s | Pulo no buraco (paisagem brasileira) |
| 8–40 s | Queda: crosta → manto → núcleo externo (campo magnético) → núcleo interno (≈ superfície do Sol) → centro a 35 mil km/h |
| 40–46 s | Freando até parar exatamente na saída |
| 46–52 s | Onde fica a saída: globo gira até o Pacífico, entre Japão e Filipinas |
| 52–58 s | Reviravolta: você cai de volta e fica indo e voltando para sempre (ida e volta a cada 1h17) |
| 58–62 s | CTA com a marca e volta ao início (loop) |

## Para publicar

**Legenda sugerida**

> Se você pulasse num túnel que atravessa a Terra, chegaria do outro lado em 38 minutos 🌍🕳️ E pulando do Brasil, você sairia no meio do Pacífico! Você teria coragem? 👇
>
> #curiosidades #ciencia #fisica #terra #espaco #fatoscuriosos #aprendanotiktok #vocesabia #brasil

- **Comentário fixado**: "Qual camada você acha que seria a mais perigosa? 🔥"
- Envie o arquivo original e ative o envio em alta qualidade. Não adicione música do app.
- Como a narração usa voz sintética, ative o rótulo de conteúdo gerado por IA.

## Fontes e premissas

| Dado | Valor |
|---|---|
| Tempo de queda (densidade real, túnel sem ar, passando pelo centro) | 38,4 min (Klotz, *Am. J. Phys.* 2015, chegou a ~38 min) |
| Velocidade máxima (no centro) | ~35 mil km/h |
| Crosta continental | ~35 km |
| Manto | até ~2.890 km de profundidade |
| Núcleo externo (ferro líquido, gera o campo magnético) | 2.890–5.150 km |
| Núcleo interno (ferro sólido) | 5.150–6.371 km, ~5.400 °C |
| Superfície do Sol (fotosfera) | ~5.500 °C |
| Antípoda de Brasília (15,8°S 47,9°O) | 15,8°N 132,1°L, mar das Filipinas |
| Ida e volta (oscilação) | 2 × 38,4 min ≈ 1h17 |

Premissas assumidas, que são as mesmas do experimento mental clássico: túnel em linha reta pelo centro, sem ar, sem atrito e sem o efeito da rotação da Terra. Na prática seria impossível (calor e pressão), e a narração deixa isso implícito ao tratar o vídeo como "e se".

## Créditos

Ilustrações: [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) © Microsoft, licença MIT. Mapa: [Natural Earth](https://www.naturalearthdata.com/) (domínio público) via `world-atlas` (ISC). Trilha e efeitos: originais (síntese). Fontes: Inter e JetBrains Mono (SIL OFL).

## Como regenerar

```bash
./build.sh                          # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh            # refaz a narração após editar roteiro.json
node src/render.js --preview 3,38   # quadros de prévia em build/preview/
```
