# Vídeo 01 — "Dobre uma folha 42 vezes e ela chega na Lua"

Vídeo vertical para TikTok (também serve para Reels e Shorts) do perfil de curiosidades científicas.

| Item | Valor |
|---|---|
| Arquivo final | `output/video-01-papel-ate-a-lua.mp4` |
| Capa | `output/capa.png` |
| Duração | 63,3 s (acima de 1 min: requisito do Programa de Recompensas para Criadores) |
| Formato | 1080×1920, 30 fps, H.264 + AAC 256 kbps |
| Áudio | -14 LUFS integrado, pico -1 dBTP (padrão das plataformas) |
| Loop | o último quadro é igual ao primeiro, então o vídeo emenda sem corte |

## Estrutura (retenção)

| Tempo | Bloco | Função |
|---|---|---|
| 0–4 s | **Gancho**: "Se você dobrar uma folha 42 vezes… ela chega até a Lua" + zoom-foguete até a Lua | promessa absurda nos 3 primeiros segundos |
| 4–5 s | Rebobina (efeito VHS) | quebra de padrão: "como assim?" |
| 5–15 s | "Parece mentira, mas é pura matemática" + fórmula 0,1 mm × 2ⁿ | credibilidade |
| 15–36 s | Escalada: caderno → xícara → pessoa → prédio → Burj Khalifa → Everest → espaço → Estação Espacial | um marco novo a cada ~2,5 s |
| 36–44 s | Clímax: Lua (impacto), Sol, universo observável | payoff com som e flash |
| 44–56 s | Reviravolta: "dizem que é impossível passar de 7… ERRADO" + recorde de 12 dobras | segundo gancho para quem ia sair |
| 56–60 s | Lição: crescimento exponencial ("começa devagar… e depois EXPLODE") | valor/compartilhamento |
| 60–63 s | CTA "Segue pra mais ciência que parece mentira" e volta para a folha (loop) | seguidores e replays |

## Para publicar

**Legenda sugerida**

> Dobrar uma folha 42 vezes te leva até a Lua 🌕📄 Parece mentira, mas é matemática pura. Qual marco te surpreendeu mais? 👇
>
> #curiosidades #ciencia #matematica #espaco #lua #universo #fatoscuriosos #aprendanotiktok #vocesabia

- **Capa**: escolha o quadro do título ou envie `output/capa.png` (no TikTok pelo computador dá para enviar uma imagem de capa).
- **Comentário fixado**: "Quer a parte 2 sobre o limite REAL de dobras? 👀". Isso puxa comentários, e o algoritmo valoriza muito comentários.
- Envie o arquivo original (não reexporte pelo editor do app) e ative "Enviar em alta qualidade" nas configurações.
- Não adicione música do TikTok por cima: o vídeo já tem trilha original (sintetizada do zero, sem direitos de terceiros).

## Fontes dos números (para responder comentários)

| Dado | Valor usado |
|---|---|
| Espessura de uma folha comum | 0,1 mm |
| 7 dobras | 12,8 mm (≈ caderno) |
| 10 dobras | 10,2 cm (≈ xícara) |
| 14 dobras | 1,64 m (≈ pessoa) |
| 17 dobras | 13,1 m (≈ prédio de 4 andares) |
| 23 dobras | 838,9 m (Burj Khalifa: 828 m) |
| 27 dobras | 13,4 km (Everest: 8.849 m) |
| 30 dobras | 107 km (linha de Kármán, início convencional do espaço: 100 km) |
| 32 dobras | 429 km (Estação Espacial Internacional: ~400–420 km) |
| 42 dobras | 439.805 km (distância média da Lua: 384.400 km) |
| 51 dobras | 225 milhões de km (Sol: 149,6 milhões de km) |
| 103 dobras | ~107 bilhões de anos-luz (diâmetro do universo observável: ~93 bilhões) |
| Recorde | Britney Gallivan, 2002: 12 dobras com um rolo de papel higiênico de ~1,2 km |

Simplificação assumida: a conta ignora que a folha fica menor a cada dobra. É a mesma convenção do problema clássico, e a narração não afirma que isso seja possível na prática; a reviravolta mostra justamente o limite real.

## Como regenerar

Requisitos: Python 3 (`pip install edge-tts numpy scipy`), Node 18+ e ffmpeg.

```bash
./build.sh                 # gera tudo; reaproveita a narração se já existir
REGERAR_VOZ=1 ./build.sh   # refaz a narração (após editar roteiro.json)
node src/render.js --preview 3.8,38   # quadros de prévia em build/preview/
```

| Arquivo | O que faz |
|---|---|
| `roteiro.json` | texto da narração, voz e velocidade |
| `src/tts.py` | narração neural pt-BR com o tempo de cada palavra |
| `src/timeline.py` | posiciona as falas e sincroniza legendas, dobras e marcos |
| `src/audio.py` | trilha original e efeitos sonoros (síntese) |
| `src/render.js` | animação quadro a quadro (canvas) e capa |
| `src/mix.py` | mixagem (ducking da trilha sob a voz), loudness -14 LUFS e mux final |
