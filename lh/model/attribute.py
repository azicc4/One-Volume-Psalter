"""WS6 attribution: give every object one HOME — the one place in the book where it is printed in full — and record
the references that replace its other printings.

Priority (docs/architecture.md): Ordinary → Psalter (psalms, canticles) → Hymns → Proper of Time → Commons →
Proper of Saints → Office of Readings readings. Hymns, psalms/canticles and Office of Readings readings/responsories
have their section by type; every other object is printed at the first *location* (book order within the priority)
where it is used. A location is an hour-sized place in the book:

  ord:<CHAPTER>:<hour>         Ordinary chapter (invitatory psalms, dismissals, complementary psalmody, Marian …)
  ord:compline:<FORM>          weekly Compline cycle SAT1 (after I Vespers) SUN MON … FRI; EASTER (Easter Octave)
  psalter:ps:<NNN>             psalm NNN (Hebrew number)          psalter:cant:<key>   canticle
  hymns:<group>                Hymns section
  time:grid:<pw>.<DOW>:<hour>  four-week grid of the Proper of Time (all seasons side by side)
  time:otweek:<NN>             Ordinary Time, proper of week NN (Sunday Gospel antiphons A/B/C, collect)
  time:day:<DAY>:<hour>        wholly proper day of the Proper of Time (17-24 Dec, Christmas, Holy Week …)
  com:<DAY>:<hour>             Commons, Office of the Dead, Saturday memorial of the BVM
  sanct:<DAY>:<hour>           Proper of Saints
  read:<DAY>                   Office of Readings readings (ribbon 10), in liturgical order

Results: object.home (section) and object.home_label (location); table `reference` for the printings replaced by a
reference of a named kind (de_communi, de_feria, grid). `python -m lh build` runs this after the overrides; the book
generator (lh/render/book.py) prints each object where object.home_label says and refers to it everywhere else.
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3

SECTIONS = ["ordinary", "psalter", "hymns", "time", "commons", "saints", "readings"]
INLINE = {"rubric", "link", "ordinary_ref", "unparsed"}       # printed where they stand (instructions), never homed
WD = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
HOURS = ["V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "V2", "COMPLINE", "APPX"]
GRID_RE = re.compile(r"^(OT|ADV|LENT|EAS)\.(\d+)\.(SUN|MON|TUE|WED|THU|FRI|SAT)$")
ORD_RE = re.compile(r"^(?:(?:PA|ADV|LQP|COM|SPA|SP|SQ|SADV)\.)?ORD\.(.+)$")
SOURCE_ORDER = {"PA": 0, "LQP": 1, "ADV": 2, "COM": 3, "SPA": 4, "SP": 5, "SQ": 6, "SADV": 7}

# Ordinary chapters in book order (normalised: ADV.ORD.INVITATORY → INVITATORY; SPA.ORD.DIMISSIO → DISMISSAL)
ORD_ORDER = ["fixed", "COMPLEMENTARY", "COMPLEMENTARY_NO_ANT", "INVITATORY", "MIDDAY_HYMNS", "MIDDAY_HYMNS_ALT",
             "AD_TERTIAM_SEXTAM_ET_NONAM", "DISMISSAL", "DISMISSAL_EASTER", "MARIAN",
             "compline:SAT1", "compline:SUN", "compline:MON", "compline:TUE", "compline:WED", "compline:THU",
             "compline:FRI", "compline:EASTER", "COMPLETORIUM", "COMPLINE_HYMNS", "SUNDAY_WK1_PSALMS"]
COMMON_ORDER = ["COMMON.DEDICATION", "COMMON.BVM", "COMMON.APOSTLES", "COMMON.MARTYRS.SEVERAL", "COMMON.MARTYRS.ONE",
                "COMMON.PASTORS", "COMMON.DOCTORS", "COMMON.VIRGINS", "COMMON.HOLY_MEN", "COMMON.HOLY_WOMEN",
                "DEAD", "MEM.BVM_SATURDAY"]
EASTER_OCTAVE = re.compile(r"^EAS\.(1\.SUN|OCT\.\w+)$")

# wholly proper days of the Proper of Time, in book order
PROPER_DAYS = (
    [f"ADV.DEC{d}" for d in range(17, 25)] + ["ADV.PROP.CANTICA_ET_EVANGELIA_PRO_VIGILIA", "SOL.CHRISTMAS"]
    + [f"CHR.DEC{d}" for d in range(26, 32)] + ["FEAST.HOLY_FAMILY", "SOL.MARY_MOTHER_OF_GOD", "CHR.2.SUN"]
    + [f"CHR.JAN{d:02d}" for d in range(2, 8)] + ["SOL.EPIPHANY"] + [f"CHR.POSTEPI.JAN{d:02d}" for d in range(7, 13)]
    + ["FEAST.BAPTISM"] + [f"LENT.0.{w}" for w in ("WED", "THU", "FRI", "SAT")]
    + [f"HOLY.{w}" for w in ("SUN", "MON", "TUE", "WED", "THU")] + [f"TRIDUUM.{w}" for w in ("THU", "FRI", "SAT")]
    + ["EAS.1.SUN"] + [f"EAS.OCT.{w}" for w in WD[1:]] + ["SOL.ASCENSION", "SOL.PENTECOST",
                                                       "SOL.TRINITY", "SOL.CORPUS_CHRISTI", "SOL.SACRED_HEART",
                                                       "SOL.CHRIST_KING"])


# ============================================================================================ day classification

def ord_chapter(key: str) -> str | None:
    if key == "LQP.PROP.COMPLETORIUM_AD_OCTAVAM_PASCHAE":
        return "compline:EASTER"
    if key == "LQP.PROP.DIMISSIO_IN_DIEBUS_INFRA_OCTAVAM":
        return "DISMISSAL_EASTER"
    m = ORD_RE.match(key)
    if not m:
        return None
    return {"DIMISSIO": "DISMISSAL"}.get(m.group(1), m.group(1))


def is_grid(day) -> bool:
    m = GRID_RE.match(day["key"])
    return bool(m) and int(m.group(2)) >= 1 and bool(day["psalter_week"])


def day_section(key: str) -> str:
    if ord_chapter(key):
        return "ordinary"
    if key == "PROP.HYMNS_AD_LIBITUM" or "HYMNI_AD_LIBITUM" in key:
        return "hymns"
    if key.startswith(("COMMON.", "MEM.")) or key == "DEAD":
        return "commons"
    if key.startswith("SANCT.") or key == "SOL.IMMACULATE_CONCEPTION":
        return "saints"
    return "time"


def saint_date(key: str) -> str:
    if key == "SOL.IMMACULATE_CONCEPTION":
        return "12-08"
    m = re.match(r"^SANCT\.(\d\d-\d\d)\.", key)
    return m.group(1) if m else "99-99"


def compline_form(day, hour: str) -> str | None:
    """Weekly Compline form of a Compline hour, or None when it belongs to its own day."""
    if hour not in ("COMPLINE", "COMPLINE1"):
        return None
    if is_grid(day):
        return "SAT1" if hour == "COMPLINE1" else day["weekday"]
    if EASTER_OCTAVE.match(day["key"]):
        return "EASTER"
    return None


def location(day, hour: str, slot: str) -> str:
    """Book location of an occurrence in (day, hour, slot) — see the module docstring."""
    key = day["key"]
    if slot in ("OPENING", "PREP_PRAYER"):
        return "ord:fixed"                  # abbreviated opening verses, preparatory prayer: Ordinary, "Opening"
    sec = day_section(key)
    form = compline_form(day, hour) if sec == "time" else None
    if form:
        return f"ord:compline:{form}"
    if sec == "ordinary":
        chap = ord_chapter(key)
        return f"ord:{chap}" if chap.startswith("compline:") else f"ord:{chap}:{hour}"
    if sec == "hymns":
        return "hymns:adlib"
    if sec == "commons":
        return f"com:{key}:{hour}"
    if sec == "saints":
        return f"sanct:{key}:{hour}"
    if is_grid(day):
        wk = day["week"]
        if day["season"] == "OT" and (slot == "ORATIO" and (day["weekday"] == "SUN" or hour == "OR")
                                      or slot == "GOSPEL_ANT" and day["weekday"] == "SUN"):
            return f"time:otweek:{wk:02d}"
        return f"time:grid:{day['psalter_week']}.{day['weekday']}:{hour}"
    return f"time:day:{key}:{hour}"


def hour_rank(hour: str) -> int:
    return HOURS.index(hour) if hour in HOURS else len(HOURS)


# ============================================================================================ book order

def time_order(days: list) -> dict[str, int]:
    """Liturgical-year order of the days of the Proper of Time (drives the readings section and claims)."""
    keys = {d["key"]: d for d in days}
    out: list[str] = []

    def grid(season, weeks):
        for w in weeks:
            for wd in WD:
                k = f"{season}.{w if season != 'OT' else f'{w:02d}'}.{wd}"
                if k in keys:
                    out.append(k)
    grid("ADV", range(1, 5))
    out += [k for k in PROPER_DAYS[:PROPER_DAYS.index("FEAST.BAPTISM") + 1]]
    out += [f"LENT.0.{w}" for w in ("WED", "THU", "FRI", "SAT")]
    grid("LENT", range(1, 6))
    out += [k for k in PROPER_DAYS if k.startswith(("HOLY.", "TRIDUUM."))] + ["EAS.1.SUN"]
    out += [f"EAS.OCT.{w}" for w in WD[1:]]
    for w in range(2, 8):
        for wd in WD:
            out.append(f"EAS.{w}.{wd}")
            if (w, wd) == (6, "WED"):
                out.append("SOL.ASCENSION")
    out += ["SOL.PENTECOST", "SOL.TRINITY", "SOL.CORPUS_CHRISTI", "SOL.SACRED_HEART"]
    for w in range(1, 35):
        grid("OT", [w])
        if w == 33:
            out.append("SOL.CHRIST_KING")
    seen, order = set(), []
    for k in out:
        if k in keys and k not in seen and day_section(k) == "time":
            seen.add(k)
            order.append(k)
    for k in sorted(keys):                          # anything not placed above
        if k not in seen and day_section(k) == "time":
            order.append(k)
    return {k: i for i, k in enumerate(order)}


def saints_order(con) -> list[str]:
    """Proper of Saints days by date, in printing order within a date; movable celebrations last."""
    rows = con.execute("""SELECT d.key, min(h.id) AS first FROM day d JOIN hour_instance h ON h.day_key = d.key
                          GROUP BY d.key""").fetchall()
    keys = [(saint_date(k), first, k) for k, first in rows if day_section(k) == "saints"]
    return [k for _, _, k in sorted(keys)]


class Order:
    """Ranks locations in claim order: Ordinary, Proper of Time (grid, OT weeks, proper days), Commons, Saints."""

    def __init__(self, con):
        days = [dict(r) for r in con.execute("SELECT * FROM day")]
        self.time = time_order(days)
        self.proper = {k: i for i, k in enumerate(PROPER_DAYS)}
        self.saints = {k: i for i, k in enumerate(saints_order(con))}
        self.commons = {k: i for i, k in enumerate(COMMON_ORDER)}

    def loc_rank(self, loc: str) -> tuple:
        p = loc.split(":")
        if p[0] == "ord":
            chap = ":".join(p[1:3]) if p[1] == "compline" else p[1]
            return (0, ORD_ORDER.index(chap) if chap in ORD_ORDER else len(ORD_ORDER), chap,
                    hour_rank(p[2]) if p[1] != "compline" and len(p) > 2 else 0)
        if p[0] == "psalter":
            return (1, loc)
        if p[0] == "hymns":
            return (2, loc)
        if p[0] == "time":
            if p[1] == "grid":
                pw, wd = p[2].split(".")
                return (3, 0, int(pw), WD.index(wd), hour_rank(p[3]))
            if p[1] == "otweek":
                return (3, 1, int(p[2]))
            return (3, 2, self.proper.get(p[2], 999), p[2], hour_rank(p[3]))
        if p[0] == "com":
            return (4, self.commons.get(p[1], 99), p[1], hour_rank(p[2]))
        if p[0] == "sanct":
            return (5, self.saints.get(p[1], 9999), p[1], hour_rank(p[2]))
        if p[0] == "read":
            return (6, self.read_rank(p[1]))
        return (9, loc)

    def read_rank(self, day_key: str) -> tuple:
        if day_key in self.time:
            return (0, self.time[day_key])
        if day_key in self.commons:
            return (1, self.commons[day_key])
        if day_key in self.saints:
            return (2, self.saints[day_key])
        return (3, day_key)


# ============================================================================================ instances / content

def instances(con, day_key: str, hour: str) -> list:
    """Printed instances of a (day, hour), base printing first: the main printing (no copy label) of the first
    volume; Commons: the Per annum copy; Advent/Christmas: the earliest start-date copy."""
    rows = con.execute("SELECT * FROM hour_instance WHERE day_key=? AND hour=?", (day_key, hour)).fetchall()

    def k(h):
        cp = h["copy"] or ""
        return (cp != "" and cp != "OT", SOURCE_ORDER.get(h["source"], 9), cp.startswith(("altera", "commemoratio")),
                h["id"])
    return sorted(rows, key=k)


def content(occs) -> list:
    """Occurrences that carry a printable text (not rubrics/links, not repeated antiphons already printed)."""
    out, seen = [], set()
    for o in occs:
        if not o["object_id"] or o["type"] in INLINE:
            continue
        if (o["slot"] or "").endswith("_R") and o["object_id"] in seen:
            continue
        seen.add(o["object_id"])
        out.append(o)
    return out


def type_home(otype: str, payload: dict) -> tuple[str, str | None]:
    """Sections fixed by type; None location = decided by use (first use in book order)."""
    from lh.model.canon import psalm_base
    if otype == "hymn":
        return "hymns", None
    if otype == "psalm":
        if any(l.get("refrain") for l in payload.get("lines", [])):
            return "ordinary", "ord:INVITATORY:APPX"
        return "psalter", f"psalter:ps:{psalm_base(payload['psalm']):03d}"
    if otype == "canticle":
        if payload.get("gospel"):
            return "ordinary", "ord:gospel"
        return "psalter", "psalter:cant"
    if otype == "te_deum":
        return "ordinary", "ord:tedeum"
    if otype == "prayer":
        return "ordinary", "ord:fixed"
    if otype in ("reading", "responsory"):
        return "readings", None
    return "", None


SECTION_OF_LOC = {"ord": "ordinary", "psalter": "psalter", "hymns": "hymns", "time": "time", "com": "commons",
                  "sanct": "saints", "read": "readings"}


# ============================================================================================ attribution

def attribute(con: sqlite3.Connection) -> dict:
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("PRAGMA table_info(object)")}
    if "home_label" not in cols:
        con.execute("ALTER TABLE object ADD COLUMN home_label TEXT")
    con.execute("DROP TABLE IF EXISTS reference")
    con.execute("""CREATE TABLE reference (hour_id INTEGER, slot TEXT, sub TEXT, object_id TEXT, kind TEXT,
                   target TEXT, target_home TEXT)""")
    order = Order(con)
    days = {r["key"]: r for r in con.execute("SELECT * FROM day")}
    objs = {r["id"]: (r["type"], json.loads(r["payload"])) for r in con.execute("SELECT id, type, payload FROM object")}
    best: dict[str, tuple] = {}              # object -> (rank, location) of its first use
    uses = collections.Counter()
    by_hour: dict[int, list] = {}
    hours = con.execute("SELECT * FROM hour_instance").fetchall()
    occ_by_hour = collections.defaultdict(list)
    for o in con.execute("SELECT * FROM occurrence ORDER BY hour_id, seq"):
        occ_by_hour[o["hour_id"]].append(o)
    for h in hours:
        d = days[h["day_key"]]
        cont = content(occ_by_hour[h["id"]])
        by_hour[h["id"]] = cont
        for o in cont:
            oid = o["object_id"]
            uses[oid] += 1
            otype = objs[oid][0]
            if otype in ("reading", "responsory"):
                loc = f"read:{d['key']}"
            else:
                loc = location(d, h["hour"], o["slot"] or "")
            r = order.loc_rank(loc)
            if oid not in best or r < best[oid][0]:
                best[oid] = (r, loc)
    rows, stats = [], collections.Counter()
    homes: dict[str, tuple[str, str]] = {}
    for oid, (otype, payload) in objs.items():
        if otype in INLINE:
            homes[oid] = ("inline", None)
            continue
        sec, loc = type_home(otype, payload)
        if loc is None:
            loc = best[oid][1] if oid in best else None
        if not sec:
            sec = SECTION_OF_LOC[loc.split(":")[0]] if loc else "unused"
        if otype == "hymn" and oid in best:
            loc = "hymns:" + best[oid][1]                 # grouped by its first use
        homes[oid] = (sec, loc)
        stats[sec] += 1
    con.executemany("UPDATE object SET home=?, home_label=? WHERE id=?",
                    [(s, l, oid) for oid, (s, l) in homes.items()])
    # ---------------------------------------------------------------- references of a named kind
    refs = []
    hours_by_key = collections.defaultdict(list)
    for h in hours:
        hours_by_key[(h["day_key"], h["hour"])].append(h)
    # commons: (hour, slot, sub, object) -> common day keys printing it there
    common_at = collections.defaultdict(set)
    for h in hours:
        if h["day_key"].startswith("COMMON."):
            for o in by_hour[h["id"]]:
                common_at[(h["hour"], o["slot"], o["object_id"])].add(h["day_key"])
    # grid cells: psalm units of each (pw, weekday, hour) in Ordinary Time → for "psalmi de feria"
    cell_units = collections.defaultdict(set)
    for h in hours:
        d = days[h["day_key"]]
        if d["season"] == "OT" and is_grid(d) and h["hour"] not in ("COMPLINE", "COMPLINE1"):
            units = tuple(o["object_id"] for o in by_hour[h["id"]] if re.fullmatch(r"PS\d", o["slot"] or ""))
            if units:
                cell_units[units].add(f"time:grid:{d['psalter_week']}.{d['weekday']}:{h['hour']}")
    ot_cell_objs = collections.defaultdict(set)          # grid cell -> objects of its Ordinary Time days
    for h in hours:
        d = days[h["day_key"]]
        if d["season"] == "OT" and is_grid(d):
            loc = location(d, h["hour"], "")
            for o in by_hour[h["id"]]:
                ot_cell_objs[(loc, o["slot"], o["sub"] or "")].add(o["object_id"])
    for h in hours:
        d = days[h["day_key"]]
        sec = day_section(d["key"])
        cont = by_hour[h["id"]]
        if sec in ("saints", "commons"):
            units = tuple(o["object_id"] for o in cont if re.fullmatch(r"PS\d", o["slot"] or ""))
            cells = cell_units.get(units)
            if units and cells:
                cell = sorted(cells, key=order.loc_rank)[0]
                for o in cont:
                    if re.fullmatch(r"PS\d", o["slot"] or ""):
                        refs.append((h["id"], o["slot"], o["sub"], o["object_id"], "de_feria", cell,
                                     homes[o["object_id"]][1]))
        if sec == "saints":
            # the Common this saint draws on most, for ties between several Commons
            tally = collections.Counter()
            for o in cont:
                for ck in common_at.get((h["hour"], o["slot"], o["object_id"]), ()):
                    tally[ck] += 1
            for o in cont:
                if objs[o["object_id"]][0] in ("psalm", "canticle"):
                    continue
                cks = common_at.get((h["hour"], o["slot"], o["object_id"]))
                if cks:
                    ck = max(cks, key=lambda c: (tally[c], -COMMON_ORDER.index(c) if c in COMMON_ORDER else 0))
                    refs.append((h["id"], o["slot"], o["sub"], o["object_id"], "de_communi", ck,
                                 homes[o["object_id"]][1]))
        if sec == "time" and is_grid(d) and d["season"] != "OT" and h["hour"] not in ("COMPLINE", "COMPLINE1"):
            loc = location(d, h["hour"], "")
            for o in cont:
                if o["object_id"] in ot_cell_objs.get((loc, o["slot"], o["sub"] or ""), ()):
                    refs.append((h["id"], o["slot"], o["sub"], o["object_id"], "grid", loc,
                                 homes[o["object_id"]][1]))
    con.executemany("INSERT INTO reference VALUES (?,?,?,?,?,?,?)", refs)
    kinds = collections.Counter(r[4] for r in refs)
    printed = sum(n for s, n in stats.items() if s in SECTIONS)
    n_uses = sum(uses[o] for o, (s, _) in homes.items() if s in SECTIONS)
    summary = {"objects_printed": printed, "by_section": dict(stats), "uses": n_uses,
               "references": n_uses - printed, "kinds": dict(kinds),
               "de_communi_hours": len({r[0] for r in refs if r[4] == "de_communi"})}
    return summary
