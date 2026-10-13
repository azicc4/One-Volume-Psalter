"""L6 verification. Each check writes rows to check_result and returns a summary dict for the report.

  roundtrip  every occurrence's object + extra must reproduce the printed source text exactly (whitespace/tags aside)
  index      the hours parsed per day must match the PDF's own index pages ("Feria II ol ld hm vp cp")
  structure  every hour must contain the slots its GILH template requires
  variants   near-identical objects of the same type (possible typos/variants in the source) are flagged
  psalms     every psalm verse line must read the same in every printing (consensus), → psalm_verse table
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3

from rapidfuzz import fuzz, process

from lh.config import DB_PATH
from lh.extract.spans import open_l1
from lh.model.canon import cmp_key, plain, restore
from lh.model.days import day_info


def _con(db=DB_PATH):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def record(con, name, subject, status, detail=""):
    con.execute("INSERT INTO check_result VALUES (?,?,?,?)", (name, subject, status,
                                                               detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)))


# ------------------------------------------------------------------------------------------------ round trip

def check_roundtrip(con) -> dict:
    q = """SELECT o.id, o.type, o.slot, o.object_id, o.extra, o.source_text, o.page, ob.payload, ob.type AS otype,
                  ob.status
           FROM occurrence o JOIN object ob ON ob.id = o.object_id"""
    n, bad, overridden = 0, [], 0
    for r in con.execute(q):
        if r["status"] == "overridden":     # differs from the PDF on purpose (data/overrides/)
            overridden += 1
            continue
        n += 1
        rebuilt = restore(r["otype"], json.loads(r["payload"]), json.loads(r["extra"] or "{}"), r["slot"])
        if cmp_key(rebuilt) != cmp_key(r["source_text"]):
            bad.append(r)
    for r in bad[:500]:
        record(con, "roundtrip", f"occ:{r['id']}", "fail",
               {"object": r["object_id"], "page": r["page"], "source": r["source_text"][:300]})
    record(con, "roundtrip", "all", "pass" if not bad else "fail", f"{n - len(bad)}/{n} occurrences reproduce exactly")
    return {"occurrences": n, "failures": len(bad), "overridden": overridden,
            "examples": [(r["object_id"], r["page"]) for r in bad[:10]]}


# ------------------------------------------------------------------------------------------------ PDF index

INDEX_CODES = {"1v": "V1", "ol": "OR", "ld": "LAUDS", "hm": "MIDDAY", "vp": "VESPERS"}


def expected_from_index(source: str) -> dict[str, set[str]]:
    """Read the PDF's own index pages: day entries are blue link lines like 'Feria II   ol   ld   hm   vp   cp'."""
    l1 = open_l1(source)
    pages = [r[0] for r in l1.execute("SELECT page FROM outline WHERE title IN ('Index','INDEX') ORDER BY seq LIMIT 1")]
    p0 = pages[0] if pages else 3
    rows = l1.execute("SELECT page, text, spans FROM line WHERE page BETWEEN ? AND ? ORDER BY id", (p0, p0 + 8)).fetchall()
    l1.close()
    exp: dict[str, set[str]] = {}
    section = ""
    from lh.sources import plugin
    section_re = getattr(plugin(source), "INDEX_SECTION_RE", r"^(HEBDOMADA [IVXL]+|SOLLEMNITATES)$")
    for page, text, spans in rows:
        t = re.sub(r"\s+", " ", text).strip()
        if re.match(section_re, t):
            section = t
            continue
        m = re.match(r"^(.*?) ((?:(?:1v|cp|ol|ld|hm|vp) ?)+)$", t)
        if not m or not section:
            continue
        name, codes = m.group(1), m.group(2).split()
        hours = set()
        after_v1 = False
        for c in codes:
            if c == "cp":
                hours.add("COMPLINE1" if after_v1 and "ol" not in hours_seen(hours) else "COMPLINE")
            elif c == "1v":
                hours.add("V1")
                after_v1 = True
            else:
                hours.add(INDEX_CODES[c])
        if "OR" in hours:
            hours.add("INV")
        if "V1" in hours and "VESPERS" in hours:      # Sunday/solemnity: second vespers
            hours.discard("VESPERS")
            hours.add("V2")
        exp[f"{section}|{name}"] = hours
    return exp


