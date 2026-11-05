# Vídeo 04 — "A banda que vendeu 2 milhões de discos e durou 8 meses"

Curiosidade sobre a música brasileira dos anos 90: a história dos Mamonas Assassinas.

| Item | Valor |
|---|---|
| Arquivo final | `output/video-04-mamonas-assassinas.mp4` |
| Capa | `output/capa.png` |
| Duração | 62,0 s (acima de 1 min) |
| Formato | 1080×1920, 30 fps, H.264 + AAC 256 kbps, -14 LUFS |
| Loop | termina no CD girando com o contador em zero, igual ao primeiro quadro |

## Ilustrações 100% próprias

Neste vídeo **nenhuma arte de terceiros** foi usada. Todas as ilustrações foram desenhadas em código (vetor, em `src/render.js`):

- CD iridescente com furo real, trilhas e reflexos; caixinha de CD em acrílico com dobradiça
- Capas fictícias (UTOPIA séria e a capa colorida anos 90). Não reproduzem as capas reais, foram criadas para o vídeo.
- Garagem de tijolos com lâmpada pendurada, amplificador e cartaz de ensaio
- Silhuetas genéricas de banda (vocal, guitarra, baixo, teclado e bateria) com luz de recorte. Não retratam a aparência dos integrantes.
- Plateia com braços, risadas "HAHA" e lanternas de celular
- Loja de discos com prateleiras, placa "ENCALHADOS" e teia de aranha
- Palco com cortina de veludo, holofotes volumétricos e piso em perspectiva
- Máscara de riso, explosão de CDs, padrão gráfico "Memphis" e raios de sol anos 90
- TV de tubo com antena, rádio portátil com toca-fitas e alto-falantes pulsando, balões e chapéus de festa
- Torre de CDs comparada a dois Everests, calendário de folhinha, estrelas e notas musicais
- O mapa do Brasil é desenhado a partir de dados geográficos de domínio público (Natural Earth)

**Música**: nenhuma gravação ou melodia dos Mamonas Assassinas é usada. As músicas deles são protegidas por direitos autorais. A trilha é original, composta e sintetizada no estilo pop-rock dos anos 90, com clima mais sombrio na fase Utopia e "trombone triste" no fracasso.

## Estrutura (retenção)

| Tempo | Bloco |
|---|---|
| 0–6 s | Gancho: "vendeu mais de 2 milhões de discos com um único álbum… e a fama durou só 8 meses" (contador + calendário) |
| 6–7 s | Rebobina em VHS (assinatura da série) |
| 7–15 s | Origem: banda séria Utopia em Guarulhos (SP) → disco encalhado (pausa cômica com trombone triste) |
| 15–26 s | A virada: a plateia ria das palhaçadas → viram banda de humor → nome novo |
| 26–43 s | Explosão: 1995, mais de 2 milhões de cópias; a pilha de CDs teria 20 km (2× o Everest); TV, rádio e festas |
| 43–51 s | Homenagem: 2 de março de 1996. As luzes se apagam uma a uma e fica só o microfone. |
| 51–58 s | Legado: cinco estrelas → 30 anos depois o Brasil ainda canta |
| 58–62 s | CTA com a marca e volta ao início (loop) |

## Para publicar

**Legenda sugerida**

> Eles venderam mais de 2 milhões de discos com UM álbum… e a fama durou só 8 meses 💿🎸 Qual música dos Mamonas você sabe de cor? 👇
>
> #mamonasassassinas #anos90 #musicabrasileira #nostalgia #curiosidades #historia #fatoscuriosos #aprendanotiktok #vocesabia

- **Comentário fixado**: "Qual música dos Mamonas você sabe inteira? 🎤" O público vai responder com os títulos, e isso gera muito comentário.
- Envie o arquivo original e ative o envio em alta qualidade.
- **Não** coloque músicas dos Mamonas por cima pelo app. O vídeo já tem trilha original, e usar a gravação real pode gerar bloqueio de áudio ou desmonetização.
- Como a narração usa voz sintética, ative o rótulo de conteúdo gerado por IA.
- O vídeo trata de um acidente real com respeito. Evite legendas ou comentários fixados em tom de piada sobre a tragédia.

## Fontes e números

| Dado | Valor usado |
|---|---|
| Origem | Banda Utopia, de Guarulhos (SP), início dos anos 90, rock sério e pouco sucesso |
| Virada | Passaram a apostar no humor e viraram Mamonas Assassinas |
| Disco | Único álbum de estúdio, lançado em 1995. A narração diz "mais de 2 milhões de cópias", um valor conservador: fontes falam em até ~3 milhões. |
| Acidente | 2 de março de 1996, queda do avião da banda na Serra da Cantareira (SP); os cinco integrantes morreram |
| Tempo de fama | ~8 meses (lançamento em meados de 1995 → março de 1996) |
| Pilha de CDs | 2.000.000 × 10,4 mm (caixinha padrão) = 20,8 km; Everest = 8,849 km → mais que 2× |
| "30 anos depois" | 1996 → 2026 |

## Como regenerar

```bash
./build.sh                           # tudo (reaproveita a narração)
REGERAR_VOZ=1 ./build.sh             # refaz a narração após editar roteiro.json
node src/render.js --preview 3,30    # quadros de prévia em build/preview/
```
