"""Saints printed in more than one Sanctis volume (WS4b): reports/sanctis_overlaps.md.

Overlaps: SQ ∩ SPA (Feb–Mar), SQ ∩ SP (19 Mar, 25 Mar, 2–13 Apr), SP ∩ SPA (May–June), SADV ∩ SPA (30 Nov).
SP, SQ and SADV come from the database. SPA is not parsed yet (WS4a), so its offices are parsed here on the fly from
its L1 dump with the WS4b header parser (lh/sources/sanctis_seasons.py) and compared by object identity (the same
canonical key the database hashes into object.hash).

For each pair of printings of one day the texts are compared slot by slot (main printings only, not ALTERA):
  same       identical object
  alleluia   identical once "allelúia" is removed (Easter-time form)
  differs    a genuine text difference — listed in full below, to be reviewed (TODO.md §3)
A commemoration (SQ "commemoratio") is compared through its own slots: Office of Readings LECT2/RESP2/ORATIO and the
Lauds/Vespers antiphon against the other printing's Gospel antiphon.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sqlite3

from lh.config import DB_PATH, L1_DIR, REPORTS
from lh.model.canon import canon, fold, plain_text
from lh.model.days import hour_code

PAIRS = [("SQ", "SPA"), ("SQ", "SP"), ("SP", "SPA"), ("SADV", "SPA")]
SKIP_SLOTS = {"OPENING", "CONCLUSION", "PATER", "SUBTITLE", "INV_PSALM", "PREP_PRAYER", "LINK", "SUBST", "MARIAN"}


def _slotkey(hour: str, slot: str, sub: str, alt: bool, comm: bool) -> tuple | None:
    if not slot or slot in SKIP_SLOTS or slot.endswith("_R"):
        return None
    if comm and hour in ("LAUDS", "VESPERS") and slot == "ANT":
        slot = "GOSPEL_ANT"          # the commemoration antiphon is the saint's Benedictus/Magnificat antiphon
    return (hour, slot, sub or "", alt)


def _db_printings(con, source: str) -> dict:
    """{day_key: {"pages": (p0, p1), "comm": bool, "slots": {slotkey: (hash, plain, page)}}} — main printings only."""
    out: dict = {}
    ndays = dict(con.execute("""SELECT o.object_id, count(DISTINCT h.day_key) FROM occurrence o
                                JOIN hour_instance h ON h.id=o.hour_id WHERE h.source=? GROUP BY 1""", (source,)))
    q = """SELECT h.day_key, h.hour, h.copy, h.page_start, o.slot, o.sub, o.cond, o.page, ob.hash, ob.plain, ob.id
           FROM hour_instance h JOIN occurrence o ON o.hour_id=h.id JOIN object ob ON ob.id=o.object_id
           WHERE h.source=? AND (h.copy IS NULL OR h.copy NOT LIKE 'altera%') ORDER BY h.id, o.seq"""
    for key, hour, copy, p0, slot, sub, cond, page, hsh, txt, oid in con.execute(q, (source,)):
        d = out.setdefault(key, {"pages": [p0, p0], "comm": copy == "commemoratio", "slots": {}})
        d["pages"][1] = max(d["pages"][1], page)
        sk = _slotkey(hour, slot, sub, "alt" in json.loads(cond or "{}"), d["comm"])
        if sk:
            d["slots"].setdefault(sk, (hsh, txt, page, ndays.get(oid, 1)))
    return out


def _spa_printings(wanted: set[str]) -> dict:
    """Parse SPA days whose SANCT key or MM-DD is in `wanted` straight from its L1 dump (no DB, no SPA plug-in)."""
    if not (L1_DIR / "SPA.sqlite").exists():
        return {}
    from lh.extract.lines import load_lines
    from lh.parse.hour import parse_hour, segment
    from lh.sources.sanctis_seasons import classify_lines, sanct_day_info
    lines = load_lines("SPA")
    classify_lines(lines)                   # SPA's own plug-in is WS4a's; reuse the WS4b header logic here
    cut = next((i for i, L in enumerate(lines) if L.kind == "week" and L.text.startswith("ALIA EX")), len(lines))
    hours, _ = segment(lines[:cut], "SPA")
    out: dict = {}
    days_of: dict[str, set] = collections.defaultdict(set)      # object hash -> SPA days using it
    for hr in hours:
        if hr.section.startswith("ALTERA"):
            continue
        try:
            info = sanct_day_info(hr.section, hr.day, hr.day_extra)
        except ValueError:
            continue
        key = info["key"]
        mmdd = key.split(".")[1] if key.startswith("SANCT.") else None
        parse_hour(hr)
        code = hour_code(hr.code, hr.subtitle)
        keep = key in wanted or mmdd in wanted
        if keep:
            d = out.setdefault(key, {"pages": [hr.page_start, hr.page_end], "slots": {}, "title": info["title"],
                                     "comm": info.get("copy") == "commemoratio"})
            d["pages"][1] = max(d["pages"][1], hr.page_end)
        for e in hr.elements:
            c = canon(e)
            if c is None:
                continue
            otype, payload, ident, _ = c
            hsh = hashlib.sha1(ident.encode("utf-8")).hexdigest()
            days_of[hsh].add(key)
            sk = _slotkey(code, e.slot, e.sub, "alt" in e.cond, keep and d["comm"])
            if keep and sk:
                d["slots"].setdefault(sk, [hsh, plain_text(otype, payload), e.page, 1])
    for d in out.values():
        for v in d["slots"].values():
            v[3] = len(days_of[v[0]])
    return out


def _no_alleluia(s: str) -> str:
    s = re.sub(r"\balleluia\b", " ", fold(s))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _core(s: str) -> str:
    """Seasonal shape of a short responsory: Easter time repeats 'Allelúia, allelúia' instead of the second half of
    the response. Compare the response and the versicle up to its '*'."""
    if s.startswith("R. ") and " V. " in s:
        r, _, v = s[3:].partition(" V. ")
        return _no_alleluia(r) + "|" + _no_alleluia(v.split("*")[0])
    return _no_alleluia(s)


def _compare(a: dict, b: dict) -> tuple[collections.Counter, list]:
    """Classify each shared slot: same · alleluia (Easter form) · variant (near-identical: possible typo, review) ·
    common (both texts are used on several days of their volume: a season-specific Common) · differs (review)."""
    from rapidfuzz import fuzz
    cnt: collections.Counter = collections.Counter()
    diffs = []
    for sk in sorted(set(a["slots"]) & set(b["slots"])):
        ha, ta, pa, na = a["slots"][sk]
        hb, tb, pb, nb = b["slots"][sk]
        if ha == hb:
            cnt["same"] += 1
        elif _no_alleluia(ta) == _no_alleluia(tb) or _core(ta) == _core(tb):
            cnt["alleluia"] += 1
        elif fuzz.ratio(_no_alleluia(ta), _no_alleluia(tb)) >= 90:
            cnt["variant"] += 1
            diffs.append(("variant", sk, pa, ta, pb, tb))
        elif na >= 2 and nb >= 2:
            cnt["common"] += 1
        else:
            cnt["differs"] += 1
            diffs.append(("differs", sk, pa, ta, pb, tb))
    cnt["only_a"] = len(set(a["slots"]) - set(b["slots"]))
    cnt["only_b"] = len(set(b["slots"]) - set(a["slots"]))
    return cnt, diffs


def _date(key: str) -> str:
    m = re.match(r"^SANCT\.(\d\d-\d\d)\.", key)
    return m.group(1) if m else {"SOL.IMMACULATE_CONCEPTION": "12-08"}.get(key, key)


def sanctis_overlaps(db=DB_PATH) -> dict:
    con = sqlite3.connect(db)
    built = {r[0] for r in con.execute("SELECT key FROM source")}
    pr = {s: _db_printings(con, s) for s in ("SP", "SQ", "SADV") if s in built}
    con.close()
    wanted = {k for p in pr.values() for k in p} | {_date(k) for p in pr.values() for k in p}
    pr["SPA"] = _spa_printings(wanted)
    rows, details, summary = [], [], collections.Counter()
    key_mismatch = []
    for a, b in PAIRS:
        if a not in pr or not pr.get(b):
            continue
        pa, pb = pr[a], pr[b]
        by_date_b = collections.defaultdict(list)
        for k in pb:
            by_date_b[_date(k)].append(k)
        for k in sorted(pa, key=_date):
            if k in pb:
                cnt, diffs = _compare(pa[k], pb[k])
                summary[(a, b)] += 1
                form = "commemoratio" if pa[k]["comm"] else ""
                rows.append((a, b, k, pa[k]["pages"], pb[k]["pages"], form, cnt))
                details += [(a, b, k, d) for d in diffs]
            elif _date(k) in by_date_b:
                key_mismatch.append((a, b, k, by_date_b[_date(k)]))
    write_report(rows, details, key_mismatch)
    return {"days": len(rows), "review": sum(r[6]["differs"] + r[6]["variant"] for r in rows),
            "key_mismatch": len(key_mismatch), "pairs": {f"{a}∩{b}": n for (a, b), n in summary.items()}}


def write_report(rows, details, key_mismatch) -> None:
    L = ["# Saints printed in more than one Sanctis volume", "",
         "Generated by `python -m lh verify` (lh/verify/sanctis_overlaps.py, WS4b). SP, SQ, SADV from the database; "
         "SPA parsed on the fly from its L1 dump with the WS4b header parser (SPA itself is WS4a's).", "",
         "Each overlapping day resolves to one day key; each printing stays its own set of objects (seasonal forms). "
         "Slots are compared on the main printings (not ALTERA):", "",
         "- **same** — identical object;",
         "- **alleluia** — identical apart from the Easter-time *allelúia* (incl. the Easter shape of short "
         "responsories) — a seasonal variant;",
         "- **common** — different texts that are each used on several days of their own volume, i.e. the season's "
         "Common or Ordinary (Lenten vs Easter Compline, Easter Common of martyrs …) — expected;",
         "- **variant** — near-identical texts (possible typo) — *review*;",
         "- **differs** — a different proper text — *review*;",
         "- *only A / only B* — slots printed in one volume only (a commemoration prints no hymns or psalmody; "
         "memorials print psalmody «de feria»).", "",
         "A day's texts *agree* when nothing is left to review.", ""]
    for a, b in PAIRS:
        sel = [r for r in rows if (r[0], r[1]) == (a, b)]
        if not sel:
            continue
        tot = collections.Counter()
        for r in sel:
            tot.update(r[6])
        L += [f"## {a} ∩ {b} — {len(sel)} day{'s' if len(sel) != 1 else ''}", "",
              f"Slots: {tot['same']} same · {tot['alleluia']} alleluia · {tot['common']} common · "
              f"{tot['variant']} variant · {tot['differs']} differ · {tot['only_a']} only in {a} · "
              f"{tot['only_b']} only in {b}", "",
              f"| Day key | {a} pages | {b} pages | Form in {a} | Same | Alleluia | Common | Variant | Differs | "
              f"Only {a} | Only {b} | Texts agree |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, _, k, pa, pb, form, c in sel:
            agree = "yes" if not (c["differs"] or c["variant"]) else "**no**"
            L.append(f"| `{k}` | {pa[0]}–{pa[1]} | {pb[0]}–{pb[1]} | {form or 'full'} | {c['same']} | {c['alleluia']} | "
                     f"{c['common']} | {c['variant']} | {c['differs']} | {c['only_a']} | {c['only_b']} | {agree} |")
        L.append("")
    if key_mismatch:
        L += ["## Same date, different day key", "",
              "| Volumes | Key in A | Keys in B on that date |", "|---|---|---|"]
        L += [f"| {a} / {b} | `{k}` | {', '.join(f'`{x}`' for x in ks)} |" for a, b, k, ks in key_mismatch]
        L.append("")
    if details:
        L += ["## Texts to review (TODO.md §3 T-SANCT)", "",
              "| Kind | Volumes | Day key | Hour / slot | A (page) | B (page) |", "|---|---|---|---|---|---|"]
        for a, b, k, (kind, sk, pa, ta, pb, tb) in details:
            slot = f"{sk[0]} {sk[1]}" + (f" {sk[2]}" if sk[2] else "") + (" (alt)" if sk[3] else "")
            L.append(f"| {kind} | {a} / {b} | `{k}` | {slot} | {a} {pa}: {ta[:160].replace('|', '/')} | "
                     f"{b} {pb}: {tb[:160].replace('|', '/')} |")
        L.append("")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "sanctis_overlaps.md").write_text("\n".join(L) + "\n", encoding="utf-8")