def hours_seen(h):
    return {"ol"} if "OR" in h else set()


def check_index(con, source: str) -> dict:
    from lh.sources import plugin
    hook = getattr(plugin(source), "check_index", None)
    if hook:                  # volumes whose index differs from Per annum's (Sanctis: lh/sources/sanctis_seasons.py)
        return hook(con, source, record)
    exp = expected_from_index(source)
    got: dict[str, set[str]] = collections.defaultdict(set)
    for r in con.execute("SELECT DISTINCT section, day_title, day_key, hour FROM hour_instance WHERE source=?", (source,)):
        got[r["day_key"]].add(r["hour"])
    # map index entries to day keys
    index_days = {}
    from lh.sources import plugin
    index_day_key = getattr(plugin(source), "index_day_key", None)
    for k, hours in exp.items():
        section, name = k.split("|")
        if index_day_key is not None:          # source-specific index layout (e.g. LQP)
            key = index_day_key(section, name)
            if key:
                index_days.setdefault(key, set()).update(hours)   # a day listed on two tracks: union
            continue
        if section == "SOLLEMNITATES":
            continue
        title = {"Dominica": "DOMINICA", "Sabbato": "SABBATO"}.get(name, name.upper())
        if name.startswith("Christus"):
            continue
        try:
            info = day_info(source, section, title)
        except Exception:
            continue
        index_days[info["key"]] = hours
    mism = []
    for key, hours in sorted(index_days.items()):
        g = got.get(key, set())
        if hours != g:
            mism.append((key, sorted(hours - g), sorted(g - hours)))
            record(con, "index", key, "fail", {"missing": sorted(hours - g), "unexpected": sorted(g - hours)})
    record(con, "index", source, "pass" if not mism else "fail", f"{len(index_days) - len(mism)}/{len(index_days)} days match")
    return {"days_in_index": len(index_days), "mismatches": mism[:20], "n_mismatch": len(mism)}


# ------------------------------------------------------------------------------------------------ structure

REQUIRED = {
    "INV": ["OPENING", "INV_ANT", "INV_PSALM"],
    "OR": ["OPENING", "HYMN", "PS1", "PS2", "PS3", "OR_VERSE", "LECT1", "RESP1", "LECT2", "RESP2", "ORATIO", "CONCLUSION"],
    "LAUDS": ["OPENING", "HYMN", "PS1", "PS2", "PS3", "LB", "RB", "GOSPEL_ANT", "GOSPEL_CANT", "PRECES", "PATER", "ORATIO", "CONCLUSION"],
    "VESPERS": ["OPENING", "HYMN", "PS1", "PS2", "PS3", "LB", "RB", "GOSPEL_ANT", "GOSPEL_CANT", "PRECES", "PATER", "ORATIO", "CONCLUSION"],
    "MIDDAY": ["OPENING", "HYMN", "PS1", "PS2", "PS3", "LB", "V", "ORATIO", "CONCLUSION"],
    "COMPLINE": ["OPENING", "HYMN", "PS1", "LB", "RB", "GOSPEL_ANT", "GOSPEL_CANT", "ORATIO", "BLESSING", "MARIAN"],
}
REQUIRED["V1"] = REQUIRED["V2"] = REQUIRED["VESPERS"]
REQUIRED["COMPLINE1"] = REQUIRED["COMPLINE"]
# Days whose hour follows a different GILH template (source-independent).
#   GILH 212: "The Easter Vigil takes the place of the Office of Readings: those not present at the Vigil should
#   therefore choose from it at least four readings with canticles and prayers … The Te Deum and the prayer of the
#   day follow."  (No hymn, no psalmody, no versicle, no responsories.)
TEMPLATE_EXCEPTIONS = {
    ("EAS.1.SUN", "OR"): ["LECT1", "LECT2", "LECT3", "LECT4", "PS1", "PS2", "PS3", "TE_DEUM", "ORATIO", "CONCLUSION"],
}
# Slot substitutions are modelled by the parser (lh/parse/hour.py): "Loco responsorii dicitur:" + antiphon
# (Christus factus est / Hæc dies) is the RB slot; the Regína cæli printed in full is the MARIAN slot (GILH 92).
# Source-specific omissions are excused by the plug-in's STRUCTURE_EXCEPTIONS (lh/sources/<key>.py).


