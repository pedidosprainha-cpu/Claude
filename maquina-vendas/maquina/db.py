"""Banco de dados SQLite (um arquivo só, sem servidor de banco)."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from . import config

_lock = threading.RLock()
_conn = None
_caminho = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS produtos (
  id INTEGER PRIMARY KEY,
  plataforma TEXT NOT NULL,
  id_externo TEXT,
  nome TEXT NOT NULL,
  nicho TEXT,
  preco REAL NOT NULL,
  comissao_pct REAL NOT NULL,
  link_afiliado TEXT NOT NULL,
  pagina_vendas TEXT,
  beneficio TEXT,
  publico TEXT,
  temperatura REAL DEFAULT 0,
  reembolso_pct REAL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'candidato',
  pontuacao REAL DEFAULT 0,
  sim_conv REAL,
  criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS criativos (
  id INTEGER PRIMARY KEY,
  produto_id INTEGER NOT NULL REFERENCES produtos(id),
  angulo TEXT,
  titulo TEXT NOT NULL,
  texto TEXT NOT NULL,
  descricao TEXT,
  cta TEXT NOT NULL,
  origem TEXT NOT NULL,
  avisos TEXT DEFAULT '[]',
  status TEXT NOT NULL,
  sim_ctr REAL,
  criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campanhas (
  id INTEGER PRIMARY KEY,
  produto_id INTEGER NOT NULL REFERENCES produtos(id),
  criativo_id INTEGER NOT NULL REFERENCES criativos(id),
  id_externo TEXT,
  status TEXT NOT NULL,
  orcamento_diario REAL NOT NULL,
  motivo TEXT,
  criada_em TEXT NOT NULL,
  ultima_escala_em TEXT,
  atualizada_em TEXT
);

CREATE TABLE IF NOT EXISTS metricas (
  campanha_id INTEGER NOT NULL REFERENCES campanhas(id),
  dia TEXT NOT NULL,
  impressoes INTEGER DEFAULT 0,
  cliques INTEGER DEFAULT 0,
  visitas INTEGER DEFAULT 0,
  gasto REAL DEFAULT 0,
  PRIMARY KEY (campanha_id, dia)
);

CREATE TABLE IF NOT EXISTS vendas (
  id INTEGER PRIMARY KEY,
  plataforma TEXT NOT NULL,
  transacao TEXT NOT NULL,
  produto_id INTEGER,
  campanha_id INTEGER,
  valor REAL DEFAULT 0,
  comissao REAL DEFAULT 0,
  status TEXT NOT NULL,
  comprador_hash TEXT,
  dia TEXT NOT NULL,
  recebida_em TEXT NOT NULL,
  atualizada_em TEXT NOT NULL,
  UNIQUE (plataforma, transacao)
);

CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY,
  visitante TEXT NOT NULL UNIQUE,
  campanha_id INTEGER,
  produto_id INTEGER,
  nome TEXT,
  email TEXT,
  whatsapp TEXT,
  email_hash TEXT,
  consentimento_em TEXT,
  pontuacao INTEGER DEFAULT 0,
  temperatura TEXT DEFAULT 'frio',
  eventos TEXT DEFAULT '{}',
  cliente INTEGER DEFAULT 0,
  criado_em TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS leads_email ON leads(email_hash);

CREATE TABLE IF NOT EXISTS alertas (
  id INTEGER PRIMARY KEY,
  nivel TEXT NOT NULL,
  titulo TEXT NOT NULL,
  mensagem TEXT,
  criado_em TEXT NOT NULL,
  lido INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS aprovacoes (
  id INTEGER PRIMARY KEY,
  tipo TEXT NOT NULL,
  ref_id INTEGER,
  titulo TEXT NOT NULL,
  detalhe TEXT DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pendente',
  criado_em TEXT NOT NULL,
  decidido_em TEXT
);

CREATE TABLE IF NOT EXISTS diario (
  id INTEGER PRIMARY KEY,
  quando TEXT NOT NULL,
  acao TEXT NOT NULL,
  detalhe TEXT
);
"""


def usar(caminho):
    """Troca o arquivo do banco (usado pelos testes)."""
    global _conn, _caminho
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _caminho = caminho


def conn():
    global _conn
    with _lock:
        if _conn is None:
            caminho = _caminho or str(config.DADOS / "maquina.db")
            if caminho != ":memory:":
                Path(caminho).parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(caminho, check_same_thread=False, isolation_level=None)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            if caminho != ":memory:":
                c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            _conn = c
            _padroes()
        return _conn


@contextmanager
def transacao():
    """Agrupa várias operações: ou todas acontecem, ou nenhuma."""
    with _lock:
        c = conn()
        if c.in_transaction:
            yield c
            return
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        else:
            c.execute("COMMIT")


def todos(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def um(sql, args=()):
    with _lock:
        r = conn().execute(sql, args).fetchone()
        return dict(r) if r else None


def valor(sql, args=(), padrao=0):
    with _lock:
        r = conn().execute(sql, args).fetchone()
        return padrao if r is None or r[0] is None else r[0]


def executar(sql, args=()):
    with _lock:
        return conn().execute(sql, args).lastrowid


# --- Configurações ajustáveis pelo app --------------------------------------

def cfg(chave, padrao=None):
    r = um("SELECT valor FROM config WHERE chave = ?", (chave,))
    return json.loads(r["valor"]) if r else padrao


def cfg_definir(chave, val):
    executar(
        "INSERT INTO config (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, json.dumps(val)),
    )


def _padroes():
    padroes = {
        "teto_diario": config.TETO_INICIAL,
        "autonomia": "limites",
        "pausado": False,
        "sim_horas": 0,
        "sim_auto": config.SIM_AUTO,
        "notificar_vendas": True,
    }
    for chave, val in padroes.items():
        if cfg(chave) is None:
            cfg_definir(chave, val)
