"""Shared pieces of the book generators (proof of concept `poc.py`, full book `book.py`): data access with in-memory
caches, the seasonal variant grid, page references, and the Psalter / Canticles writer with margin notes."""
from __future__ import annotations

import collections
import json
import re
import sqlite3
from dataclasses import dataclass

import yaml

from lh.config import DB_PATH, SEED
from lh.model.attribute import INLINE, instances as _instances
from lh.model.canon import plain, psalm_base, unit_verses
from lh.psalter.refs import fmt, parse_ref, psalm_ranges
from lh.render import latex as L
from lh.render.latex import esc, label, tex

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
HOURCODE = {"OR": "OR", "LAUDS": "L", "MIDDAY": "D", "VESPERS": "V", "V1": "1V", "V2": "2V", "INV": "Inv"}
DAYABBR = {"SUN": "Sun", "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu", "FRI": "Fri", "SAT": "Sat"}
SEASON_LABEL = {"OT": "OT", "ADV": "Adv.", "LENT": "Lent", "EAS": "Easter"}
SEASON_ORDER = {"OT": 0, "ADV": 1, "LENT": 2, "EAS": 3}
HOUR_TITLE = {"V1": "First Vespers", "COMPLINE1": "Compline after First Vespers", "INV": "Invitatory",
              "OR": "Office of Readings", "LAUDS": "Lauds", "MIDDAY": "Daytime Prayer", "VESPERS": "Vespers",
              "V2": "Second Vespers", "COMPLINE": "Compline", "APPX": ""}
SUB_TITLE = {"TERCE": "Terce", "SEXT": "Sext", "NONE": "None"}
GOSPEL = {"LAUDS": "Benedictus", "VESPERS": "Magnificat", "V1": "Magnificat", "V2": "Magnificat", "COMPLINE": "Nunc dimittis",
          "COMPLINE1": "Nunc dimittis"}