def _source_exceptions(source: str) -> dict:
    from lh.sources import plugin
    try:
        return getattr(plugin(source), "STRUCTURE_EXCEPTIONS", {}) or {}
    except (KeyError, ImportError):
        return {}


def check_structure(con) -> dict:
    slots: dict[int, set] = collections.defaultdict(set)
    subs: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in con.execute("SELECT hour_id, type, slot, sub, source_text FROM occurrence"):
        slots[r["hour_id"]].add(r["slot"])
        if r["sub"]:
            subs[r["hour_id"]][r["slot"]] += 1
        t = r["source_text"] or ""
        # memorials take parts from the current day: "Antiphonæ, psalmi, versus et lectio prior cum suo responsorio,
        # de sabbato currente." (BVM on Saturday, PA 6271); a reading given by link carries its responsory
        if r["type"] == "rubric" and re.search(r"\bde (?:sabbato|feria) currente\b", t):
            if re.match(r"^Antiphonæ(?:,| et) psalmi", t):
                slots[r["hour_id"]].update(("PS1", "PS2", "PS3"))
                # the versicle goes with the psalmody ("Antiphonæ, psalmi et lectio prior … de feria currente.", SP 130)
                slots[r["hour_id"]].add("OR_VERSE")
            if "versus" in t:
                slots[r["hour_id"]].add("OR_VERSE")
            if "lectio prior" in t:
                slots[r["hour_id"]].update(("LECT1", "RESP1"))
        if r["type"] == "link" and r["slot"] in ("LECT1", "LECT2"):
            slots[r["hour_id"]].add("RESP" + r["slot"][-1])
        # RB / MARIAN substitutions (Loco responsorii, Regína cæli) are modelled by the parser — see above
    from lh.sources import MODULES, plugin
    bad, excused = [], []
    for h in con.execute("SELECT id, source, day_key, hour, copy, page_start FROM hour_instance "
                         "WHERE day_key NOT LIKE '%ORD.%' AND day_key NOT LIKE '%PROP.%'"):   # appendix fragments
        req = TEMPLATE_EXCEPTIONS.get((h["day_key"], h["hour"])) or REQUIRED.get(h["hour"], [])
        hook = getattr(plugin(h["source"]), "required_slots", None) if h["source"] in MODULES else None
        if hook:          # printed forms with their own template, e.g. Sanctis commemorations (sanctis_seasons.py)
            req = hook(h["day_key"], h["hour"], h["copy"], req)
        missing = [s for s in req if s not in slots[h["id"]]]
        if h["hour"] == "MIDDAY" and "LINK" in slots[h["id"]]:      # complementary psalmody given by reference
            missing = [s for s in missing if s not in ("PS1", "PS2", "PS3")]
        if h["hour"] == "MIDDAY" and (h["day_key"], h["hour"]) not in TEMPLATE_EXCEPTIONS:
            for s in ("LB", "V", "ORATIO"):     # Terce, Sext and None each need LB, V, ORATIO
                if subs[h["id"]][s] < 3:
                    missing.append(f"{s}x3")
        exc = _source_exceptions(h["source"]).get((h["day_key"], h["hour"]))
        if missing and exc and set(missing) <= set(exc["missing"]):
            excused.append((h["day_key"], h["hour"], h["page_start"], missing))
            record(con, "structure", f"{h['day_key']} {h['hour']}", "excused",
                   {"missing": missing, "page": h["page_start"], "reason": exc["reason"]})
            continue
        if missing:
            bad.append((h["day_key"], h["hour"], h["page_start"], missing))
            record(con, "structure", f"{h['day_key']} {h['hour']}", "fail", {"missing": missing, "page": h["page_start"]})
    n = con.execute("SELECT count(*) FROM hour_instance WHERE day_key NOT LIKE '%ORD.%' AND day_key NOT LIKE '%PROP.%'").fetchone()[0]
    record(con, "structure", "all", "pass" if not bad else "fail",
           f"{n - len(bad)}/{n} hours complete ({len(excused)} excused source omissions)")
    return {"hours": n, "incomplete": len(bad), "examples": bad[:15], "excused": len(excused)}


# ------------------------------------------------------------------------------------------------ near-duplicates

