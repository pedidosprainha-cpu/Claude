"""Diário de bordo, alertas, pedidos de aprovação e notificação no celular.

A regra é incomodar você o mínimo possível: só vai para o celular o que é
urgente, o que precisa da sua decisão e (se quiser) as vendas.
"""
import json
import threading
import urllib.request

from . import config, db, relogio


def diario(acao, detalhe=""):
    """Registra tudo o que a máquina faz, para você poder auditar depois."""
    db.executar(
        "INSERT INTO diario (quando, acao, detalhe) VALUES (?, ?, ?)",
        (relogio.agora_iso(), acao, detalhe),
    )


def alerta(nivel, titulo, mensagem="", celular=None):
    """nivel: info | bom | atencao | urgente"""
    db.executar(
        "INSERT INTO alertas (nivel, titulo, mensagem, criado_em) VALUES (?, ?, ?, ?)",
        (nivel, titulo, mensagem, relogio.agora_iso()),
    )
    if celular is None:
        celular = nivel == "urgente"
    if celular:
        enviar_celular(f"{titulo}\n{mensagem}".strip())


def enviar_celular(texto):
    """Manda mensagem pelo Telegram, se estiver configurado. Nunca trava a máquina."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return

    def _enviar():
        try:
            corpo = json.dumps({"chat_id": config.TELEGRAM_CHAT_ID, "text": texto[:4000]}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                data=corpo,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10).close()
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()


def pedir_aprovacao(tipo, ref_id, titulo, detalhe=None, notificar=True):
    """Cria um pedido de aprovação (sem duplicar um que já esteja aberto)."""
    existente = db.um(
        "SELECT id FROM aprovacoes WHERE tipo = ? AND ref_id IS ? AND status = 'pendente'",
        (tipo, ref_id),
    )
    if existente:
        return existente["id"]
    aid = db.executar(
        "INSERT INTO aprovacoes (tipo, ref_id, titulo, detalhe, criado_em) VALUES (?, ?, ?, ?, ?)",
        (tipo, ref_id, titulo, json.dumps(detalhe or {}, ensure_ascii=False), relogio.agora_iso()),
    )
    if notificar:
        enviar_celular(f"Preciso da sua decisão: {titulo}\nAbra o app na aba Aprovar.")
    return aid


def tem_pendente(tipo, ref_id=None):
    if ref_id is None:
        sql, args = "SELECT 1 FROM aprovacoes WHERE tipo = ? AND status = 'pendente'", (tipo,)
    else:
        sql, args = (
            "SELECT 1 FROM aprovacoes WHERE tipo = ? AND ref_id = ? AND status = 'pendente'",
            (tipo, ref_id),
        )
    return db.um(sql, args) is not None


def cancelar_pendentes(tipo, ref_id):
    db.executar(
        "UPDATE aprovacoes SET status = 'cancelada', decidido_em = ? "
        "WHERE tipo = ? AND ref_id = ? AND status = 'pendente'",
        (relogio.agora_iso(), tipo, ref_id),
    )
