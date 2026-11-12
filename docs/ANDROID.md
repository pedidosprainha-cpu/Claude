# Aplicativo Android

Aplicativo nativo em **Kotlin + Jetpack Compose (Material 3)**, Android 8.0+ (minSdk 26, targetSdk 35).
APK instalável: `releases/FXIntel-1.0.0.apk`, release assinado, minificado com R8, cerca de 1,6 MB.

| Cartão de sinal (render JVM com dados reais da API) | Gráfico com Entrada/SL/TP |
|---|---|
| ![sinal](img/android-sinal.png) | ![gráfico](img/android-grafico.png) |

> As imagens acima foram renderizadas na JVM com Paparazzi, a partir de respostas reais do backend. O cartão
> usa uma observação real promovida a "sinal" apenas para exibir todos os campos. Não havia emulador/KVM
> disponível neste ambiente, então o app **não foi executado em um aparelho** durante o desenvolvimento.
> Valide a instalação no seu dispositivo (ver checklist abaixo).

## Funcionalidades

- **Painel:** cotações em tempo real (WebSocket, com fallback para consulta a cada 10 s), botão central
  **ANALISAR MERCADO AGORA**, resultado com a estrutura completa do sinal, barra de probabilidade calibrada com
  IC 90%, justificativas técnicas/fundamentalistas/quantitativas, invalidação, cenários, portões, tamanho da posição
  e execução em conta demo. Também mostra observações não recomendadas, gráfico de candles (M15/H1/H4/D1) com
  linhas de Entrada, SL, TP1 e TP2, visão do mercado (tendências D1/H4/H1, score fundamental, regime, eventos),
  força relativa das moedas e próximos eventos.
- **Histórico:** sinais emitidos com status forward e resultado em R; análises anteriores, que podem ser reabertas no Painel.
- **Alertas:** lista com badge de não lidos; notificações do sistema em tempo real (app aberto) e por
  WorkManager a cada 15 min (app em segundo plano).
- **Ajustes:** URL do servidor e chave de API (com teste de conexão), notificações, instrumentos monitorados,
  capital, risco por trade, perda diária, máximo de posições, EV e R:R mínimos, exigência de modelo validado.
  Inclui ainda o painel de **conectividade e integridade**: rede do aparelho, canal de dados, servidor, provedores,
  banco, modelo e última cotação.

## Compilação

Requisitos: JDK 17+ e Android SDK (platform 35, build-tools 35).

```bash
cd android
echo "sdk.dir=/caminho/para/android-sdk" > local.properties
./gradlew assembleDebug                      # app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest                  # testes de parsing com respostas reais da API
./gradlew recordPaparazziDebug               # renderiza os componentes (snapshots)
```

Release assinado: crie `android/keystore.properties` (não versionado):

```
storeFile=release.jks
storePassword=…
keyAlias=fxintel
keyPassword=…
```

```bash
keytool -genkeypair -keystore release.jks -alias fxintel -keyalg RSA -keysize 3072 -validity 9125
./gradlew assembleRelease                    # app/build/outputs/apk/release/app-release.apk
```

> A chave que assinou o APK de `releases/` foi gerada no ambiente de build e **não está no repositório**.
> Para publicar atualizações instaláveis por cima, gere sua própria chave e mantenha-a. Um APK assinado com
> outra chave exige desinstalar a versão anterior.

## Checklist de validação no dispositivo

1. Instalar o APK e abrir o app: a aba Ajustes abre por padrão na primeira execução.
2. Testar a conexão com o servidor e salvar: o selo "ao vivo" aparece e as cotações atualizam a cada ~10 s.
3. Tocar em ANALISAR MERCADO AGORA: o resultado aparece em ~3–20 s.
4. Tocar numa observação: o gráfico passa a mostrar Entrada, SL e TPs.
5. Desligar o Wi-Fi: o selo muda para "sem rede". Ao religar, a conexão é restabelecida.
6. Conceder permissão de notificações e verificar os alertas (por exemplo, evento econômico próximo).
