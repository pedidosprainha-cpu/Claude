"""Política monetária: taxas básicas, diferencial de juros (carry) e viés dos bancos centrais."""
from __future__ import annotations

import json
from datetime import date

from ..config import CONFIG_DIR


def load_table() -> dict:
    p = CONFIG_DIR / "central_banks.json"
    if not p.exists():
        return {"as_of": None, "banks": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def staleness_days(table: dict, today: date | None = None) -> int | None:
    if not table.get("as_of"):
        return None
    today = today or date.today()
    return (today - date.fromisoformat(table["as_of"])).days


def carry(base: str, quote: str, table: dict) -> dict | None:
    """Diferencial de taxa básica base−quote (p.p.) e de viés (stance)."""
    b = table.get("banks", {})
    if base not in b or quote not in b:
        return None
    diff = b[base]["rate"] - b[quote]["rate"]
    stance = b[base].get("stance", 0) - b[quote].get("stance", 0)
    return {
        "rate_base": b[base]["rate"], "rate_quote": b[quote]["rate"], "diff_pp": round(diff, 3),
        "stance_diff": stance, "bank_base": b[base]["bank"], "bank_quote": b[quote]["bank"],
        "next_meetings": {base: b[base].get("next_meeting"), quote: b[quote].get("next_meeting")},
    }
