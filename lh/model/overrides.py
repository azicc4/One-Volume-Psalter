"""Reviewed corrections to the database: data/overrides/*.yaml (format: docs/overrides.md).

Applied at the end of `lh build`, after canonicalisation. Every applied entry is logged in `override_log`, and the
round-trip check skips (and reports) occurrences of overridden objects — they differ from the PDF on purpose.

Actions
  replace   substring replacement inside an object's payload text   {object, find, replace}
  merge     occurrences of object `object` are re-pointed to `into`  {object, into}
  note      decision recorded, no data change ("no change" resolutions, e.g. Felix Just's own typo)
"""
from __future__ import annotations

import json
import sqlite3

import yaml

from lh.config import OVERRIDES

REQUIRED = {"id", "action", "reason", "evidence"}


def load() -> list[dict]:
    entries = []
    for f in sorted(OVERRIDES.glob("*.yaml")):
        for e in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            missing = REQUIRED - set(e)
            if missing:
                raise ValueError(f"{f.name}: override {e.get('id', '?')} lacks {sorted(missing)}")
            e["_file"] = f.name
            entries.append(e)
    return entries


def _replace_in(obj, find: str, repl: str):
    if isinstance(obj, str):
        return obj.replace(find, repl), obj.count(find)
    if isinstance(obj, list):
        n, out = 0, []
        for x in obj:
            y, k = _replace_in(x, find, repl)
            out.append(y)
            n += k
        return out, n
    if isinstance(obj, dict):
        n, out = 0, {}
        for key, x in obj.items():
            y, k = _replace_in(x, find, repl)
            out[key] = y
            n += k
        return out, n
    return obj, 0


def apply(con: sqlite3.Connection) -> int:
    con.execute("""CREATE TABLE IF NOT EXISTS override_log (id TEXT, action TEXT, object_id TEXT, detail TEXT,
                   reason TEXT, evidence TEXT, file TEXT)""")
    applied = 0
    for e in load():
        act, oid = e["action"], e.get("object")
        detail = ""
        if act == "replace":
            row = con.execute("SELECT payload FROM object WHERE id=?", (oid,)).fetchone()
            if not row:
                raise ValueError(f"override {e['id']}: no object {oid}")
            payload, n = _replace_in(json.loads(row[0]), e["find"], e["replace"])
            if n == 0:
                raise ValueError(f"override {e['id']}: text {e['find']!r} not found in {oid}")
            con.execute("UPDATE object SET payload=?, status='overridden' WHERE id=?", (json.dumps(payload, ensure_ascii=False), oid))
            detail = f"{n} replacement(s)"
        elif act == "merge":
            into = e["into"]
            if not con.execute("SELECT 1 FROM object WHERE id=?", (into,)).fetchone():
                raise ValueError(f"override {e['id']}: no target object {into}")
            n = con.execute("UPDATE occurrence SET object_id=? WHERE object_id=?", (into, oid)).rowcount
            con.execute("UPDATE object SET n_occ = n_occ + ? WHERE id=?", (n, into))
            con.execute("DELETE FROM object WHERE id=?", (oid,))
            con.execute("DELETE FROM object_fts WHERE id=?", (oid,))
            con.execute("UPDATE object SET status='overridden' WHERE id=?", (into,))
            detail = f"{n} occurrence(s) → {into}"
        elif act != "note":
            raise ValueError(f"override {e['id']}: unknown action {act!r}")
        con.execute("INSERT INTO override_log VALUES (?,?,?,?,?,?,?)",
                    (e["id"], act, oid, detail, e["reason"], e["evidence"], e["_file"]))
        applied += 1
    return applied