def check_variants(con, threshold: float = 93.0) -> dict:
    """Flag objects of the same type whose plain texts are nearly (not exactly) identical."""
    found = []
    for otype in ("ant", "oratio", "lectio_brevis", "versicle", "resp_breve", "hymn", "preces", "responsory"):
        rows = con.execute("SELECT id, plain, n_occ FROM object WHERE type=?", (otype,)).fetchall()
        texts = [r["plain"] for r in rows]
        for i, r in enumerate(rows):
            if len(r["plain"]) < 25:
                continue
            for _, score, j in process.extract(r["plain"], texts, scorer=fuzz.ratio, limit=3, score_cutoff=threshold):
                if j <= i or texts[j] == r["plain"]:
                    continue
                found.append((otype, r["id"], rows[j]["id"], round(score, 1), r["n_occ"], rows[j]["n_occ"]))
    for f in found:
        record(con, "variants", f"{f[1]} ~ {f[2]}", "review", {"type": f[0], "score": f[3], "n": [f[4], f[5]]})
    return {"pairs": len(found), "examples": found[:25]}


# ------------------------------------------------------------------------------------------------ psalm text consensus

def check_psalms(con) -> dict:
    """Every printing of a psalm verse line must agree. Builds psalm_verse with the majority reading."""
    lines: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    xs: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    vulg: dict[int, str] = {}
    q = """SELECT ob.payload, ob.n_occ FROM object ob WHERE ob.type='psalm'"""
    for r in con.execute(q):
        p = json.loads(r["payload"])
        base = int(re.match(r"\d+", p["psalm"]).group(0))
        vulg.setdefault(base, p["vulg"])
        v, k = None, 0
        for ln in p["lines"]:
            if ln["v"]:
                v, k = ln["v"], 0
            else:
                k += 1
            key = (base, v, k)
            lines[key][ln["t"]] += r["n_occ"]
            xs[key][ln["x"]] += r["n_occ"]
    disagree = []
    rows = []

    def vkey(v):
        m = re.match(r"\(?(\d+)(?:,(\d+))?([a-z]?)", v or "0")
        return (int(m.group(1)), int(m.group(2) or 0), m.group(3)) if m else (0, 0, "")

    by_psalm = collections.defaultdict(list)
    for (base, v, k), cnt in lines.items():
        by_psalm[base].append((vkey(v), k, v, cnt))
    for base, items in by_psalm.items():
        items.sort()
        for seq, (_, k, v, cnt) in enumerate(items):
            (text, n_agree), total = cnt.most_common(1)[0], sum(cnt.values())
            x = xs[(base, v, k)].most_common(1)[0][0]
            rows.append((base, seq, v, k, x, text, "LH", total, n_agree, 1))
            if len(cnt) > 1:
                disagree.append((base, v, k, dict(cnt)))
                record(con, "psalms", f"Ps {base}:{v} line {k}", "flag", {"readings": dict(cnt)})
    con.executemany("INSERT INTO psalm_verse VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    for base, vu in vulg.items():
        con.execute("INSERT OR IGNORE INTO psalm (num, vulgate) VALUES (?,?)", (base, vu))
    record(con, "psalms", "all", "pass" if not disagree else "review",
           f"{len(rows)} verse lines in {len(by_psalm)} psalms; {len(disagree)} lines with divergent readings")
    return {"psalms": len(by_psalm), "lines": len(rows), "divergent": len(disagree), "examples": disagree[:15]}


def run_all(sources=("PA",), db=DB_PATH) -> dict:
    con = _con(db)
    con.execute("DELETE FROM check_result")
    con.execute("DELETE FROM psalm_verse")
    out = {"roundtrip": check_roundtrip(con)}
    for s in sources:
        out[f"index:{s}"] = check_index(con, s)
    out["structure"] = check_structure(con)
    out["psalms"] = check_psalms(con)
    out["variants"] = check_variants(con)
    con.commit()
    built = [r[0] for r in con.execute("SELECT key FROM source ORDER BY rowid")]
    con.close()
    from lh.verify.coverage import coverage
    for s in built:                       # every source in the database, not only those with an index check
        out[f"coverage:{s}"] = coverage(s, db)
    if set(built) & {"SP", "SQ", "SADV"}:  # saints printed in several Sanctis volumes -> reports/sanctis_overlaps.md
        from lh.verify.sanctis_overlaps import sanctis_overlaps
        out["sanctis_overlaps"] = sanctis_overlaps(db)
    return out
