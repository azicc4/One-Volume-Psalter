"""Build build/lh.sqlite from parsed sources: days, hour instances, objects, occurrences, psalm uses."""
from __future__ import annotations

import hashlib
import re
import json
import sqlite3
import time
from pathlib import Path

from lh.config import DB_PATH
from lh.extract.spans import open_l1
from lh.model.canon import canon, incipit, object_id, plain_text, psalm_base, unit_verses
from lh.model.days import day_info, hour_code
from lh.parse.run import parse_pdf

SCHEMA = Path(__file__).with_name("schema.sql")
REF_TYPES = {"lectio_brevis", "responsory", "resp_breve"}


def build(sources: list[str], db_path: Path = DB_PATH) -> None:
    t0 = time.time()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    objects: dict[str, dict] = {}       # identity key -> {id, type, payload, n}
    ids: dict[str, str] = {}            # object id -> identity key (collision guard)
    days: dict[str, dict] = {}
    for spec in sources:
        src, _, rng = spec.partition(":")          # "ADV:4-1198" = only those pages (one Advent start-date copy)
        p0, p1 = (int(x) for x in rng.split("-")) if rng else (None, None)
        seen_hours: dict = {}
        l1 = open_l1(src)
        meta = dict(l1.execute("SELECT key, value FROM meta").fetchall())
        l1.close()
        con.execute("INSERT OR IGNORE INTO source VALUES (?,?,?,?)", (src, meta["pdf"], meta["sha256"], int(meta["pages"])))
        hours, _ = parse_pdf(src, p0, p1)
        for hr in hours:
            if getattr(hr, "day_key", None):
                key = hr.day_key if src == "PA" else f"{src}.{hr.day_key}"
                info = {"key": key, "season": "ORD" if hr.day_key.startswith("ORD") else "PROP", "week": None,
                        "weekday": None, "psalter_week": None, "title": hr.day_title, "rank": "appendix", "precedence": None}
            else:
                info = day_info(src, hr.section, hr.day)
            days.setdefault(info["key"], info)
            code = hour_code(hr.code, hr.subtitle)
            n_seen = seen_hours.get((info["key"], code), 0)
            seen_hours[(info["key"], code)] = n_seen + 1
            copy = f"#{n_seen + 1}" if n_seen else None        # e.g. Ascension's two tracks
            cur = con.execute(
                "INSERT INTO hour_instance (source,day_key,hour,section,day_title,subtitle,page_start,page_end,copy)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (src, info["key"], code, hr.section, hr.day, hr.subtitle, hr.page_start, hr.page_end, copy))
            hid = cur.lastrowid
            last_ref = ""
            for seq, e in enumerate(hr.elements):
                if e.type == "label":
                    last_ref = e.data.get("ref", "")
                elif e.type in REF_TYPES and last_ref:
                    e.data["ref"] = last_ref
                    last_ref = ""
                c = canon(e)
                oid = None
                extra: dict = {}
                otype = e.type
                if c is not None:
                    otype, payload, key, extra = c
                    ob = objects.get(key)
                    if ob is None:
                        oid = object_id(otype, payload, key)
                        n = 2
                        while oid in ids and ids[oid] != key:   # hash-prefix collision: disambiguate
                            oid = f"{object_id(otype, payload, key)}~{n}"
                            n += 1
                        ids[oid] = key
                        ob = objects[key] = {"id": oid, "type": otype, "payload": payload, "n": 0, "key": key}
                    ob["n"] += 1
                    oid = ob["id"]
                else:
                    extra = {"text": e.data.get("text") or e.data.get("label", "")}
                    if e.data.get("ref"):
                        extra["ref"] = e.data["ref"]
                    if e.data.get("year"):
                        extra["year"] = e.data["year"]
                con.execute(
                    "INSERT INTO occurrence (hour_id,seq,type,slot,sub,cond,object_id,page,page_end,source_text,extra)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (hid, seq, otype, e.slot, e.sub, json.dumps(e.cond, ensure_ascii=False) if e.cond else None,
                     oid, e.page, e.lines[-1].page if e.lines else e.page, e.source_text,
                     json.dumps(extra, ensure_ascii=False) if extra else None))
    con.executemany("INSERT INTO day VALUES (?,?,?,?,?,?,?,?)",
                    [(d["key"], d["season"], d["week"], d["weekday"], d["psalter_week"], d["title"], d["rank"],
                      d["precedence"]) for d in days.values()])
    rows = []
    for ob in objects.values():
        p = ob["payload"]
        rows.append((ob["id"], ob["type"], incipit(ob["type"], p), plain_text(ob["type"], p),
                     json.dumps(p, ensure_ascii=False), hashlib.sha1(ob["key"].encode("utf-8")).hexdigest(),
                     ob["n"], "unverified", None))
    con.executemany("INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO object_fts (id, type, plain) SELECT id, type, plain FROM object")
    build_psalm_use(con)
    con.commit()
    n_occ = con.execute("SELECT count(*) FROM occurrence").fetchone()[0]
    print(f"[build] {', '.join(sources)}: {len(days)} days, {len(objects)} objects, {n_occ} occurrences "
          f"in {time.time() - t0:.0f}s -> {db_path}")
    con.close()


def build_psalm_use(con: sqlite3.Connection) -> None:
    q = """SELECT o.id, o.object_id, o.slot, o.extra, ob.payload, h.day_key, h.hour, d.psalter_week, d.weekday
           FROM occurrence o JOIN object ob ON ob.id = o.object_id JOIN hour_instance h ON h.id = o.hour_id
           JOIN day d ON d.key = h.day_key WHERE ob.type = 'psalm'"""
    rows = []
    for occ, oid, slot, extra, payload, day_key, hour, pw, wd in con.execute(q).fetchall():
        p = json.loads(payload)
        x = json.loads(extra or "{}")
        verses, starts_mid = unit_verses(p["lines"])
        if starts_mid and verses:
            m = re.match(r"\d+", verses[0])
            if m:
                verses.insert(0, f"{int(m.group(0)) - 1}b")
        rows.append((occ, psalm_base(p["psalm"]), oid, json.dumps(verses), verses[0] if verses else None,
                     verses[-1] if verses else None, x.get("section", ""), day_key, hour, slot, pw, wd))
    con.executemany("INSERT INTO psalm_use VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
