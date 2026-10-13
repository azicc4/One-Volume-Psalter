"""Proof-of-concept book: Psalter-week I, Sunday and Monday, generated entirely from build/lh.sqlite.

Sections follow the planned book order: Psalter (+ Canticles) · Hymns · Ordinary · Propers of Time · OR Readings.
Every object is printed once at its home and referenced elsewhere by \\pageref, so page numbers stay correct.
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3
from dataclasses import dataclass, field

import yaml

from lh.config import BOOK, DB_PATH, SEED
from lh.model.canon import plain, psalm_base, unit_verses
from lh.model.days import DAY_NAMES
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
              "V2": "Second Vespers", "COMPLINE": "Compline"}
SUB_TITLE = {"TERCE": "Terce", "SEXT": "Sext", "NONE": "None"}
GOSPEL = {"LAUDS": "Benedictus", "VESPERS": "Magnificat", "V1": "Magnificat", "V2": "Magnificat", "COMPLINE": "Nunc dimittis"}

VESPERS_SLOTS = ["HYMN", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3", "LB", "RB", "GOSPEL_ANT", "PRECES", "ORATIO"]
SLOT_ORDER = {
    "INV": ["INV_ANT"],
    "OR": ["HYMN", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3", "OR_VERSE", "LECT1", "LECT2", "ORATIO"],
    "LAUDS": VESPERS_SLOTS, "VESPERS": VESPERS_SLOTS, "V1": VESPERS_SLOTS, "V2": VESPERS_SLOTS,
    "MIDDAY": [("HYMN", "TERCE"), ("ANT", "TERCE"), ("HYMN", "SEXT"), ("ANT", "SEXT"), ("HYMN", "NONE"), ("ANT", "NONE"),
               "ANT", "ANT1", "PS1", "ANT2", "PS2", "ANT3", "PS3",
               ("LB", "TERCE"), ("V", "TERCE"), ("ORATIO", "TERCE"), ("LB", "SEXT"), ("V", "SEXT"), ("ORATIO", "SEXT"),
               ("LB", "NONE"), ("V", "NONE"), ("ORATIO", "NONE")],
}
SLOT_NAME = {"HYMN": "Hymn", "ANT": "Antiphon", "ANT1": "Ant. 1", "ANT2": "Ant. 2", "ANT3": "Ant. 3", "PS1": "Psalm 1",
             "PS2": "Psalm 2", "PS3": "Psalm 3", "LB": "Short reading", "RB": "Short responsory",
             "GOSPEL_ANT": "Gospel canticle antiphon", "PRECES": "Intercessions", "ORATIO": "Concluding prayer",
             "INV_ANT": "Invitatory antiphon", "OR_VERSE": "Versicle", "V": "Versicle", "LECT1": "First reading",
             "LECT2": "Second reading"}
COND_LABEL = {"year": lambda v: f"Year {v}:", "variant": lambda v: {"night": "At night or early morning:",
                                                                    "day": "During the day:"}.get(v, v),
              "alt": lambda v: "Or:"}


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


class DB:
    def __init__(self):
        self.c = con()
        self._obj: dict[str, Obj] = {}

    def obj(self, oid: str) -> Obj:
        if oid not in self._obj:
            r = self.c.execute("SELECT id, type, payload, n_occ FROM object WHERE id=?", (oid,)).fetchone()
            self._obj[oid] = Obj(r["id"], r["type"], json.loads(r["payload"]), r["n_occ"])
        return self._obj[oid]

    def days(self, pw: int, wd: str):
        return self.c.execute("""SELECT * FROM day WHERE psalter_week=? AND weekday=? AND season IN ('OT','ADV','LENT','EAS')
                                 AND key NOT LIKE 'ADV.DEC%' ORDER BY season, week""", (pw, wd)).fetchall()

    def hour(self, day_key: str, hour: str):
        return self.c.execute("SELECT * FROM hour_instance WHERE day_key=? AND hour=? ORDER BY copy IS NOT NULL, id LIMIT 1",
                              (day_key, hour)).fetchone()

    def occ(self, hour_id: int):
        return self.c.execute("SELECT * FROM occurrence WHERE hour_id=? ORDER BY seq", (hour_id,)).fetchall()


# ============================================================================================ variant grid

def day_tag(d) -> tuple[str, int]:
    return d["season"], d["week"]


def cond_text(cond_json: str | None) -> str:
    if not cond_json:
        return ""
    c = json.loads(cond_json)
    for k in ("year", "variant", "alt"):
        if c.get(k):
            return COND_LABEL[k](c[k])
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
    per_day = {}
    for d in days:
        h = db.hour(d["key"], hour)
        if not h:
            continue
        items = []
        for o in db.occ(h["id"]):
            if o["slot"] == slot and (o["sub"] or "") == sub and o["object_id"]:
                items.append((cond_text(o["cond"]), o["object_id"]))
        if items:
            # keep first occurrence order, drop exact duplicates
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


def obj_ref(db: DB, oid: str) -> str:
    o = db.obj(oid)
    p = o.payload
    if o.type == "psalm":
        return f"{esc(psalm_unit_ref(p))} {{\\footnotesize ({esc(p['vulg'])})}}\\enspace\\seepage{{{label('psu:' + oid)}}}"
    if o.type == "canticle":
        try:
            b, r, _ = parse_ref(p["ref"])
            ref = fmt(b, r).replace("-end", "ff.")
        except ValueError:
            ref = p["ref"]
        return f"Canticle {esc(ref)}\\enspace\\seepage{{{label(oid)}}}"
    if o.type == "hymn":
        return f"\\textit{{{tex(p['stanzas'][0][0], marks=False)}}}\\enspace\\seepage{{{label(oid)}}}"
    if o.type == "reading":
        intro = plain(" ".join(p.get("intro", []))) or plain(p["lines"][0][1])[:60]
        return f"{{\\small {esc(intro)}}}\\enspace\\seepage{{{label(oid)}}}"
    return L.render(o.type, p)


# ============================================================================================ book builder

class POC:
    PW, WEEKDAYS = 1, ("SUN", "MON")

    def __init__(self):
        self.db = DB()
        self.supp = yaml.safe_load((SEED / "ordinary_supplement.yaml").read_text(encoding="utf-8"))
        self.used_objects: set[str] = set()         # referenced from the grid
        self.printed: set[str] = set()              # labels actually placed (for safe refs)
        self.or_readings: list[tuple[str, str]] = []  # (label text, reading object id)

    # ---------------------------------------------------------------- collect what the POC needs
    def grid_days(self, wd):
        return self.db.days(self.PW, wd)

    def hours_for(self, wd):
        return ["V1", "INV", "OR", "LAUDS", "MIDDAY", "V2"] if wd == "SUN" else ["INV", "OR", "LAUDS", "MIDDAY", "VESPERS"]

    def collect(self):
        for wd in self.WEEKDAYS:
            days = self.grid_days(wd)
            for hour in self.hours_for(wd):
                for s in SLOT_ORDER["VESPERS" if hour in ("V1", "V2") else hour]:
                    slot, sub = (s if isinstance(s, tuple) else (s, ""))
                    for g in slot_groups(self.db, days, hour, slot, sub):
                        for _, oid in g.items:
                            self.used_objects.add(oid)
        # Compline (fixed weekly cycle): Saturday after I Vespers, Sunday, Monday — taken from OT days
        self.compline = {}
        for key, hour, name in (("OT.05.SUN", "COMPLINE1", "Saturday (after First Vespers of Sunday)"),
                                ("OT.05.SUN", "COMPLINE", "Sunday (after Second Vespers)"),
                                ("OT.05.MON", "COMPLINE", "Monday")):
            h = self.db.hour(key, hour)
            self.compline[name] = [o for o in self.db.occ(h["id"]) if o["object_id"]]
            for o in self.compline[name]:
                self.used_objects.add(o["object_id"])

    def psalms_needed(self) -> list[int]:
        nums = set()
        for oid in self.used_objects:
            o = self.db.obj(oid)
            if o.type == "psalm":
                nums.add(psalm_base(o.payload["psalm"]))
        nums.add(95)   # invitatory
        return sorted(nums)

    # ---------------------------------------------------------------- PSALTER
    def use_codes(self, rows) -> tuple[list, list]:
        """psalm_use-like rows → (four-week-cycle codes, other uses each as its own line), deduplicated in order."""
        cycle, other = [], []
        for r in rows:
            m = re.match(r"PS(\d+)", r["slot"] or "")
            n = m.group(1) if m else ""
            hc = HOURCODE.get(r["hour"], "C" if r["hour"].startswith("COMPLINE") else r["hour"])
            code, is_cycle = None, True
            if r["hour"] in ("COMPLINE", "COMPLINE1"):
                if not (r["season"] == "OT" and r["rank"] in ("sunday", "weekday")):
                    continue       # Compline of solemnities/seasons repeats the weekly cycle (Sunday Compline)
                code = "C " + ("Sat" if r["hour"] == "COMPLINE1" else DAYABBR[r["weekday"]])
            elif r["season"] == "OT" and r["rank"] in ("sunday", "weekday") and r["psalter_week"]:
                code = f"{ROMAN[r['psalter_week']]} {DAYABBR[r['weekday']]} {hc}.{n}"
            elif r["day_key"] == "ORD.INVITATORY":
                code = "Inv"
            elif r["day_key"].startswith("ORD.COMPLEMENTARY"):
                code = None if r["day_key"].endswith("NO_ANT") else f"Compl.{n}"
            elif r["season"] in ("ADV", "LENT", "EAS") and r["rank"] in ("sunday", "weekday", "privileged_weekday") and r["psalter_week"]:
                continue       # same psalter-week use as Ordinary Time
            elif not r["day_key"].startswith(("ORD.", "PROP.")) and "ORD." not in r["day_key"] and "PROP." not in r["day_key"]:
                code, is_cycle = f"{r['short'] or r['title']} {hc}.{n}".rstrip("."), False
            if code:
                bucket = cycle if is_cycle else other
                if code not in bucket:
                    bucket.append(code)
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

    def strophe_breaks(self, num: int) -> set[tuple]:
        """(verse, k) keys preceded by a strophe break in the majority of printings (page breaks excluded)."""
        votes = collections.Counter()
        totals = collections.Counter()
        for r in self.db.c.execute("""SELECT ob.payload, o.extra FROM occurrence o JOIN object ob ON ob.id=o.object_id
                                      WHERE ob.type='psalm' AND ob.payload LIKE ?""", (f'%"psalm": "{num}%',)):
            p = json.loads(r["payload"])
            if psalm_base(p["psalm"]) != num:
                continue
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
        for r in self.db.c.execute("SELECT id, payload FROM object WHERE type='psalm'"):
            p = json.loads(r["payload"])
            if psalm_base(p["psalm"]) != num:
                continue
            first = [l["t"] for l in p["lines"] if not l.get("refrain")][:2]
            for i in range(len(texts)):
                if texts[i] == first[0] and (len(first) < 2 or (i + 1 < len(texts) and texts[i + 1] == first[1])):
                    out[i].append(r["id"])
                    break
        return out

    def psalm_title(self, num: int) -> str:
        c = collections.Counter()
        for (payload,) in self.db.c.execute("SELECT payload FROM object WHERE type='psalm'"):
            p = json.loads(payload)
            if psalm_base(p["psalm"]) == num and p.get("title"):
                c[p["title"]] += 1
        return c.most_common(1)[0][0] if c else ""

    def psalter(self) -> str:
        out = [r"\chapter{The Psalter}", r"\objlabel{sec:psalter}",
               r"\rubr{Psalms are numbered as in the English Liturgy of the Hours (Hebrew numbering), with the Vulgate "
               r"number of the Latin edition in parentheses. The margin shows where each portion is prayed in the "
               r"four-week cycle: \emph{week} (I–IV), \emph{day}, \emph{hour} and \emph{psalm number}, e.g. "
               r"\rubric{I Mon L.1} = Week I, Monday, Lauds, first psalm. Hours: Inv = Invitatory, OR = Office of "
               r"Readings, L = Lauds, D = Daytime Prayer, 1V/2V = First/Second Vespers, V = Vespers, C = Compline. "
               r"A verse range follows when only part of the psalm is used. Verses printed in "
               r"{\footnotesize smaller type} are not used in the Liturgy of the Hours (text: Nova Vulgata).}",
               r"\par\vspace{\baselineskip}"]
        for num in self.psalms_needed():
            out.append(self.psalm(num))
        out.append(self.canticles())
        return "\n".join(out)

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
        lh_verses = {r["verse"] for r in rows if r["source"] == "LH"}
        in_unused = False
        prev_v = None
        k = 0
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

    def canticles(self) -> str:
        out = [r"\chapter{Canticles}", r"\objlabel{sec:canticles}",
               r"\rubr{Old and New Testament canticles of Lauds and Vespers. The Gospel canticles (Benedictus, "
               r"Magnificat, Nunc dimittis) are in the Ordinary.}"]
        cants = [self.db.obj(oid) for oid in self.used_objects if self.db.obj(oid).type == "canticle"
                 and not self.db.obj(oid).payload.get("gospel")]
        seen = set()
        for o in sorted(cants, key=lambda o: o.payload["ref"]):
            p = o.payload
            if o.id in seen:
                continue
            seen.add(o.id)
            uses = self.db.c.execute("""SELECT h.day_key, d.psalter_week, d.weekday, h.hour, oc.slot, d.season, d.rank,
                                               d.title, d.short
                                        FROM occurrence oc JOIN hour_instance h ON h.id=oc.hour_id JOIN day d ON d.key=h.day_key
                                        WHERE oc.object_id=? ORDER BY h.id""", (o.id,)).fetchall()
            cycle, other = self.use_codes(uses)
            n_first = next((i for i, l in enumerate(p["lines"][1:], 1) if l.get("v")), 2)
            out.append(f"\\psalmhead[{3 + n_first}]{{Canticle {esc(p['ref'])}}}{{{tex(p.get('title', ''), marks=False)}}}")
            out.append(f"\\objlabel{{{label(o.id)}}}")
            lines = L.canticle_lines(p["lines"])
            note = self.margin_note(cycle, other)
            if note:   # attach to the first line (horizontal mode)
                lines = re.sub(r"(\\psl\{[^}]*\}\{|\\psc\{|\\psk\{)", lambda m: m.group(1) + note, lines, count=1)
            out.append(lines)
            if p.get("no_gloria"):
                out.append(r"\par{\footnotesize\rubric{Glória Patri is not said after this canticle.}}\par")
        return "\n".join(out)

    # ---------------------------------------------------------------- HYMNS
    def hymns(self) -> str:
        out = [r"\chapter{Hymns}", r"\objlabel{sec:hymns}",
               r"\rubr{Each hymn is printed once; the Propers and the Ordinary refer to it by page.}"]
        hyms = [self.db.obj(oid) for oid in self.used_objects if self.db.obj(oid).type == "hymn"]
        for o in sorted(hyms, key=lambda o: plain(o.payload["stanzas"][0][0])):
            first = tex(o.payload["stanzas"][0][0], marks=False)
            out.append(r"\needspace{6\baselineskip}\par\vspace{0.5\baselineskip}{\scshape\color{rubric}"
                       + first.rstrip(",.;:") + r"}\par" + f"\\objlabel{{{label(o.id)}}}")
            out.append(L.hymn(o.payload))
        return "\n".join(out)

    # ---------------------------------------------------------------- ORDINARY
    def ordinary(self) -> str:
        s = self.supp
        db = self.db

        def sup_pairs(prs):
            return r"\par ".join((r"\Vs " if k == "V" else r"\Rs ") + tex(v) for k, v in prs)

        def first_obj(day_key, hour, slot, otype=None):
            h = db.hour(day_key, hour)
            if not h:
                return None
            for o in db.occ(h["id"]):
                if o["slot"] == slot and o["object_id"] and (otype is None or o["type"] == otype):
                    return db.obj(o["object_id"])
            return None

        ben = first_obj("OT.01.MON", "LAUDS", "GOSPEL_CANT")
        mag = first_obj("OT.01.MON", "VESPERS", "GOSPEL_CANT")
        nunc = first_obj("OT.01.MON", "COMPLINE", "GOSPEL_CANT")
        tedeum = first_obj("OT.05.SUN", "OR", "TE_DEUM")
        dism = {hr: [db.obj(o["object_id"]) for o in db.occ(db.hour("ORD.DISMISSAL", hr)["id"]) if o["object_id"]]
                for hr in ("OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE")}
        marian = [db.obj(o["object_id"]) for o in db.occ(db.hour("ORD.MARIAN", "APPX")["id"])
                  if o["object_id"] and o["type"] in ("text", "rubric")]
        out = [r"\chapter{The Ordinary}", r"\objlabel{sec:ordinary}"]
        # --- finding the office: order of checking and the ten ribbons
        out += [r"\section{Finding the Office}", r"\objlabel{sec:finding}",
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
                r"\item \textbf{The hour.} Open the Ordinary at the hour (ribbon 3), then the Proper of Time at the week "
                r"and day (ribbon 4). Each hour heading in the Proper of Time gives the pages to mark: "
                r"\rubric{O} the Ordinary, \rubric{P} the psalms (ribbons 6–9), \rubric{R} the readings (ribbon 10). "
                r"Hymns (ribbon 5) are referred to at the top of each hour.",
                r"\end{enumerate}",
                r"\subsection{The ten ribbons}",
                r"\begin{enumerate}[leftmargin=1.8em,itemsep=0pt,label=\rubric{\arabic*.}]",
                r"\item Proper of Saints \item Commons \item Ordinary \item Proper of Time \item Hymns",
                r"\item Psalter — first psalm \item Psalter — second psalm \item Psalter — third psalm",
                r"\item Psalter — invitatory psalm (Ps 95, 100, 67 or 24) \item Readings of the Office of Readings",
                r"\end{enumerate}"]
        # --- common texts
        out += [r"\section{Opening and Gloria}", r"\objlabel{ord:opening}",
                r"\rubr{Every hour except the Invitatory begins:}\par", sup_pairs(s["opening"]),
                r"\par " + tex(s["gloria_short"]) + r" \rubr{Allelúia (omitted in Lent).}",
                r"\par\vspace{4pt}\rubr{At the end of every psalm and canticle (unless noted):}\par",
                r"\objlabel{ord:gloria}\psl{}{Glória Patri et Fílio \mediant{}}\psk{et Spirítui Sancto.}"
                r"\psc{Sicut erat in princípio et nunc et semper \mediant{}}\psk{et in sǽcula sæculórum. Amen.}"]
        def ordhour(title, anchor, refs):
            """Hour heading in the Ordinary with the pages of its fixed parts at the right."""
            r = r" \enspace·\enspace ".join(f"{name} \\pg{{{lab}}}" for name, lab in refs)
            return [f"\\objlabel{{{anchor}}}",
                    f"\\hourhead{{\\large {title}}}{{{r}}}",
                    f"\\addcontentsline{{toc}}{{section}}{{{title}}}\\markright{{{title}}}"]

        out += ordhour("Invitatory", "ord:invitatory", [("Ps 95", label("ps:95"))]) + [
                r"\rubr{Said before the first hour of the day (Office of Readings or Lauds).}\par",
                sup_pairs(s["invitatory_opening"]),
                r"\par\rubr{The antiphon of the day (Propers) is said and repeated after each strophe of Psalm 95, "
                r"\pgref{" + label("ps:95") + r"}, or Psalm 100, 67 or 24.}"]
        hour_refs = {
            "OR": [("Te Deum", "ord:tedeum"), ("Dismissal", "ord:dismissal:or")],
            "LAUDS": [("Benedictus", "ord:benedictus"), ("Pater", "ord:pater"), ("Dismissal", "ord:dismissal:lauds")],
            "MIDDAY": [("Dismissal", "ord:dismissal:midday")],
            "VESPERS": [("Magnificat", "ord:magnificat"), ("Pater", "ord:pater"), ("Dismissal", "ord:dismissal:vespers")],
        }
        for hr, title, gospel in (("OR", "Office of Readings", None), ("LAUDS", "Lauds", ben),
                                  ("MIDDAY", "Daytime Prayer", None), ("VESPERS", "Vespers", mag)):
            out += ordhour(title, f"ord:{hr.lower()}", hour_refs[hr])
            steps = {
                "OR": ["Opening", "Hymn", "Psalmody (three psalms with antiphons)", "Versicle",
                       "First reading and responsory; second reading and responsory",
                       r"Te Deum on Sundays (outside Lent), solemnities and feasts, \pgref{ord:tedeum}", "Concluding prayer"],
                "LAUDS": ["Opening", "Hymn", "Psalmody: morning psalm, Old Testament canticle, psalm of praise",
                          "Short reading and short responsory", "Benedictus with its antiphon (below)",
                          "Intercessions", r"Pater noster, \pgref{ord:pater}", "Concluding prayer", "Dismissal"],
                "MIDDAY": ["Opening", "Hymn (Terce, Sext or None)", "Psalmody: of the day, or the complementary "
                           "psalmody (Pss 120–128) at the other hours", "Short reading and versicle", "Concluding prayer",
                           r"\Vs Benedicámus Dómino. \Rs Deo grátias."],
                "VESPERS": ["Opening", "Hymn", "Psalmody: two psalms and a New Testament canticle",
                            "Short reading and short responsory", "Magnificat with its antiphon (below)",
                            "Intercessions", r"Pater noster, \pgref{ord:pater}", "Concluding prayer", "Dismissal"],
            }[hr]
            out.append(r"\begin{enumerate}[leftmargin=1.4em,itemsep=0pt,label=\rubric{\arabic*.}]" +
                       "".join(r"\item " + x for x in steps) + r"\end{enumerate}")
            if gospel:
                name = "Benedictus" if hr == "LAUDS" else "Magnificat"
                out += [f"\\subsection{{{name}}}", f"\\objlabel{{ord:{name.lower()}}}",
                        r"{\centering\footnotesize " + esc(gospel.payload["ref"]) + r"\par}", L.canticle_lines(gospel.payload["lines"]),
                        r"\gloria"]
            if dism.get(hr):
                out.append(r"\subsection{Dismissal}" + f"\\objlabel{{ord:dismissal:{hr.lower()}}}")
                out += [L.render(o.type, o.payload) + r"\par" for o in dism[hr]]
        out += [r"\section{Pater noster}", r"\objlabel{ord:pater}", tex(s["pater_noster"]),
                r"\par\vspace{4pt}\rubr{Prayer endings abbreviated in the Propers:}\par\begin{itemize}[leftmargin=1em,itemsep=0pt]"]
        out += [r"\item \rubric{" + esc(k) + "} " + tex(v) for k, v in s["conclusions"].items()]
        out.append(r"\end{itemize}")
        if tedeum:
            out += [r"\section{Te Deum}", r"\objlabel{ord:tedeum}", L.te_deum(tedeum.payload)]
        # --- Compline: fixed weekly cycle lives in the Ordinary
        out += ordhour("Compline", "ord:compline", [("Nunc dimittis", "ord:nunc"), ("B.V.M.", "ord:marian")]) + [
                r"\begin{enumerate}[leftmargin=1.4em,itemsep=0pt,label=\rubric{\arabic*.}]"
                r"\item Opening \item Examination of conscience (penitential act) \item Hymn \item Psalmody of the day "
                r"\item Short reading \item Responsory \item Nunc dimittis with antiphon \item Concluding prayer "
                r"\item Blessing \item Antiphon of the Blessed Virgin Mary\end{enumerate}"]
        if nunc:
            out += [r"\subsection{Nunc dimittis}", r"\objlabel{ord:nunc}", L.canticle_lines(nunc.payload["lines"]), r"\gloria"]
        for name, occs in self.compline.items():
            out += [f"\\subsection{{Compline: {esc(name)}}}", f"\\objlabel{{ord:compline:{esc(name.split()[0].lower())}}}"]
            for o in occs:
                ob = db.obj(o["object_id"])
                slot = o["slot"]
                if slot == "HYMN":
                    nm, body = "Hymn", obj_ref(db, ob.id)
                elif slot.startswith("ANT") and not slot.endswith("_R"):
                    nm, body = "Antiphon", L.ant(ob.payload)
                elif slot.startswith("PS") and not slot.endswith("_R"):
                    nm, body = "Psalm", obj_ref(db, ob.id)
                elif slot in ("LB", "RB", "ORATIO", "GOSPEL_ANT", "BLESSING"):
                    nm = {"LB": "Short reading", "RB": "Responsory", "ORATIO": "Concluding prayer",
                          "GOSPEL_ANT": "Antiphon at the Nunc dimittis", "BLESSING": "Blessing"}[slot]
                    body = L.render(ob.type, ob.payload)
                else:
                    continue
                out.append(r"\slotname{" + nm + "}{" + L.citation(ob.type, ob.payload) + "}"
                           + r"\variant{}{}{" + body + "}")
        out += [r"\subsection{Antiphons of the Blessed Virgin Mary}", r"\objlabel{ord:marian}"]
        out += [L.render(o.type, o.payload) + r"\par\vspace{3pt}" for o in marian]
        return "\n".join(out)

    # ---------------------------------------------------------------- PROPERS OF TIME
    def propers(self) -> str:
        out = [r"\chapter{Propers of Time}", r"\objlabel{sec:propers}",
               r"\rubr{The four-week cycle, day by day and hour by hour. Under each part, the texts for every season "
               r"that uses this psalter week are given side by side: \rubric{\scshape Per annum} (all weeks of "
               r"Ordinary Time on this psalter week), \rubric{\scshape Adv.}, \rubric{\scshape Lent}, "
               r"\rubric{\scshape Easter} with the week of the season. Where a season has its own text it is listed; "
               r"otherwise the Per annum text serves. Fixed parts are in the Ordinary.}"]
        for wd in self.WEEKDAYS:
            out.append(self.proper_day(wd))
        return "\n".join(out)

    def ribbon_refs(self, days: list, hour: str) -> str:
        """Hour head: O = Ordinary page, P = psalm pages (ribbons 6–9), R = readings page when it is the same for all."""
        db = self.db
        anchor = {"INV": "ord:invitatory", "OR": "ord:or", "LAUDS": "ord:lauds", "MIDDAY": "ord:midday"}.get(hour, "ord:vespers")
        parts = [r"\ribbon{O}{\pg{" + anchor + "}}"]
        if hour == "INV":
            parts.append(r"\ribbon{P}{\pg{" + label("ps:95") + "}}")
            return r"\enspace ".join(parts)
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
                labs.append(label("psu:" + o.id) if o.type == "psalm" else label(o.id))
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

    def proper_day(self, wd: str) -> str:
        db = self.db
        days = self.grid_days(wd)
        title = f"Week {ROMAN[self.PW]} — {DAY_NAMES[wd]}"
        ot_weeks = sorted(d["week"] for d in days if d["season"] == "OT")
        others = ", ".join(f"{SEASON_LABEL[d['season']]} {d['week']}" for d in days if d["season"] != "OT")
        out = [f"\\section{{{title}}}", f"\\objlabel{{prop:{wd}}}",
               r"{\footnotesize\rubric{Used on:} Ordinary Time weeks " + ", ".join(map(str, ot_weeks)) + "; "
               + esc(others) + r".\par}"]
        week_blocks: dict[int, list] = collections.defaultdict(list)    # OT week -> [(hour, slot, items)]
        sunday_collects = {}
        if wd == "SUN":
            for d in days:
                if d["season"] == "OT":
                    h = db.hour(d["key"], "LAUDS")
                    for o in db.occ(h["id"]):
                        if o["slot"] == "ORATIO" and o["object_id"]:
                            sunday_collects[d["week"]] = o["object_id"]
        for hour in self.hours_for(wd):
            ht = r"First Vespers \rubric{\footnotesize (Saturday evening)}" if hour == "V1" else HOUR_TITLE[hour]
            out.append(r"\hourhead{" + ht + "}{" + self.ribbon_refs(days, hour) + "}")
            cur_sub = None
            for s in SLOT_ORDER["VESPERS" if hour in ("V1", "V2") else hour]:
                slot, sub = (s if isinstance(s, tuple) else (s, ""))
                groups = slot_groups(db, days, hour, slot, sub)
                if not groups:
                    continue
                if sub and sub != cur_sub and slot == "LB":
                    out.append(r"\sublabel{" + SUB_TITLE[sub] + "}")
                    cur_sub = sub
                name = SLOT_NAME.get(slot, slot)
                if sub and slot in ("HYMN", "ANT"):
                    name += f" ({SUB_TITLE[sub]})"
                if slot == "GOSPEL_ANT":
                    name = f"Antiphon at the {GOSPEL.get(hour, 'Gospel canticle')}"
                kept = []
                for g in groups:
                    single_ot = all(d["season"] == "OT" for d in g.days) and len(g.days) == 1
                    if single_ot and slot == "GOSPEL_ANT" and wd == "SUN":
                        week_blocks[g.days[0]["week"]].append((hour, slot, g.items))
                        continue
                    if single_ot and slot == "ORATIO" and wd == "SUN":
                        continue     # Sunday collect: listed with its week below
                    if single_ot and slot == "ORATIO" and hour == "OR":
                        sun = db.hour(f"OT.{g.days[0]['week']:02d}.SUN", "LAUDS")
                        if sun and any(o["object_id"] == g.items[0][1] for o in db.occ(sun["id"])):
                            continue     # weekday Office of Readings: collect of the preceding Sunday
                    kept.append(g)
                if slot in ("LECT1", "LECT2"):
                    # level 2 per season-week: citation/incipit with its page in the Readings section
                    body = []
                    for g in kept:
                        for _, oid in g.items:
                            self.or_readings.append((g.label, oid))
                            body.append(r"\variant{" + esc(g.label) + "}{}{" + obj_ref(db, oid) + "}")
                    if body:
                        out.append(r"\slotname{" + name + "}{}" + "\n".join(body))
                    continue
                if not kept:
                    if slot == "ORATIO" and hour == "OR" and wd != "SUN":
                        out.append(r"\slotname{" + name + r"}{}\variant{Per annum}{}{\rubr{Collect of the preceding "
                                   r"Sunday (see the list at the end of this day).}}")
                    continue
                # citation: after the slot name when shared by every variant, else after each variant label
                cites = {L.citation(db.obj(oid).type, db.obj(oid).payload) for g in kept for _, oid in g.items}
                cites.discard("")
                shared = next(iter(cites)) if len(cites) == 1 else ""
                lines = []
                for g in kept:
                    items = []
                    for cond, oid in g.items:
                        o = db.obj(oid)
                        is_ant = slot in ("ANT", "ANT1", "ANT2", "ANT3", "GOSPEL_ANT", "INV_ANT")
                        r = L.ant(o.payload) if is_ant else obj_ref(db, oid)
                        items.append((r"\condlabel{" + esc(cond) + "}" if cond else "") + r)
                    first = db.obj(g.items[0][1])
                    cite = "" if shared or not cites else L.citation(first.type, first.payload)
                    lead = r"\par " if any(c for c, _ in g.items) else ""      # conditions start at level 3
                    lines.append(r"\variant{" + esc(g.label) + "}{" + cite + "}{" + lead + r"\par ".join(items) + "}")
                out.append(r"\slotname{" + name + "}{" + shared + "}" + "\n".join(lines))
            if hour in ("LAUDS", "VESPERS", "V1", "V2"):
                gname = GOSPEL[hour]
                out.append(r"\par{\footnotesize\rubric{" + gname + r",} \pgref{ord:" + gname.lower() + r"}; "
                           r"\rubric{Pater noster,} \pgref{ord:pater}.}\par")
            if hour == "OR" and wd == "SUN":
                out.append(r"\par{\footnotesize\rubric{Te Deum} (except in Lent), \pgref{ord:tedeum}.}\par")
        cname = "monday" if wd == "MON" else "sunday"
        out.append(r"\hourhead{Compline}{\ribbon{O}{\pg{ord:compline:" + cname + "}}}")
        if wd == "SUN":
            out.append(r"{\footnotesize After First Vespers: \pgref{ord:compline:saturday}; after Second Vespers: "
                       r"\pgref{ord:compline:sunday}.\par}")
        if week_blocks or sunday_collects:
            out.append(r"\subsection{Ordinary Time: proper to each week}")
            out.append(r"\rubr{The Gospel canticle antiphons follow the Sunday Gospel of Years A, B and C; the collect "
                       r"of the Sunday is also said at the Office of Readings on the weekdays of that week.}")
            for wk in sorted(set(week_blocks) | set(sunday_collects)):
                out.append(r"\sublabel{" + f"Week {wk} of Ordinary Time" + "}")
                for hour, slot, items in week_blocks.get(wk, []):
                    hn = {"V1": "First Vespers", "LAUDS": "Lauds", "V2": "Second Vespers"}.get(hour, hour)
                    body = r"\par ".join(r"\condlabel{" + esc(c) + "}" + L.ant(db.obj(o).payload) for c, o in items)
                    out.append(r"\variant{" + hn + r"}{}{\par " + body + "}")
                if wk in sunday_collects:
                    oid = sunday_collects[wk]
                    out.append(r"\variant{Collect}{}{" + f"\\objlabel{{{label('collect:' + oid)}}}"
                               + L.render("oratio", db.obj(oid).payload) + "}")
        if wd != "SUN":
            refs = []
            for d in days:
                if d["season"] != "OT":
                    continue
                h = db.hour(d["key"], "OR")
                o = next((o for o in db.occ(h["id"]) if o["slot"] == "ORATIO" and o["object_id"]), None)
                sun = db.hour(f"OT.{d['week']:02d}.SUN", "LAUDS")
                if o and sun and any(oo["object_id"] == o["object_id"] for oo in db.occ(sun["id"])):
                    refs.append(f"OT {d['week']}: " + r"\pgref{" + label("collect:" + o["object_id"]) + "}")
            if refs:
                out.append(r"\par\vspace{3pt}{\footnotesize\rubric{Collect at the Office of Readings (from the Sunday):} "
                           + "; ".join(refs) + r".\par}")
        return "\n".join(out)

    # ---------------------------------------------------------------- OR READINGS
    def readings(self) -> str:
        out = [r"\chapter{Readings of the Office of Readings}", r"\objlabel{sec:readings}",
               r"\rubr{Each day's two readings with their responsories. In this proof of concept only Week 1 of "
               r"Ordinary Time, Monday, is printed in full; the Propers list all the others by their opening line.}"]
        db = self.db
        h = db.hour("OT.01.MON", "OR")
        occs = [o for o in db.occ(h["id"]) if o["slot"] in ("LECT1", "RESP1", "LECT2", "RESP2")]
        out.append(r"\section{Monday of Week 1 in Ordinary Time}")
        for o in occs:
            ob = db.obj(o["object_id"])
            if o["slot"].startswith("LECT"):
                # heading with the citation: "First reading — Incipit liber Ecclesiástici 1, 1-25"
                title = "First reading" if o["slot"] == "LECT1" else "Second reading"
                cite = L.citation(ob.type, ob.payload)
                out.append(r"\slotname{" + title + "}{" + cite + "}" + f"\\objlabel{{{label(ob.id)}}}")
                rest = dict(ob.payload, intro=[])            # the intro is now in the heading
                out.append(L.reading(rest))
            else:
                out.append(r"\slotname{Responsory}{" + L.citation(ob.type, ob.payload) + "}")
                out.append(L.pairs(ob.payload))
        return "\n".join(out)

    def pending_part(self, title: str, note: str) -> str:
        return (f"\\chapter{{{title}}}\\objlabel{{sec:{slug_label(title)}}}\n"
                r"\rubr{" + note + "}")

    # ---------------------------------------------------------------- whole document
    def body(self) -> str:
        self.collect()
        # Book order: Saints · Commons · Ordinary · Proper of Time · Hymns · Psalter · OR readings (ribbons 1–10)
        parts = [
            self.pending_part("Proper of Saints", "Ribbon 1. Not yet in this proof of concept: built from the four "
                              "Sanctis volumes (workstreams WS4a/WS4b in TODO.md)."),
            self.pending_part("Commons", "Ribbon 2. Not yet in this proof of concept: built from the Communia volume "
                              "(workstream WS3 in TODO.md)."),
            self.ordinary(), self.propers(), self.hymns(), self.psalter(), self.readings()]
        body = "\n\n".join(parts)
        # references to texts not printed in the POC (e.g. other weeks' readings): neutralise their page refs
        printed = set(re.findall(r"\\objlabel\{([^}]*)\}", body))
        missing = r"{\footnotesize\color{black!55}[not in POC]}"
        for macro in ("seepage", "pgref", "pg"):
            body = re.sub(r"\\" + macro + r"\{([^}]*)\}", lambda m: m.group(0) if m.group(1) in printed else missing, body)
        return body


def slug_label(s: str) -> str:
    return re.sub(r"[^a-z]+", "-", s.lower()).strip("-")


def write_poc() -> str:
    out = BOOK / "generated"
    out.mkdir(parents=True, exist_ok=True)
    body = POC().body()
    (out / "poc_body.tex").write_text(body, encoding="utf-8")
    return str(out / "poc_body.tex")
