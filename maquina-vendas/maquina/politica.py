"""Pente-fino de política de anúncios do Meta, antes de qualquer publicação.

Conta de anúncio bloqueada acaba com o negócio, então a máquina barra o que
costuma ser reprovado: afirmar características pessoais de quem lê, prometer
resultado, dinheiro fácil, cura, "antes e depois" etc. Não substitui a revisão
do Meta, mas evita os erros mais comuns.
"""
import re

BLOQUEIA = "bloqueia"
ATENCAO = "atencao"

_REGRAS = [
    (r"\b(voc[eê]|vc)\s+(est[aá]|[eé])\s+(gord|acima do peso|obes|endividad|deprimid|ansios|careca|pobre|quebrad|solteir)",
     BLOQUEIA, "Afirma uma característica pessoal de quem lê (proibido pelo Meta)"),
    (r"\b(voc[eê]|vc)\s+(tem|sofre de|sofre com)\s+(diabetes|ansiedade|depress|d[ií]vidas?|c[aâ]ncer|calv[ií]cie|disfun)",
     BLOQUEIA, "Afirma uma condição pessoal de quem lê (proibido pelo Meta)"),
    (r"\b(resultados?|lucros?|renda|ganhos?)\s+garantid|\bgarant(o|imos)\s+(que|o\s+resultado|resultado|lucro)",
     BLOQUEIA, "Promete resultado garantido"),
    (r"\b(fique|ficar|ficará)\s+rico|\bdinheiro\s+f[aá]cil|\bsem\s+esfor[cç]o|\bganhe\s+r\$\s?\d|\brenda\s+de\s+r\$\s?\d",
     BLOQUEIA, "Promete dinheiro fácil ou um ganho específico"),
    (r"\bcura(r|do|da)?\b", BLOQUEIA, "Alegação de cura"),
    (r"\bantes\s+e\s+depois\b", BLOQUEIA, "\"Antes e depois\" costuma ser reprovado"),
    (r"\bperca\s+\d+\s*(kg|quilos)", BLOQUEIA, "Promete perda de peso específica"),
    (r"\bclique\s+aqui\b|\bcurta\s+e\s+compartilhe\b|\bmarque\s+um\s+amigo\b",
     ATENCAO, "Isca de engajamento: o Meta entrega menos"),
    (r"!{2,}|\?{2,}", ATENCAO, "Pontuação exagerada"),
    (r"\b[uú]ltimas?\s+(vagas|unidades)|\bs[oó]\s+hoje\b", ATENCAO, "Escassez: só use se for verdade"),
    (r"\b100\s*%", ATENCAO, "Absolutos como \"100%\" costumam ser barrados"),
]


def checar(titulo="", texto="", descricao=""):
    avisos = []
    completo = " ".join(t for t in (titulo, texto, descricao) if t)
    for padrao, gravidade, motivo in _REGRAS:
        achado = re.search(padrao, completo, re.IGNORECASE)
        if achado:
            avisos.append({"gravidade": gravidade, "motivo": motivo, "trecho": achado.group(0)})
    letras = [c for c in completo if c.isalpha()]
    if len(letras) > 20 and sum(c.isupper() for c in letras) / len(letras) > 0.5:
        avisos.append({"gravidade": ATENCAO, "motivo": "Texto em CAIXA ALTA", "trecho": ""})
    if len(titulo) > 40:
        avisos.append({"gravidade": ATENCAO, "motivo": "Título longo: corta na tela do celular", "trecho": ""})
    if len(texto) > 180:
        avisos.append({"gravidade": ATENCAO, "motivo": "Texto longo: só o começo aparece", "trecho": ""})
    return avisos


def bloqueia(avisos):
    return any(a["gravidade"] == BLOQUEIA for a in avisos)
