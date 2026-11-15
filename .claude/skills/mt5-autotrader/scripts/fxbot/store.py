"""Files the bot keeps between runs: state, heartbeat, journals, logs."""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .risk import new_state
from .timeutil import iso, utcnow


def _atomic_write(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)


class Store:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.journal_dir = self.home / "journal"
        self.log_dir = self.home / "logs"
        for d in (self.home, self.journal_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.state_path = self.home / "state.json"
        self.heartbeat_path = self.home / "heartbeat.json"
        self.stop_path = self.home / "STOP"
        self.pid_path = self.home / "bot.pid"
        self.news_path = self.home / "news_cache.json"
        self.commands_path = self.home / "commands.jsonl"
        self.desired_path = self.home / "desired"

    # ---------------------------------------------------------------- state
    def load_state(self) -> dict:
        state = {}
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError):
                # A corrupt state file must not stop trading safety: keep a copy, start clean.
                self.state_path.replace(self.state_path.with_suffix(".corrupt"))
                state = {}
        state.setdefault("risk", new_state())
        state.setdefault("positions", {})       # ticket -> metadata recorded at entry
        state.setdefault("last_bar", {})        # symbol -> time of the last processed closed bar
        state.setdefault("pending_closed", {})  # tickets that vanished, waiting for their deals
        state.setdefault("last_scan", None)
        return state

    def save_state(self, state: dict) -> None:
        _atomic_write(self.state_path, state)

    # -------------------------------------------------------------- desired
    # What the operator wants (running | stopped). Kept in its own file because the
    # running bot owns state.json and would overwrite anything the CLI wrote there.
    def desired(self) -> str:
        try:
            return self.desired_path.read_text(encoding="utf-8").strip() or "stopped"
        except OSError:
            return "stopped"

    def set_desired(self, value: str) -> None:
        self.desired_path.write_text(value, encoding="utf-8")

    # ------------------------------------------------------------ heartbeat
    def write_heartbeat(self, data: dict) -> None:
        data = dict(data, ts=utcnow().timestamp(), time=iso(), pid=os.getpid())
        _atomic_write(self.heartbeat_path, data)

    def read_heartbeat(self) -> dict | None:
        try:
            with open(self.heartbeat_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    # -------------------------------------------------------------- journal
    def append(self, name: str, record: dict) -> None:
        """Append one JSON line. `decisions` rotates monthly; `trades` is a single file."""
        fname = f"{name}-{utcnow():%Y-%m}.jsonl" if name == "decisions" else f"{name}.jsonl"
        with open(self.journal_dir / fname, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(record, logged_at=iso()), default=str) + "\n")

    def read(self, name: str, limit: int | None = None) -> list[dict]:
        files = sorted(self.journal_dir.glob(f"{name}*.jsonl"))
        out: list[dict] = []
        for p in files:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return out[-limit:] if limit else out

    # ------------------------------------------------------------- commands
    def push_command(self, cmd: dict) -> None:
        """Operator instruction for the running bot (pause, veto, close ...)."""
        with open(self.commands_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(cmd) + "\n")

    def pop_commands(self) -> list[dict]:
        if not self.commands_path.exists():
            return []
        taken = self.commands_path.with_suffix(".taken")
        try:
            os.replace(self.commands_path, taken)
            with open(taken, "r", encoding="utf-8") as f:
                cmds = [json.loads(line) for line in f if line.strip()]
            taken.unlink()
            return cmds
        except (OSError, json.JSONDecodeError):
            return []

    def bot_alive(self, max_age: float = 120.0) -> bool:
        hb = self.read_heartbeat()
        return bool(hb and hb.get("status") != "stopped" and utcnow().timestamp() - float(hb.get("ts", 0)) < max_age)

    # ----------------------------------------------------------------- misc
    def logger(self, console: bool = False) -> logging.Logger:
        log = logging.getLogger("fxbot")
        if not log.handlers:
            log.setLevel(logging.INFO)
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            fh = RotatingFileHandler(self.log_dir / "fxbot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
            if console:
                sh = logging.StreamHandler()
                sh.setFormatter(fmt)
                log.addHandler(sh)
        return log

    def stop_requested(self) -> bool:
        return self.stop_path.exists()
