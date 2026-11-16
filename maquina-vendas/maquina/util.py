def brl(valor):
    """1234.5 -> 'R$ 1.234,50'"""
    sinal = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def pct(valor, casas=1):
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


def num(valor, casas=2):
    """5.374 -> '5,37'"""
    return f"{valor:.{casas}f}".replace(".", ",")
