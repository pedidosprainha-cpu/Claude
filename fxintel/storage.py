"""Persistência em SQLite (WAL): análises, sinais, eventos do motor, alertas, posições demo e chaves."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, symbol TEXT,
  direction TEXT, score REAL, elapsed_ms REAL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_analyses_created ON analyses(created_at);
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY, analysis_id TEXT, created_at TEXT NOT NULL, symbol TEXT NOT NULL,
  direction TEXT NOT NULL, entry REAL, sl REAL, tp1 REAL, tp2 REAL, valid_until TEXT,
  status TEXT NOT NULL, outcome_r REAL, closed_at TEXT, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_signals_created ON signals(created_at);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, level TEXT, kind TEXT, message TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT, severity TEXT, symbol TEXT,
  message TEXT, data TEXT, dedup TEXT UNIQUE);
CREATE INDEX IF NOT EXISTS ix_alerts_ts ON alerts(ts);
CREATE TABLE IF NOT EXISTS paper_positions (
  id TEXT PRIMARY KEY, signal_id TEXT, symbol TEXT, direction INTEGER, units REAL, entry REAL,
  sl REAL, tp1 REAL, tp2 REAL, opened_at TEXT, status TEXT, remaining REAL, realized REAL,
  risk_amount REAL, closed_at TEXT, r REAL, log TEXT);
CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, key_hash TEXT UNIQUE, created_at TEXT,
  last_used TEXT, revoked INTEGER DEFAULT 0);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Storage:
    def __init__(self, path: Path | None = None):
        ensure_dirs()
        self.path = Path(path or DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @contextmanager
    def tx(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def q(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    # ---------------------------------------------------------------- análises
    def save_analysis(self, res: dict) -> None:
        best = res.get("signal") or {}
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO analyses VALUES (?,?,?,?,?,?,?,?)",
                      (res["id"], res["created_at"], res["status"], best.get("instrument"),
                       best.get("direction"), best.get("score"), res.get("elapsed_ms"),
                       json.dumps(res, ensure_ascii=False, default=str)))

    def analyses(self, limit: int = 50) -> list[dict]:
        rows = self.q("SELECT id, created_at, status, symbol, direction, score, elapsed_ms FROM analyses "
                      "ORDER BY created_at DESC LIMIT ?", (limit,))
        return rows

    def analysis(self, aid: str) -> dict | None:
        r = self.q("SELECT payload FROM analyses WHERE id=?", (aid,))
        return json.loads(r[0]["payload"]) if r else None

    def latest_analysis(self) -> dict | None:
        r = self.q("SELECT payload FROM analyses ORDER BY created_at DESC LIMIT 1")
        return json.loads(r[0]["payload"]) if r else None

    # ---------------------------------------------------------------- sinais
    def save_signal(self, sig: dict, analysis_id: str) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sig["id"], analysis_id, sig["created_at"], sig["instrument"], sig["direction"],
                       sig["entry"]["price"], sig["stop_loss"]["price"], sig["take_profit"][0]["price"],
                       sig["take_profit"][1]["price"] if len(sig["take_profit"]) > 1 else None,
                       sig["validity"]["valid_until"], "ativo", None, None,
                       json.dumps(sig, ensure_ascii=False, default=str)))

    def signals(self, limit: int = 100, status: str | None = None) -> list[dict]:
        sql = ("SELECT id, analysis_id, created_at, symbol, direction, entry, sl, tp1, tp2, valid_until, "
               "status, outcome_r, closed_at FROM signals")
        args: tuple = ()
        if status:
            sql += " WHERE status=?"
            args = (status,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        return self.q(sql, args + (limit,))

    def signal(self, sid: str) -> dict | None:
        r = self.q("SELECT * FROM signals WHERE id=?", (sid,))
        if not r:
            return None
        d = r[0]
        d["payload"] = json.loads(d["payload"])
        return d

    def update_signal(self, sid: str, status: str, outcome_r: float | None = None) -> None:
        with self.tx() as c:
            c.execute("UPDATE signals SET status=?, outcome_r=?, closed_at=? WHERE id=?",
                      (status, outcome_r, now_iso() if status != "ativo" else None, sid))

    def signal_stats(self) -> dict:
        rows = self.q("SELECT status, outcome_r FROM signals")
        closed = [r for r in rows if r["outcome_r"] is not None]
        rs = [r["outcome_r"] for r in closed]
        return {"total": len(rows), "active": sum(r["status"] == "ativo" for r in rows),
                "closed": len(closed), "avg_r": (sum(rs) / len(rs)) if rs else None,
                "wins": sum(1 for x in rs if x > 0), "losses": sum(1 for x in rs if x < 0)}

    # ---------------------------------------------------------------- eventos/alertas
    def log_event(self, kind: str, message: str, level: str = "INFO", data: dict | None = None) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO events (ts, level, kind, message, data) VALUES (?,?,?,?,?)",
                      (now_iso(), level, kind, message, json.dumps(data or {}, ensure_ascii=False, default=str)))

    def events(self, limit: int = 100) -> list[dict]:
        return self.q("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

    def add_alert(self, kind: str, severity: str, message: str, symbol: str | None = None,
                  data: dict | None = None, dedup: str | None = None) -> bool:
        try:
            with self.tx() as c:
                c.execute("INSERT INTO alerts (ts, kind, severity, symbol, message, data, dedup) VALUES (?,?,?,?,?,?,?)",
                          (now_iso(), kind, severity, symbol, message,
                           json.dumps(data or {}, ensure_ascii=False, default=str), dedup))
            return True
        except sqlite3.IntegrityError:
            return False  # alerta duplicado

    def alerts(self, since_id: int = 0, limit: int = 100) -> list[dict]:
        rows = self.q("SELECT * FROM alerts WHERE id > ? ORDER BY id DESC LIMIT ?", (since_id, limit))
        for r in rows:
            r["data"] = json.loads(r["data"] or "{}")
        return rows

    # ---------------------------------------------------------------- chaves de API
    def create_api_key(self, name: str) -> str:
        key = "fxi_" + secrets.token_urlsafe(32)
        with self.tx() as c:
            c.execute("INSERT INTO api_keys (name, key_hash, created_at) VALUES (?,?,?)",
                      (name, hash_key(key), now_iso()))
        return key

    def check_api_key(self, key: str) -> bool:
        if not key:
            return False
        h = hash_key(key)
        r = self.q("SELECT id FROM api_keys WHERE key_hash=? AND revoked=0", (h,))
        if not r:
            return False
        with self.tx() as c:
            c.execute("UPDATE api_keys SET last_used=? WHERE id=?", (now_iso(), r[0]["id"]))
        return True

    def has_api_keys(self) -> bool:
        return bool(self.q("SELECT 1 FROM api_keys WHERE revoked=0 LIMIT 1"))

    def list_api_keys(self) -> list[dict]:
        return self.q("SELECT id, name, created_at, last_used, revoked FROM api_keys")

    def revoke_api_key(self, kid: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
