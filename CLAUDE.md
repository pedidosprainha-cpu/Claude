# Projeto: fxengine

Motor de análise gráfica, quantitativa e fundamentalista de Forex (28 pares) e metais
(XAU, XAG, XPT, XPD) que aponta a melhor entrada a mercado no preço spot ao vivo.

- Quando o usuário pedir para "analisar" / "qual a melhor entrada agora", use a skill
  `analisar` (ou rode `python3 -m fxengine scan`). Nunca invente preços: use a saída do motor.
- Código em `fxengine/`, testes em `tests/` (`python3 -m pytest -q`; usam dados sintéticos,
  sem rede). Modo demonstração sem rede: `python3 -m fxengine --offline`.
- Textos para o usuário em português; código e comentários em inglês.
- `android/`: app Android (Kotlin + Compose + Chaquopy) que embute o motor; ele chama
  `fxengine/app_api.py`. Mudou a saída do motor? Mantenha `app_api.result_dict` e
  `android/.../data/Models.kt` em sincronia. Build: `cd android && ./gradlew assembleRelease`.
- `analysis/` contém análises manuais antigas (anteriores ao motor).
