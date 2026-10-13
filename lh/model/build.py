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
from lh.model.canon import canon, fold, incipit, object_id, plain_text, psalm_base, unit_verses
from lh.model.days import day_info, hour_code, short_name
from lh.parse.run import parse_pdf
from lh.sources import copy_label, non_content, plugin

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
        con.execute("INSERT OR IGNORE INTO source VALUES (?,?,?,?,?,?)",
                    (src, meta["pdf"], meta["sha256"], int(meta["pages"]), p0, p1))
        hours, outside = parse_pdf(src, p0, p1)
        # lines on a page the plug-in declares non-content (cover, index …) are front matter, whatever they look like
        con.executemany("INSERT INTO source_line VALUES (?,?,?,?,?,?,?,?)",
                        [(src, o.line.l1_ids[0], o.line.l1_ids[-1], o.line.page,
                          "front" if non_content(src, o.line.page) else o.role, o.section, o.day, o.line.text)
                         for o in outside])
        appendix_days = getattr(plugin(src), "APPENDIX_DAYS", {})   # appendix chapters that are real days
        refine = getattr(plugin(src), "refine_hour", None)   # optional plug-in hook: (hour, info, copy) -> (info, copy)
        for hr in hours:
            if getattr(hr, "day_key", None) and hr.day_title in appendix_days:
                info = dict(appendix_days[hr.day_title])
            elif getattr(hr, "day_key", None):
                key = hr.day_key if src == "PA" else f"{src}.{hr.day_key}"
                info = {"key": key, "season": "ORD" if hr.day_key.startswith("ORD") else "PROP", "week": None,
                        "weekday": None, "psalter_week": None, "title": hr.day_title, "rank": "appendix", "precedence": None}
            else:
                info = day_info(src, hr.section, hr.day, hr.day_extra)
            # e.g. Advent start-date copy "28 Nov"; or an appendix fragment's own label ("LECTIO ALTERA"); or a
            # per-printing form set by a plug-in's day_info (Sanctis "commemoratio")
            vol_copy = getattr(hr, "copy", None) or info.get("copy") or copy_label(src, hr.page_start)
            if refine is not None:                              # e.g. ADV: days after Epiphany, Epiphany tracks
                info, vol_copy = refine(hr, info, vol_copy)
            days.setdefault(info["key"], info)
            code = hour_code(hr.code, hr.subtitle)
            n_seen = seen_hours.get((info["key"], code, vol_copy), 0)
            seen_hours[(info["key"], code, vol_copy)] = n_seen + 1
            dup = f"#{n_seen + 1}" if n_seen else None          # e.g. Ascension's two tracks
            copy = " ".join(x for x in (vol_copy, dup) if x) or None
            cur = con.execute(
                "INSERT INTO hour_instance (source,day_key,hour,section,day_title,subtitle,page_start,page_end,copy,"
                "l1_first,l1_last) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (src, info["key"], code, hr.section, hr.day, hr.subtitle, hr.page_start, hr.page_end, copy,
                 hr.lines[0].l1_ids[0], hr.lines[-1].l1_ids[-1]))
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
    con.executemany("INSERT INTO day VALUES (?,?,?,?,?,?,?,?,?)",
                    [(d["key"], d["season"], d["week"], d["weekday"], d["psalter_week"], d["title"], d["rank"],
                      d["precedence"], short_name(d)) for d in days.values()])
    rows = []
    for ob in objects.values():
        p = ob["payload"]
        rows.append((ob["id"], ob["type"], incipit(ob["type"], p), plain_text(ob["type"], p),
                     json.dumps(p, ensure_ascii=False), hashlib.sha1(ob["key"].encode("utf-8")).hexdigest(),
                     ob["n"], "unverified", None))
    con.executemany("INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO object_fts (id, type, plain) SELECT id, type, plain FROM object")
    build_psalm_use(con)
    build_hour_refs(con)
    build_link_targets(con)
    from lh.model.overrides import apply as apply_overrides
    n_over = apply_overrides(con)          # reviewed corrections (data/overrides/*.yaml)
    if n_over:
        print(f"[build] applied {n_over} override(s)")
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


