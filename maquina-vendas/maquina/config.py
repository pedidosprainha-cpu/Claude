"""Configuração da máquina.

Tudo que mexe com dinheiro tem um limite aqui. Os valores vêm de variáveis de
ambiente (arquivo .env no servidor) para que ninguém consiga aumentá-los pelo
app: o TETO_ABSOLUTO só muda editando a configuração do servidor.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _ler_env(arquivo):
    """Carrega o arquivo .env (sem sobrescrever variáveis já definidas no sistema)."""
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_ler_env(RAIZ / ".env")

WEB = RAIZ / "web"
DADOS = Path(os.getenv("MAQUINA_DADOS", str(RAIZ / "dados")))

# "simulacao": nada de dinheiro real, anúncios e vendas simulados.
# "real": conecta nas contas de verdade (liberado na etapa 2).
MODO = os.getenv("MAQUINA_MODO", "simulacao").strip().lower()

# --- Travas de gasto -------------------------------------------------------
# Teto diário inicial (pode ser reduzido pelo app; aumentado só com aprovação).
TETO_INICIAL = float(os.getenv("TETO_DIARIO_BRL", "30"))
# Teto que nem uma aprovação pelo app consegue ultrapassar.
TETO_ABSOLUTO = float(os.getenv("TETO_ABSOLUTO_BRL", "100"))
if TETO_INICIAL > TETO_ABSOLUTO:
    raise SystemExit("TETO_DIARIO_BRL não pode ser maior que TETO_ABSOLUTO_BRL")

ORCAMENTO_MINIMO = 5.0      # menor orçamento diário que o Meta aceita (aprox.)
ORCAMENTO_TESTE = 10.0      # orçamento de cada campanha nova em teste

# --- Regras do otimizador --------------------------------------------------
FATOR_CORTE_SEM_VENDA = 1.0     # pausa ao gastar 1x a comissão sem nenhuma venda...
DIAS_TETO_CORTE_SEM_VENDA = 3   # ...ou 3 dias de teto, o que vier primeiro
IMPRESSOES_MIN_CTR = 1500       # só julga o CTR depois de tantas impressões
CTR_MINIMO = 0.007              # 0,7%
ROAS_CORTE = 0.8                # pausa se devolver menos de R$0,80 por R$1 gasto...
GASTO_MIN_CORTE_ROAS = 1.5      # ...depois de gastar 1,5x a comissão
ROAS_ESCALA = 1.5               # aumenta a verba se devolver R$1,50 por R$1 gasto...
VENDAS_MIN_ESCALA = 2           # ...com pelo menos 2 vendas na janela
PASSO_ESCALA = 0.20             # +20% por vez
HORAS_ENTRE_ESCALAS = 24
JANELA_DIAS = 3                 # janela das decisões de ROAS para campanhas mais velhas

# --- Produtos e criativos --------------------------------------------------
COMISSAO_MINIMA = 30.0          # abaixo disso tráfego pago quase nunca se paga
PONTUACAO_MINIMA = 40.0
MAX_PRODUTOS_EM_TESTE = 2
CRIATIVOS_POR_RODADA = 3
MAX_CRIATIVOS_POR_PRODUTO = 6   # depois disso sem lucro, o produto é reprovado
GASTO_MIN_REPROVAR = 2.5        # reprova o produto ao gastar 2,5x a comissão (ou 7 dias
DIAS_TETO_REPROVAR = 7          # de teto, o que vier primeiro)...
ROAS_REPROVAR = 0.8             # ...com ROAS somado abaixo disso
LIMITE_CRIATIVOS_PENDENTES = 6

# --- Leads -----------------------------------------------------------------
LEAD_MORNO = 30
LEAD_QUENTE = 60

# --- IA para criativos -----------------------------------------------------
# "auto": usa a API da Anthropic se houver chave; senão, usa modelos prontos.
IA_CRIATIVOS = os.getenv("IA_CRIATIVOS", "auto").strip().lower()
MODELO_IA = os.getenv("MODELO_IA", "claude-opus-5-5")

# --- Painel e notificações -------------------------------------------------
PAINEL_TOKEN = os.getenv("PAINEL_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# --- Webhooks das plataformas de afiliado ----------------------------------
HOTMART_HOTTOK = os.getenv("HOTMART_HOTTOK", "").strip()
KIWIFY_TOKEN = os.getenv("KIWIFY_TOKEN", "").strip()
EDUZZ_TOKEN = os.getenv("EDUZZ_TOKEN", "").strip()

# --- Simulação -------------------------------------------------------------
SIM_AUTO = os.getenv("SIM_AUTO", "1") == "1"
SIM_SEGUNDOS_POR_HORA = float(os.getenv("SIM_SEGUNDOS_POR_HORA", "5"))
SIM_SEMENTE = os.getenv("SIM_SEMENTE")

AUTONOMIAS = ("limites", "total", "manual")
