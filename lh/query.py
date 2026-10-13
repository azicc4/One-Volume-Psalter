"""CLI search and inspection over build/lh.sqlite (`python -m lh find|show|hour`)."""
from __future__ import annotations

import json
import sqlite3

from lh.config import DB_PATH
from lh.model.canon import plain, restore
from lh.model.days import HOUR_NAMES


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def find(args):
    con = _con()
    q = " ".join(args.query)
    sql = """SELECT o.id, o.type, o.n_occ, substr(o.plain, 1, 100) AS txt FROM object_fts f JOIN object o ON o.id = f.id
             WHERE object_fts MATCH ?""" + (" AND o.type = ?" if args.type else "") + " ORDER BY o.n_occ DESC LIMIT 40"
    rows = con.execute(sql, (q, args.type) if args.type else (q,)).fetchall()
    for r in rows:
        print(f"{r['id']:48s} {r['type']:12s} x{r['n_occ']:<4d} {r['txt']}")
    if not rows:
        print("no matches")


def show(args):
    con = _con()
    ob = con.execute("SELECT * FROM object WHERE id = ?", (args.id,)).fetchone()
    if not ob:
        print("no such object")
        return
    print(f"{ob['id']}  [{ob['type']}]  printed {ob['n_occ']} times  status={ob['status']}")
    print(f"  {ob['plain'][:600]}")
    print("  printed at:")
    for r in con.execute("""SELECT h.day_key, h.hour, o.slot, o.sub, h.source, o.page FROM occurrence o
                            JOIN hour_instance h ON h.id = o.hour_id WHERE o.object_id = ? ORDER BY h.id, o.seq""", (args.id,)):
        sub = f"/{r['sub']}" if r["sub"] else ""
        print(f"    {r['day_key']:14s} {HOUR_NAMES.get(r['hour'], r['hour']):26s} {r['slot']}{sub:8s} {r['source']} p.{r['page']}")


def hour(args):
    con = _con()
    h = con.execute("SELECT * FROM hour_instance WHERE day_key = ? AND hour = ? LIMIT 1",
                    (args.day, args.hour.upper())).fetchone()
    if not h:
        print("no such hour")
        return
    print(f"== {h['day_key']} {HOUR_NAMES.get(h['hour'], h['hour'])}  ({h['source']} pp. {h['page_start']}-{h['page_end']})")
    for r in con.execute("""SELECT o.slot, o.sub, o.type, o.object_id, o.extra, ob.type AS otype, ob.payload FROM occurrence o
                            LEFT JOIN object ob ON ob.id = o.object_id WHERE o.hour_id = ? ORDER BY o.seq""", (h["id"],)):
        if r["type"] == "marker":
            continue
        if r["type"] == "label":
            print(f"  [{json.loads(r['extra'] or '{}').get('text', r['slot'])}]")
            continue
        txt = plain(restore(r["otype"], json.loads(r["payload"]), json.loads(r["extra"] or "{}")))
        sub = f"/{r['sub']}" if r["sub"] else ""
        print(f"  {r['slot'] + sub:16s} {txt[:110]}{'…' if len(txt) > 110 else ''}   <{r['object_id']}>")
