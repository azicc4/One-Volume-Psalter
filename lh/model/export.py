"""Diffable text snapshot of the database in data/export/ (committed; build/lh.sqlite is not).

  objects.jsonl   one canonical object per line, sorted by id: {"id","type","n","payload"}
  hours.jsonl     one printed hour per line, as a recipe of slots → object ids, with source pages
  psalter.jsonl   one psalm per line: verses with source (LH / NV / NVT) and consensus counts
"""
from __future__ import annotations

import json
import sqlite3

from lh.config import DB_PATH, EXPORT


def export(db=DB_PATH) -> dict:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    EXPORT.mkdir(parents=True, exist_ok=True)
    counts = {}
    with open(EXPORT / "objects.jsonl", "w", encoding="utf-8", newline="\n") as f:
        n = 0
        for r in con.execute("SELECT id, type, n_occ, payload FROM object ORDER BY id"):
            f.write(json.dumps({"id": r["id"], "type": r["type"], "n": r["n_occ"], "payload": json.loads(r["payload"])},
                               ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
        counts["objects"] = n
    with open(EXPORT / "hours.jsonl", "w", encoding="utf-8", newline="\n") as f:
        n = 0
        for h in con.execute("SELECT * FROM hour_instance ORDER BY source, page_start, id"):
            slots = [[o["slot"], o["sub"] or "", json.loads(o["cond"]) if o["cond"] else None, o["object_id"], o["page"]]
                     for o in con.execute("SELECT slot, sub, cond, object_id, page FROM occurrence WHERE hour_id=? AND object_id IS NOT NULL ORDER BY seq", (h["id"],))]
            f.write(json.dumps({"source": h["source"], "day": h["day_key"], "hour": h["hour"], "copy": h["copy"],
                                "pages": [h["page_start"], h["page_end"]], "slots": slots}, ensure_ascii=False) + "\n")
            n += 1
        counts["hours"] = n
    with open(EXPORT / "psalter.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in con.execute("SELECT * FROM psalm ORDER BY num"):
            verses = [[r["verse"], r["line"], r["x"], r["text"], r["source"], r["n_copies"], r["n_agree"]]
                      for r in con.execute("SELECT * FROM psalm_verse WHERE psalm=? ORDER BY seq", (p["num"],))]
            f.write(json.dumps({"psalm": p["num"], "vulgate": p["vulgate"], "verses": verses}, ensure_ascii=False) + "\n")
        counts["psalms"] = con.execute("SELECT count(*) FROM psalm").fetchone()[0]
    con.close()
    return counts