LINK_PREFIX_RE = re.compile(r"^(?:Ad libitum(?: dici potest hymnus)?|Memoria ad libitum)\s+")


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(s or ""))


def build_link_targets(con: sqlite3.Connection) -> None:
    """Resolve each printed link to what is printed at its target page in the same PDF (table link_target).

    A link that names its target (a hymn incipit — "Ad libitum dici potest hymnus Salve dies." —, a reading's source
    "Ex Sermónibus sancti Procli…", an invitatory psalm "Venite, exsultemus Domino") resolves to that element on the
    target page or the next (how = 'text'); otherwise to the first element on the page, preferring an hour of the link's own kind
    (Conclusio → the dismissal of that hour; "Memoria ad libitum Sanctæ Mariæ" → the memorial's hour) (how = 'page')."""
    by_page: dict = {}
    for r in con.execute("""SELECT o.id, o.hour_id, h.source, h.hour, o.page, o.object_id, ob.plain
                            FROM occurrence o JOIN hour_instance h ON h.id = o.hour_id JOIN object ob ON ob.id = o.object_id
                            WHERE o.type NOT IN ('rubric', 'link') ORDER BY o.id"""):
        by_page.setdefault((r[2], r[4]), []).append(r)
    hours = con.execute("SELECT id, source, hour, page_start, page_end FROM hour_instance ORDER BY id").fetchall()
    rows = []
    for occ, src, code, extra, text in con.execute(
            """SELECT o.id, h.source, h.hour, o.extra, o.source_text FROM occurrence o
               JOIN hour_instance h ON h.id = o.hour_id WHERE o.type = 'link' ORDER BY o.id""").fetchall():
        page = json.loads(extra or "{}").get("target")
        if not page:
            continue
        cands = by_page.get((src, page), [])
        want = _words(LINK_PREFIX_RE.sub("", text))
        # the named element may start on the next page (its label is at the foot of the target page)
        near = cands + by_page.get((src, page + 1), [])
        hit = next((c for c in near if len(want) >= 2
                    and _words(re.sub(r"^\([^)]*\)\s*", "", c[6]))[:len(want)] == want), None)
        how = "text"
        if hit is None:
            how = "page"
            hit = next((c for c in cands if c[3] == code), None) or (cands[0] if cands else None)
        if hit is not None:
            rows.append((occ, page, hit[1], hit[0], hit[5], how))
            continue
        cover = [h for h in hours if h[1] == src and h[3] <= page <= h[4]]
        hr = next((h for h in cover if h[2] == code), None) or (cover[0] if cover else None)
        if hr is not None:
            rows.append((occ, page, hr[0], None, None, how))
    con.executemany("INSERT INTO link_target VALUES (?,?,?,?,?,?)", rows)


ORDINARY_ANCHOR = {"INV": "ord:invitatory", "OR": "ord:or", "LAUDS": "ord:lauds", "MIDDAY": "ord:midday",
                   "VESPERS": "ord:vespers", "V1": "ord:vespers", "V2": "ord:vespers",
                   "COMPLINE": "ord:compline", "COMPLINE1": "ord:compline"}


def build_hour_refs(con: sqlite3.Connection) -> None:
    """Per hour: the Ordinary anchor, the psalm/canticle units (≤3; Invitatory: none — its psalm is fixed) and,
    for the Office of Readings, the readings and responsories. The book prints their pages at each hour head."""
    rows = []
    for h in con.execute("SELECT id, day_key, hour FROM hour_instance").fetchall():
        psalms, readings = {}, {}
        for slot, oid in con.execute("""SELECT o.slot, o.object_id FROM occurrence o JOIN object ob ON ob.id=o.object_id
                                        WHERE o.hour_id=? ORDER BY o.seq""", (h[0],)):
            if re.fullmatch(r"PS\d", slot or "") and slot not in psalms:
                psalms[slot] = oid
            elif slot in ("LECT1", "RESP1", "LECT2", "RESP2") and slot not in readings:
                readings[slot] = oid
        rows.append((h[0], h[1], h[2], ORDINARY_ANCHOR.get(h[2]), json.dumps(psalms), json.dumps(readings) if readings else None))
    con.executemany("INSERT INTO hour_refs VALUES (?,?,?,?,?,?)", rows)