VESPERS_SLOTS = ["HYMN", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3", "LB", "RB", "GOSPEL_ANT", "PRECES", "ORATIO"]
SLOT_ORDER = {
    "INV": ["INV_ANT"],
    "OR": ["HYMN", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3", "OR_VERSE", "LECT1", "LECT2", "ORATIO"],
    "LAUDS": VESPERS_SLOTS, "VESPERS": VESPERS_SLOTS, "V1": VESPERS_SLOTS, "V2": VESPERS_SLOTS,
    "MIDDAY": [("HYMN", "TERCE"), ("ANT", "TERCE"), ("HYMN", "SEXT"), ("ANT", "SEXT"), ("HYMN", "NONE"), ("ANT", "NONE"),
               "ANT", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3",
               ("LB", "TERCE"), ("V", "TERCE"), ("ORATIO", "TERCE"), ("LB", "SEXT"), ("V", "SEXT"), ("ORATIO", "SEXT"),
               ("LB", "NONE"), ("V", "NONE"), ("ORATIO", "NONE")],
    "COMPLINE": ["HYMN", "ANT", "ANT1", "PS1", "ANT2", "PS2", "LB", "RB", "GOSPEL_ANT", "ORATIO", "BLESSING", "MARIAN"],
}
SLOT_ORDER["COMPLINE1"] = SLOT_ORDER["COMPLINE"]
SLOT_NAME = {"HYMN": "Hymn", "ANT": "Antiphon", "ANT1": "Ant. 1", "ANT2": "Ant. 2", "ANT3": "Ant. 3", "PS1": "Psalm 1",
             "PS2": "Psalm 2", "PS3": "Psalm 3", "LB": "Short reading", "RB": "Short responsory",
             "GOSPEL_ANT": "Gospel canticle antiphon", "PRECES": "Intercessions", "ORATIO": "Concluding prayer",
             "INV_ANT": "Invitatory antiphon", "OR_VERSE": "Versicle", "V": "Versicle", "LECT1": "First reading",
             "LECT2": "Second reading", "RESP1": "Responsory", "RESP2": "Responsory", "TE_DEUM": "Te Deum",
             "BLESSING": "Blessing", "MARIAN": "Antiphon of the Blessed Virgin Mary", "OPENING": "Opening",
             "GOSPEL": "Gospel", "VR": "Versicle", "TEXT": "Text", "PREP_PRAYER": "Preparatory prayer",
             "LECT3": "Third reading", "LECT4": "Fourth reading", "GOSPEL_CANT": "Gospel canticle"}
COND_LABEL = {"year": lambda v: f"Year {v}:", "variant": lambda v: {"night": "At night or early morning:",
                                                                    "day": "During the day:"}.get(v, v),
              "alt": lambda v: "Or:" if v.strip().lower() in ("vel:", "vel", "aut:", "aut") else v,
              "for": lambda v: v if v.endswith(":") else v + ":",
              "choice": lambda v: f"{v}."}


def con():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ============================================================================================ data access

@dataclass
class Obj:
    id: str
    type: str
    payload: dict
    n_occ: int = 0
    home: str | None = None
    home_label: str | None = None


class DB:
    """Read-only access to build/lh.sqlite with in-memory caches (the full book touches every hour many times)."""

    def __init__(self):
        self.c = con()
        self._obj: dict[str, Obj] = {}
        self._occ: dict[int, list] = collections.defaultdict(list)
        for o in self.c.execute("SELECT * FROM occurrence ORDER BY hour_id, seq"):
            self._occ[o["hour_id"]].append(o)
        self._inst: dict[tuple, list] = {}
        self.day_rows = {r["key"]: r for r in self.c.execute("SELECT * FROM day")}
        cols = {r[1] for r in self.c.execute("PRAGMA table_info(object)")}
        self.has_home = "home_label" in cols

    def obj(self, oid: str) -> Obj:
        if oid not in self._obj:
            cols = "id, type, payload, n_occ" + (", home, home_label" if self.has_home else "")
            r = self.c.execute(f"SELECT {cols} FROM object WHERE id=?", (oid,)).fetchone()
            self._obj[oid] = Obj(r["id"], r["type"], json.loads(r["payload"]), r["n_occ"],
                                 r["home"] if self.has_home else None, r["home_label"] if self.has_home else None)
        return self._obj[oid]

    def load_all(self):
        cols = "id, type, payload, n_occ" + (", home, home_label" if self.has_home else "")
        for r in self.c.execute(f"SELECT {cols} FROM object"):
            if r["id"] not in self._obj:
                self._obj[r["id"]] = Obj(r["id"], r["type"], json.loads(r["payload"]), r["n_occ"],
                                         r["home"] if self.has_home else None, r["home_label"] if self.has_home else None)
        return self._obj

    def days(self, pw: int, wd: str):
        return self.c.execute("""SELECT * FROM day WHERE psalter_week=? AND weekday=? AND season IN ('OT','ADV','LENT','EAS')
                                 AND key NOT LIKE 'ADV.DEC%' AND key NOT LIKE 'LENT.0.%' AND key NOT LIKE 'HOLY.%'
                                 AND week >= 1 ORDER BY season, week""", (pw, wd)).fetchall()

    def instances(self, day_key: str, hour: str) -> list:
        k = (day_key, hour)
        if k not in self._inst:
            self._inst[k] = _instances(self.c, day_key, hour)
        return self._inst[k]

    def hour(self, day_key: str, hour: str):
        ins = self.instances(day_key, hour)
        return ins[0] if ins else None

    def occ(self, hour_id: int):
        return self._occ.get(hour_id, [])


# ============================================================================================ variant grid

def day_tag(d) -> tuple[str, int]:
    return d["season"], d["week"]


def cond_text(cond_json: str | None) -> str:
    if not cond_json:
        return ""
    c = json.loads(cond_json)
    for k in ("year", "variant", "for", "alt", "choice"):
        if c.get(k):
            return COND_LABEL[k](str(c[k]))
    return ""


def labels_for(days: list, all_ot: set[int]) -> str:
    by = collections.defaultdict(list)
    for d in days:
        by[d["season"]].append(d["week"])
    parts = []
    for s in sorted(by, key=lambda s: SEASON_ORDER[s]):
        weeks = sorted(set(by[s]))
        if s == "OT" and set(weeks) == all_ot and len(all_ot) > 1:
            parts.append("Per annum")
        else:
            parts.append(f"{SEASON_LABEL[s]} {', '.join(map(str, weeks))}")
    return " · ".join(parts)


@dataclass
class Group:
    days: list
    items: list           # [(cond_text, object_id)]
    label: str = ""


def slot_groups(db: DB, days: list, hour: str, slot: str, sub: str) -> list[Group]:
    """Group the days of a grid cell by the texts they have in one slot (all printings of each day merged)."""
    per_day = {}
    for d in days:
        items = []
        for h in db.instances(d["key"], hour):
            for o in db.occ(h["id"]):
                if o["slot"] == slot and (o["sub"] or "") == sub and o["object_id"] and o["type"] not in INLINE:
                    items.append((cond_text(o["cond"]), o["object_id"]))
        if items:
            seen, uniq = set(), []
            for it in items:
                if it not in seen:
                    seen.add(it)
                    uniq.append(it)
            per_day[d["key"]] = (d, tuple(uniq))
    groups: dict[tuple, Group] = {}
    for d, items in per_day.values():
        groups.setdefault(items, Group([], list(items))).days.append(d)
    all_ot = {d["week"] for d in days if d["season"] == "OT"}
    out = list(groups.values())
    for g in out:
        g.label = labels_for(g.days, all_ot)
    out.sort(key=lambda g: (min(SEASON_ORDER[d["season"]] for d in g.days), min(d["week"] or 0 for d in g.days)))
    return out


# ============================================================================================ references

def psalm_unit_ref(p: dict) -> str:
    base = psalm_base(p["psalm"])
    verses, starts_mid = unit_verses(p["lines"])
    nums = sorted({int(re.match(r"\(?(\d+)", v).group(1)) for v in verses if re.match(r"\(?\d", v)})
    if starts_mid and nums:
        nums = [nums[0] - 1] + nums
    rng = fmt("Ps", psalm_ranges(base, [str(n) for n in nums])).replace("Ps ", "")
    return f"Ps {rng}"


def canticle_ref(p: dict) -> str:
    try:
        b, r, _ = parse_ref(p["ref"])
        return fmt(b, r).replace("-end", "ff.")
    except ValueError:
        return p["ref"]


def unit_anchor(o: Obj) -> str:
    """LaTeX label of the place an object is printed: psalm portions are labelled inside the psalm (psu:)."""
    if o.type == "psalm" and o.home in (None, "psalter"):
        return label("psu:" + o.id)
    return label(o.id)


def obj_ref(db: DB, oid: str) -> str:
    """POC style: psalms/canticles/hymns/readings by page; other (short) texts printed again in place."""
    o = db.obj(oid)
    p = o.payload
    if o.type == "psalm":
        return f"{esc(psalm_unit_ref(p))} {{\\footnotesize ({esc(p['vulg'])})}}\\enspace\\seepage{{{unit_anchor(o)}}}"
    if o.type == "canticle":
        return f"Canticle {esc(canticle_ref(p))}\\enspace\\seepage{{{label(oid)}}}"
    if o.type == "hymn":
        return f"\\textit{{{tex(p['stanzas'][0][0], marks=False)}}}\\enspace\\seepage{{{label(oid)}}}"
    if o.type == "reading":
        intro = plain(" ".join(p.get("intro", []))) or plain(p["lines"][0][1])[:60]
        return f"{{\\small {esc(intro)}}}\\enspace\\seepage{{{label(oid)}}}"
    return L.render(o.type, p)


# ============================================================================================ psalter writer

def cant_key(ref: str) -> str:
    """Canticle identity across printing variants ('Ap 11, 17-18; 12, 10 b-12 a' = 'Ap 11, 17-18; 12, 10b-12a')."""
    from lh.model.canon import canticle_slug
    return re.sub(r"[^a-z0-9-]", "", canticle_slug(ref))


class PsalterWriter:
    """Psalter (all psalms, consensus text from psalm_verse) and Canticles with margin notes of their uses."""

    db: DB
    OTHER_MAX = 10          # margin lines for "other uses" (compaction of long lists: TODO B-9)

    def use_codes(self, rows) -> tuple[list, list]:
        """psalm_use-like rows → (four-week-cycle codes, other uses each as its own line), deduplicated in order."""
        cycle, other = [], []
        for r in rows:
            m = re.match(r"PS(\d+)", r["slot"] or "")
            n = m.group(1) if m else ""
            hc = HOURCODE.get(r["hour"], "C" if r["hour"].startswith("COMPLINE") else r["hour"])
            code, is_cycle = None, True
            key = r["day_key"]
            if r["hour"] in ("COMPLINE", "COMPLINE1"):
                if not (r["season"] == "OT" and r["rank"] in ("sunday", "weekday")):
                    continue       # Compline of solemnities/seasons repeats the weekly cycle (Sunday Compline)
                code = "C " + ("Sat" if r["hour"] == "COMPLINE1" else DAYABBR[r["weekday"]])
            elif r["season"] == "OT" and r["rank"] in ("sunday", "weekday") and r["psalter_week"]:
                code = f"{ROMAN[r['psalter_week']]} {DAYABBR[r['weekday']]} {hc}.{n}"
            elif key.endswith("ORD.INVITATORY"):
                code = "Inv"
            elif "ORD.COMPLEMENTARY" in key:
                code = None if key.endswith("NO_ANT") else f"Compl.{n}"
            elif r["season"] in ("ADV", "LENT", "EAS") and r["rank"] in ("sunday", "weekday", "privileged_weekday") and r["psalter_week"]:
                continue       # same psalter-week use as Ordinary Time
            elif key.startswith("SANCT.") or key == "SOL.IMMACULATE_CONCEPTION":
                code, is_cycle = f"Saints {hc}.{n}", False
            elif key.startswith("COMMON."):
                code, is_cycle = f"Commons {hc}.{n}", False
            elif key == "DEAD":
                code, is_cycle = f"Dead {hc}.{n}", False
            elif key.startswith("MEM."):
                code, is_cycle = f"BVM Sat {hc}.{n}", False
            elif "ORD." not in key and "PROP." not in key:
                code, is_cycle = f"{r['short'] or r['title']} {hc}.{n}".rstrip("."), False
            if code:
                bucket = cycle if is_cycle else other
                if code not in bucket:
                    bucket.append(code)
        if len(other) > self.OTHER_MAX:
            other = other[:self.OTHER_MAX - 1] + [f"+ {len(other) - self.OTHER_MAX + 1} more"]
        return cycle, other

    def margin_codes(self, num: int) -> dict:
        """unit object id → (cycle codes, other uses) for every printing of that psalm portion."""
        rows = self.db.c.execute("""SELECT u.unit, u.day_key, u.hour, u.slot, u.psalter_week, u.weekday, d.season, d.rank,
                                           d.title, d.short
                                    FROM psalm_use u JOIN day d ON d.key=u.day_key WHERE u.psalm=? ORDER BY u.rowid""",
                                 (num,)).fetchall()
        by_unit = collections.defaultdict(list)
        for r in rows:
            by_unit[r["unit"]].append(r)
        return {u: self.use_codes(rs) for u, rs in by_unit.items()}

    @staticmethod
    def margin_note(cycle: list, other: list, rng: str = "") -> str:
        parts = r"\\ ".join(esc(c) for c in cycle)
        if rng:
            parts += esc(rng)
        if other:
            parts += (r"\otheruses " if cycle else "") + r"\\ ".join(esc(o) for o in other)
        return r"\usemark{" + parts + "}" if parts else ""

    def psalm_objects(self, num: int) -> list[Obj]:
        if not hasattr(self, "_psalm_objs"):
            self._psalm_objs = collections.defaultdict(list)
            for r in self.db.c.execute("SELECT id FROM object WHERE type='psalm'"):
                o = self.db.obj(r["id"])
                self._psalm_objs[psalm_base(o.payload["psalm"])].append(o)
        return self._psalm_objs.get(num, [])

    def strophe_breaks(self, num: int) -> set[tuple]:
        """(verse, k) keys preceded by a strophe break in the majority of printings (page breaks excluded)."""
        votes = collections.Counter()
        totals = collections.Counter()
        ids = [o.id for o in self.psalm_objects(num)]
        rows = []
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            rows += self.db.c.execute(f"""SELECT object_id, extra FROM occurrence WHERE object_id IN
                                          ({','.join('?' * len(chunk))})""", chunk).fetchall()
        for r in rows:
            p = self.db.obj(r["object_id"]).payload
            brk = {int(k): v for k, v in json.loads(r["extra"] or "{}").get("brk", {}).items()}
            v, k = None, 0
            for i, l in enumerate(p["lines"]):
                if l["v"]:
                    v, k = l["v"], 0
                else:
                    k += 1
                if i == 0:
                    continue
                totals[(v, k)] += 1
                if brk.get(i) == "block":
                    votes[(v, k)] += 1
        return {key for key, n in votes.items() if n * 2 > totals[key]}

    def unit_starts(self, num: int, rows) -> dict[int, list[str]]:
        """row index in psalm_verse order → unit ids starting there (matched by line text sequence)."""
        texts = [r["text"] for r in rows]
        out = collections.defaultdict(list)
        for o in self.psalm_objects(num):
            if o.home not in (None, "psalter"):
                continue
            first = [l["t"] for l in o.payload["lines"] if not l.get("refrain")][:2]
            if not first:
                continue
            for i in range(len(texts)):
                if texts[i] == first[0] and (len(first) < 2 or (i + 1 < len(texts) and texts[i + 1] == first[1])):
                    out[i].append(o.id)
                    break
        return out

    def psalm_title(self, num: int) -> str:
        c = collections.Counter()
        for o in self.psalm_objects(num):
            if o.payload.get("title"):
                c[o.payload["title"]] += 1
        return c.most_common(1)[0][0] if c else ""

    def psalm(self, num: int) -> str:
        prow = self.db.c.execute("SELECT * FROM psalm WHERE num=?", (num,)).fetchone()
        rows = self.db.c.execute("SELECT * FROM psalm_verse WHERE psalm=? ORDER BY seq", (num,)).fetchall()
        vul = prow["vulgate"] if prow and prow["vulgate"] else str(num)
        head = f"Psalm {num}" + (f" ({esc(vul)})" if vul and vul != str(num) else "")
        # keep the heading with one whole verse; otherwise the psalm may start at the bottom of a page
        first = [r for r in rows if r["source"] != "NVT"]
        first_v = first[0]["verse"] if first else None
        n_first = sum(1 for r in first if r["verse"] == first_v) if first else 1
        n_titles = sum(1 for r in rows if r["source"] == "NVT")
        out = [f"\\psalmhead[{3 + n_titles + n_first}]{{{head}}}{{{tex(self.psalm_title(num), marks=False)}}}",
               f"\\objlabel{{{label(f'ps:{num}')}}}"]
        codes = self.margin_codes(num)
        breaks = self.strophe_breaks(num)
        starts = self.unit_starts(num, rows)
        placed = {u for us in starts.values() for u in us}
        # portions whose text does not match the consensus lines (printing variants): labelled at the psalm head
        for o in self.psalm_objects(num):
            if o.home in (None, "psalter") and o.id not in placed:
                out.append(f"\\objlabel{{{label('psu:' + o.id)}}}")
        lh_verses = {r["verse"] for r in rows if r["source"] == "LH"}
        in_unused = False
        prev_v = None
        pending: list[str] = []
        for i, r in enumerate(rows):
            v = r["verse"]
            k = r["line"]
            unused = r["source"] != "LH"
            if unused and not in_unused:
                out.append(r"\begin{unused}")
                in_unused = True
            if not unused and in_unused:
                out.append(r"\end{unused}")
                in_unused = False
            # a strophe gap only where a verse or couplet begins — never inside a couplet/triplet
            if (v, k) in breaks and i > 0 and r["x"] == 0:
                out.append(r"\psbreak")
            # one margin note per line, merging every portion that starts here; a verse range follows each code
            # when that portion is only part of the psalm
            cyc_all, oth_all = [], []
            for uid in starts.get(i, []):
                out.append(f"\\objlabel{{{label('psu:' + uid)}}}")
                cycle, other = codes.get(uid, ([], []))
                p = self.db.obj(uid).payload
                partial = bool(lh_verses - set(unit_verses(p["lines"])[0]))
                ref = psalm_unit_ref(p)
                rng = f" ({ref.split(':', 1)[1]})" if partial and ":" in ref else ""
                cyc_all += [c + rng for c in cycle if c + rng not in cyc_all]
                oth_all += [c + rng for c in other if c + rng not in oth_all]
            if len(oth_all) > self.OTHER_MAX:
                oth_all = oth_all[:self.OTHER_MAX - 1] + [f"+ {len(oth_all) - self.OTHER_MAX + 1} more"]
            if cyc_all or oth_all:
                pending.append(self.margin_note(cyc_all, oth_all))
            t = tex(r["text"]) if r["source"] == "LH" else tex(r["text"], marks=False)
            if pending:            # margin notes ride inside the line they belong to (horizontal mode)
                t = "".join(pending) + t
                pending = []
            if r["source"] == "NVT":
                out.append(r"\pstitle{" + t + "}")
            elif k == 0 and v != prev_v:
                out.append(f"\\psl{{{esc(v or '')}}}{{{t}}}")
            elif r["x"] >= 2:
                out.append(f"\\psk{{{t}}}")
            else:
                out.append(f"\\psc{{{t}}}")
            prev_v = v
        if in_unused:
            out.append(r"\end{unused}")
        return "\n".join(out)

    def canticle(self, o: Obj, aliases: list[str] = ()) -> str:
        """One canticle with the margin uses of every printing variant (aliases share the heading's label)."""
        p = o.payload
        ids = [o.id, *aliases]
        uses = []
        for oid in ids:
            uses += self.db.c.execute("""SELECT h.day_key, d.psalter_week, d.weekday, h.hour, oc.slot, d.season, d.rank,
                                                d.title, d.short
                                         FROM occurrence oc JOIN hour_instance h ON h.id=oc.hour_id JOIN day d ON d.key=h.day_key
                                         WHERE oc.object_id=? ORDER BY h.id""", (oid,)).fetchall()
        cycle, other = self.use_codes(uses)
        n_first = next((i for i, l in enumerate(p["lines"][1:], 1) if l.get("v")), 2)
        out = [f"\\psalmhead[{3 + n_first}]{{Canticle {esc(p['ref'])}}}{{{tex(p.get('title', ''), marks=False)}}}"]
        out += [f"\\objlabel{{{label(i)}}}" for i in ids]
        lines = L.canticle_lines(p["lines"])
        note = self.margin_note(cycle, other)
        if note:   # attach to the first line (horizontal mode)
            lines = re.sub(r"(\\psl\{[^}]*\}\{|\\psc\{|\\psk\{)", lambda m: m.group(1) + note, lines, count=1)
        out.append(lines)
        if p.get("no_gloria"):
            out.append(r"\par{\footnotesize\rubric{Glória Patri is not said after this canticle.}}\par")
        return "\n".join(out)

    PSALTER_INTRO = (r"\rubr{Psalms are numbered as in the English Liturgy of the Hours (Hebrew numbering), with the Vulgate "
                     r"number of the Latin edition in parentheses. The margin shows where each portion is prayed in the "
                     r"four-week cycle: \emph{week} (I–IV), \emph{day}, \emph{hour} and \emph{psalm number}, e.g. "
                     r"\rubric{I Mon L.1} = Week I, Monday, Lauds, first psalm. Hours: Inv = Invitatory, OR = Office of "
                     r"Readings, L = Lauds, D = Daytime Prayer, 1V/2V = First/Second Vespers, V = Vespers, C = Compline. "
                     r"A verse range follows when only part of the psalm is used. Verses printed in "
                     r"{\footnotesize smaller type} are not used in the Liturgy of the Hours (text: Nova Vulgata).}")


def load_supplement() -> dict:
    return yaml.safe_load((SEED / "ordinary_supplement.yaml").read_text(encoding="utf-8"))

# ============================================================================================ shared Ordinary texts

def sup_pairs(prs) -> str:
    return r"\par ".join((r"\Vs " if k == "V" else r"\Rs ") + tex(v) for k, v in prs)


def finding_the_office() -> str:
    """Ordinary: how to find the office (order of checking) and the ten ribbons."""
    return "\n".join([r"\section{Finding the Office}", r"\objlabel{sec:finding}",
        r"\begin{enumerate}[leftmargin=1.4em,itemsep=2pt]",
        r"\item \textbf{The day.} From the calendar, find the season, the week, and any celebration of the date.",
        r"\item \textbf{Saints first.} Look the date up in the Proper of Saints (ribbon 1). If the celebration "
        r"outranks the day of the season (solemnity, feast, memorial over a weekday; Table of Liturgical Days), "
        r"take what it gives, and what it lacks from the Common it names (ribbon 2). On a memorial only the "
        r"proper parts change; the psalms are usually those of the weekday. In the evening, compare today's "
        r"Vespers with tomorrow's First Vespers the same way.",
        r"\item \textbf{The psalter week.} Ordinary Time week $N$ uses psalter week $((N-1) \bmod 4)+1$; "
        r"Advent weeks 1–4 use I–IV; Lent: Ash Wednesday IV, weeks 1–5 I, II, III, IV, I; Holy Week II; "
        r"Easter weeks 2–7: II, III, IV, I, II, III.",
        r"\item \textbf{The hour.} Open the Proper of Time at the day and hour (ribbons 4–6). Say the hour from its "
        r"heading, with the \textbf{Ordinary card} in hand: the opening verses, the Invitatory psalm, the Gospel "
        r"canticles, the Pater noster, the dismissals, the Te Deum and the antiphons of Our Lady are on the two "
        r"cards (and in this Ordinary). Each hour heading gives the pages to mark: \rubric{P} the psalms and "
        r"canticles (ribbons 8–9), \rubric{R} the readings (ribbon 10), \rubric{O} this Ordinary for Daytime "
        r"Prayer (ribbon 3). The hymn is referred to at the top of each hour (ribbon 7). Compline is printed whole "
        r"in the weekly forms of this Ordinary (ribbon 3).",
        r"\end{enumerate}",
        r"\subsection{The ten ribbons}",
        r"\rubr{Assigned by use: the places the reader comes back to most often have the most ribbons (TODO B-16; "
        r"reports/simulation.md).}",
        r"\begin{enumerate}[leftmargin=1.8em,itemsep=0pt,label=\rubric{\arabic*.}]",
        r"\item Proper of Saints — the saint of the day \item Commons — the Common it refers to",
        r"\item Ordinary — Compline (the form of the day) and Daytime Prayer",
        r"\item Proper of Time — the hour being said",
        r"\item Proper of Time — where that hour continues, or the next hour",
        r"\item Proper of Time — the texts of the week (Ordinary Time: Sunday antiphons and collect) or of the "
        r"season's day",
        r"\item Hymns",
        r"\item Psalter — the psalms of the hour \item Psalter or Canticles — the canticle or the next psalm",
        r"\item Readings of the Office of Readings",
        r"\end{enumerate}"])


def opening_block(s: dict) -> str:
    """Ordinary: opening verse and Gloria Patri (from the Ordinary supplement)."""
    return "\n".join([r"\section{Opening and Gloria}", r"\objlabel{ord:opening}",
        r"\rubr{Every hour except the Invitatory begins:}\par", sup_pairs(s["opening"]),
        r"\par " + tex(s["gloria_short"]) + r" \rubr{Allelúia (omitted in Lent).}",
        r"\par\vspace{4pt}\rubr{At the end of every psalm and canticle (unless noted):}\par",
        r"\objlabel{ord:gloria}\psl{}{Glória Patri et Fílio \mediant{}}\psk{et Spirítui Sancto.}"
        r"\psc{Sicut erat in princípio et nunc et semper \mediant{}}\psk{et in sǽcula sæculórum. Amen.}"])


def ribbon_refs(db: DB, days: list, hour: str, inv_label: str = label("ps:95"), anchor=None) -> str:
    """Hour head (B-16): P = psalm pages (ribbons 8–9), R = readings page when it is the same for all, O = the
    Ordinary page of Daytime Prayer (ribbon 3). The fixed parts of the other hours are on the Ordinary card."""
    anchor_of = anchor or unit_anchor
    if hour == "INV":
        return r"\cardref{1}"
    parts = [r"\ribbon{O}{\pg{ord:midday}}"] if hour == "MIDDAY" else []
    groups: dict[tuple, list] = collections.defaultdict(list)
    reads: set = set()
    for d in days:
        h = db.hour(d["key"], hour)
        if not h:
            continue
        ref = db.c.execute("SELECT psalm_units, readings FROM hour_refs WHERE hour_id=?", (h["id"],)).fetchone()
        if not ref:
            continue
        units = json.loads(ref["psalm_units"] or "{}")
        labs = []
        for slot in sorted(units):
            o = db.obj(units[slot])
            labs.append(anchor_of(o))
        if labs:
            groups[tuple(labs)].append(d)
        if ref["readings"]:
            reads.add(json.loads(ref["readings"]).get("LECT1"))
    all_ot = {d["week"] for d in days if d["season"] == "OT"}
    ordered = sorted(groups.items(), key=lambda kv: min(SEASON_ORDER[d["season"]] for d in kv[1]))
    for i, (labs, ds) in enumerate(ordered):
        pages = ", ".join(r"\pg{" + l + "}" for l in labs)
        prefix = "" if i == 0 else r"\enspace/\enspace{\scshape " + esc(labels_for(ds, all_ot)) + "} "
        parts.append(prefix + r"\ribbon{P}{" + pages + "}")
    if len(reads) == 1 and None not in reads:
        parts.append(r"\ribbon{R}{\pg{" + label(next(iter(reads))) + "}}")
    return r"\enspace ".join(parts)
