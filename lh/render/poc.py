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
    def margin_codes(self, num: int) -> tuple[dict, list]:
        """unit object id → [codes] for psalter-grid uses; plus a list of other uses ('also')."""
        rows = self.db.c.execute("""SELECT u.unit, u.day_key, u.hour, u.slot, u.psalter_week, u.weekday, d.season, d.rank, d.title
                                    FROM psalm_use u JOIN day d ON d.key=u.day_key WHERE u.psalm=?""", (num,)).fetchall()
        codes: dict[str, list] = collections.defaultdict(list)
        also = set()
        for r in rows:
            m = re.match(r"PS(\d+)", r["slot"] or "")
            n = m.group(1) if m else ""
            code = None
            if r["hour"] in ("COMPLINE", "COMPLINE1") and not (r["season"] == "OT" and r["rank"] in ("sunday", "weekday")):
                continue       # Compline of solemnities/seasons repeats the weekly cycle (Sunday Compline)
            if r["hour"] in ("COMPLINE", "COMPLINE1"):
                code = "C " + ("Sat" if r["hour"] == "COMPLINE1" else DAYABBR[r["weekday"]])
            elif r["season"] == "OT" and r["rank"] in ("sunday", "weekday") and r["psalter_week"]:
                code = f"{ROMAN[r['psalter_week']]} {DAYABBR[r['weekday']]} {HOURCODE.get(r['hour'], r['hour'])}.{n}"
            elif r["day_key"] == "ORD.INVITATORY":
                code = "Inv"
            elif r["day_key"].startswith("ORD.COMPLEMENTARY"):
                code = None if r["day_key"].endswith("NO_ANT") else f"Compl.{n}"
            elif r["season"] in ("ADV", "LENT", "EAS") and r["rank"] in ("sunday", "weekday", "privileged_weekday") and r["psalter_week"]:
                continue       # same psalter-week use as Ordinary Time
            elif not r["day_key"].startswith(("ORD.", "PROP.")):
                also.add(r["title"])
            if code and code not in codes[r["unit"]]:
                codes[r["unit"]].append(code)
        return codes, sorted(also)

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
        out = [f"\\section{{{head}}}" if False else f"\\psalmhead{{{head}}}{{{tex(self.psalm_title(num), marks=False)}}}",
               f"\\objlabel{{{label(f'ps:{num}')}}}"]
        codes, also = self.margin_codes(num)
        breaks = self.strophe_breaks(num)
        starts = self.unit_starts(num, rows)
        lh_verses = {r["verse"] for r in rows if r["source"] == "LH"}
        in_unused = False
        prev_v = None
        k = 0
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
            if (v, k) in breaks and i > 0:
                out.append(r"\psbreak")
            for uid in starts.get(i, []):
                out.append(f"\\objlabel{{{label('psu:' + uid)}}}")
                cs = codes.get(uid)
                if cs:
                    p = self.db.obj(uid).payload
                    unit_vs = set(unit_verses(p["lines"])[0])
                    partial = bool(lh_verses - unit_vs)
                    rng = (" (" + psalm_unit_ref(p).split(":", 1)[1] + ")") if partial and ":" in psalm_unit_ref(p) else ""
                    out.append(r"\usemark{" + r"\\ ".join(esc(c) for c in cs) + esc(rng) + "}")
            t = tex(r["text"]) if r["source"] == "LH" else tex(r["text"], marks=False)
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
        if also:
            out.append(r"\par\vspace{2pt}{\footnotesize\rubric{Also used:} " + esc("; ".join(also)) + r".\par}")
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
            uses = self.db.c.execute("""SELECT DISTINCT d.psalter_week, d.weekday, h.hour, oc.slot, d.season, d.rank FROM occurrence oc
                                        JOIN hour_instance h ON h.id=oc.hour_id JOIN day d ON d.key=h.day_key
                                        WHERE oc.object_id=?""", (o.id,)).fetchall()
            codes = sorted({f"{ROMAN[u['psalter_week']]} {DAYABBR[u['weekday']]} {HOURCODE.get(u['hour'], u['hour'])}.{u['slot'][2:]}"
                            for u in uses if u["season"] == "OT" and u["rank"] in ("sunday", "weekday") and u["psalter_week"]})
            out.append(f"\\psalmhead{{Canticle {esc(p['ref'])}}}{{{tex(p.get('title', ''), marks=False)}}}")
            out.append(f"\\objlabel{{{label(o.id)}}}")
            if codes:
                out.append(r"\usemark{" + r"\\ ".join(esc(c) for c in codes) + "}")
            out.append(L.canticle_lines(p["lines"]))
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
        # --- finding the office
        out += [r"\section{Finding the Office}", r"\objlabel{sec:finding}",
                r"\begin{enumerate}[leftmargin=1.4em,itemsep=2pt]",
                r"\item \textbf{The day.} From the calendar, find the season, the week, and any celebration of the date "
                r"(Proper of Saints).",
                r"\item \textbf{Precedence.} If a saint and a day of the season meet, the higher rank prevails "
                r"(solemnity, feast, memorial, weekday; Table of Liturgical Days). In the evening, compare today's "
                r"Vespers with tomorrow's First Vespers the same way.",
                r"\item \textbf{The psalter week.} Ordinary Time week $N$ uses psalter week $((N-1) \bmod 4)+1$; "
                r"Advent weeks 1–4 use I–IV; Lent: Ash Wednesday IV, weeks 1–5 I, II, III, IV, I; Holy Week II; "
                r"Easter weeks 2–7: II, III, IV, I, II, III.",
                r"\item \textbf{Propers.} Turn to that week and day in the Propers of Time; every part of every hour "
                r"is listed there with its seasonal variants side by side, and refers you to the Psalter and Hymns.",
                r"\item \textbf{Saints.} On a solemnity or feast, the Proper of Saints and the Commons supply the "
                r"texts; on a memorial, only what is proper (psalms usually from the current weekday).",
                r"\item \textbf{The Ordinary.} The fixed parts of each hour are below; in the Propers they are named "
                r"only by title.", r"\end{enumerate}",
                r"\rubr{Ribbons: (1) Psalter, (2) Propers of Time, (3) Ordinary, (4) Proper of Saints, (5) Commons, "
                r"(6) Hymns.}"]
        # --- common texts
        out += [r"\section{Opening and Gloria}", r"\objlabel{ord:opening}",
                r"\rubr{Every hour except the Invitatory begins:}\par", sup_pairs(s["opening"]),
                r"\par " + tex(s["gloria_short"]) + r" \rubr{Allelúia (omitted in Lent).}",
                r"\par\vspace{4pt}\rubr{At the end of every psalm and canticle (unless noted):}\par",
                r"\objlabel{ord:gloria}\psl{}{Glória Patri et Fílio \mediant{}}\psk{et Spirítui Sancto.}"
                r"\psc{Sicut erat in princípio et nunc et semper \mediant{}}\psk{et in sǽcula sæculórum. Amen.}"]
        out += [r"\section{Invitatory}", r"\objlabel{ord:invitatory}",
                r"\rubr{Said before the first hour of the day (Office of Readings or Lauds).}\par",
                sup_pairs(s["invitatory_opening"]),
                r"\par\rubr{The antiphon of the day (Propers) is said and repeated after each strophe of Psalm 95, "
                r"\pgref{" + label("ps:95") + r"}, or Psalm 100, 67 or 24.}"]
        for hr, title, gospel in (("OR", "Office of Readings", None), ("LAUDS", "Lauds", ben),
                                  ("MIDDAY", "Daytime Prayer", None), ("VESPERS", "Vespers", mag)):
            out += [f"\\section{{{title}}}", f"\\objlabel{{ord:{hr.lower()}}}"]
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
                out.append(r"\subsection{Dismissal}")
                out += [L.render(o.type, o.payload) for o in dism[hr]]
        out += [r"\section{Pater noster}", r"\objlabel{ord:pater}", tex(s["pater_noster"]),
                r"\par\vspace{4pt}\rubr{Prayer endings abbreviated in the Propers:}\par\begin{itemize}[leftmargin=1em,itemsep=0pt]"]
        out += [r"\item \rubric{" + esc(k) + "} " + tex(v) for k, v in s["conclusions"].items()]
        out.append(r"\end{itemize}")
        if tedeum:
            out += [r"\section{Te Deum}", r"\objlabel{ord:tedeum}", L.te_deum(tedeum.payload)]
        # --- Compline: fixed weekly cycle lives in the Ordinary
        out += [r"\section{Compline}", r"\objlabel{ord:compline}",
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
                if o["slot"] in ("HYMN",):
                    out.append(r"\slotname{Hymn}" + obj_ref(db, ob.id))
                elif o["slot"] == "HYMN_ALT":
                    continue
                elif o["slot"].startswith("ANT") and not o["slot"].endswith("_R"):
                    out.append(r"\slotname{Antiphon}" + L.ant(ob.payload))
                elif o["slot"].startswith("PS"):
                    out.append(r"\slotname{Psalm}" + obj_ref(db, ob.id))
                elif o["slot"] in ("LB", "RB", "ORATIO") or (o["slot"] == "GOSPEL_ANT"):
                    if o["slot"] == "GOSPEL_ANT" and o["seq"] and name != "Saturday (after First Vespers of Sunday)":
                        pass
                    nm = {"LB": "Short reading", "RB": "Responsory", "ORATIO": "Concluding prayer",
                          "GOSPEL_ANT": "Antiphon at the Nunc dimittis"}[o["slot"]]
                    out.append(r"\slotname{" + nm + "}" + L.render(ob.type, ob.payload))
                elif o["slot"] == "BLESSING":
                    out.append(r"\slotname{Blessing}" + L.render(ob.type, ob.payload))
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

    def proper_day(self, wd: str) -> str:
        db = self.db
        days = self.grid_days(wd)
        title = f"Week {ROMAN[self.PW]} — {DAY_NAMES[wd]}"
        uses = labels_for(days, {d["week"] for d in days if d["season"] == "OT"})
        ot_weeks = sorted(d["week"] for d in days if d["season"] == "OT")
        out = [f"\\section{{{title}}}", f"\\objlabel{{prop:{wd}}}",
               r"{\footnotesize\rubric{Used on:} Ordinary Time weeks " + ", ".join(map(str, ot_weeks)) + "; "
               + esc(", ".join(f"{SEASON_LABEL[d['season']]} {d['week']}" for d in days if d['season'] != 'OT')) + r".\par}"]
        week_blocks: dict[int, list] = collections.defaultdict(list)    # OT week → [(hour title, slot, items)]
        sunday_collects = {}
        if wd == "SUN":
            for d in days:
                if d["season"] == "OT":
                    h = db.hour(d["key"], "LAUDS")
                    for o in db.occ(h["id"]):
                        if o["slot"] == "ORATIO":
                            sunday_collects[d["week"]] = o["object_id"]
        for hour in self.hours_for(wd):
            if hour == "V1":
                ht = r"First Vespers \rubric{\footnotesize (Saturday evening)}"
            else:
                ht = HOUR_TITLE[hour]
            ref = {"INV": r"\pgref{ord:invitatory}", "OR": r"\pgref{ord:or}", "LAUDS": r"\pgref{ord:lauds}",
                   "MIDDAY": r"\pgref{ord:midday}"}.get(hour, r"\pgref{ord:vespers}")
            out.append(r"\hourhead{" + ht + r"}{\rubric{Ordinary} " + ref + "}")
            slots = SLOT_ORDER["VESPERS" if hour in ("V1", "V2") else hour]
            cur_sub = None
            for s in slots:
                slot, sub = (s if isinstance(s, tuple) else (s, ""))
                groups = slot_groups(db, days, hour, slot, sub)
                if not groups:
                    continue
                if sub and sub != cur_sub and slot in ("LB",):
                    out.append(r"\par\vspace{2pt}{\scshape\footnotesize\color{rubric}" + SUB_TITLE[sub] + r"}\par")
                    cur_sub = sub
                name = SLOT_NAME.get(slot, slot)
                if sub and slot in ("HYMN", "ANT"):
                    name += f" ({SUB_TITLE[sub]})"
                if slot == "GOSPEL_ANT":
                    name = f"Antiphon at the {GOSPEL.get(hour, 'Gospel canticle')}"
                lines = []
                for g in groups:
                    ot_only = all(d["season"] == "OT" for d in g.days)
                    single_ot = ot_only and len(g.days) == 1
                    if single_ot and slot in ("GOSPEL_ANT",) and wd == "SUN":
                        week_blocks[g.days[0]["week"]].append((hour, slot, g.items))
                        continue
                    if single_ot and slot == "ORATIO" and wd == "SUN":
                        continue     # Sunday collect: listed with the week below
                    if single_ot and slot == "ORATIO" and hour == "OR" and wd != "SUN":
                        oid = g.items[0][1]
                        # weekday Office of Readings uses the collect of the preceding Sunday
                        sun = db.hour(f"OT.{g.days[0]['week']:02d}.SUN", "LAUDS")
                        if sun and any(o["object_id"] == oid for o in db.occ(sun["id"])):
                            week_blocks[g.days[0]["week"]].append(("OR", "ORATIO_REF", g.items))
                            continue
                    if slot in ("LECT1", "LECT2"):
                        for _, oid in g.items:
                            self.or_readings.append((g.label, oid))
                    body = []
                    for cond, oid in g.items:
                        r = obj_ref(db, oid) if slot not in ("ANT", "ANT1", "ANT2", "ANT3", "GOSPEL_ANT", "INV_ANT") else L.ant(db.obj(oid).payload)
                        body.append((r"\condlabel{" + esc(cond) + "}" if cond else "") + r)
                    lines.append(r"\variant{" + esc(g.label) + "}{" + r"\par ".join(body) + "}")
                collapsed = [x for x in lines]
                if slot in ("LECT1", "LECT2") and lines:
                    # one compact paragraph: each season-week with the reading's opening line and page
                    items = []
                    for g in groups:
                        for _, oid in g.items:
                            items.append(r"{\footnotesize\scshape\color{rubric}" + esc(g.label) + "} " + obj_ref(db, oid))
                    collapsed = [r"\par\noindent{\small " + r"\enspace·\enspace ".join(items) + r"}\par"]
                if slot == "ORATIO" and hour == "OR" and wd != "SUN" and not collapsed:
                    collapsed = [r"\variant{Per annum}{\rubr{Collect of the preceding Sunday (listed with that Sunday).}}"]
                if collapsed:
                    out.append(r"\slotname{" + name + "}" + "\n".join(collapsed))
            if hour in ("LAUDS", "VESPERS", "V1", "V2"):
                gname = GOSPEL[hour]
                out.append(r"\par{\footnotesize\rubric{" + gname + r",} \pgref{ord:" + gname.lower() + r"}; "
                           r"\rubric{Pater noster,} \pgref{ord:pater}.}\par")
            if hour == "OR" and wd == "SUN":
                out.append(r"\par{\footnotesize\rubric{Te Deum} (except in Lent), \pgref{ord:tedeum}.}\par")
        cname = "saturday" if False else ("monday" if wd == "MON" else "sunday")
        out.append(r"\hourhead{Compline}{\rubric{Ordinary} \pgref{ord:compline:" + cname + "}}")
        if wd == "SUN":
            out.append(r"{\footnotesize After First Vespers: \pgref{ord:compline:saturday}; after Second Vespers: "
                       r"\pgref{ord:compline:sunday}.\par}")
        if week_blocks or sunday_collects:
            out.append(r"\subsection{Ordinary Time: proper to each week}")
            out.append(r"\rubr{The Gospel canticle antiphons follow the Sunday Gospel of Years A, B and C; the collect "
                       r"of the Sunday is also said at the Office of Readings on the weekdays of that week.}")
            for wk in sorted(set(week_blocks) | set(sunday_collects)):
                out.append(r"\par\needspace{4\baselineskip}\vspace{4pt}{\scshape\color{rubric}" + f"Week {wk} of Ordinary Time" + r"}\par")
                for hour, slot, items in week_blocks.get(wk, []):
                    if slot == "ORATIO_REF":
                        continue
                    hn = {"V1": "First Vespers", "LAUDS": "Lauds", "V2": "Second Vespers"}.get(hour, hour)
                    body = r"\par ".join(r"\condlabel{" + esc(c) + "}" + L.ant(db.obj(o).payload) for c, o in items)
                    out.append(r"\variant{" + hn + "}{" + body + "}")
                if wk in sunday_collects:
                    oid = sunday_collects[wk]
                    out.append(r"\variant{Collect}{" + f"\\objlabel{{{label('collect:' + oid)}}}" + L.render("oratio", db.obj(oid).payload) + "}")
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
                out.append(r"\par{\footnotesize\rubric{Collect at the Office of Readings (from the Sunday):} " + "; ".join(refs) + r".\par}")
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
                out.append(r"\subsection{" + ("First reading" if o["slot"] == "LECT1" else "Second reading") + "}")
                out.append(f"\\objlabel{{{label(ob.id)}}}")
                out.append(L.reading(ob.payload))
            else:
                ref = ob.payload.get("ref", "")
                out.append(r"\par\vspace{3pt}{\footnotesize\rubric{Responsory " + esc(ref) + r"}}\par")
                out.append(L.pairs(ob.payload))
        return "\n".join(out)

    # ---------------------------------------------------------------- whole document
    def body(self) -> str:
        self.collect()
        parts = [self.psalter(), self.hymns(), self.ordinary(), self.propers(), self.readings()]
        body = "\n\n".join(parts)
        # references to readings not printed in the POC: neutralise their page refs
        printed = set(re.findall(r"\\objlabel\{([^}]*)\}", body))
        def fix(m):
            return m.group(0) if m.group(1) in printed else r"{\footnotesize\color{black!55}[not in POC]}"
        body = re.sub(r"\\seepage\{([^}]*)\}", fix, body)
        body = re.sub(r"\\pref\{([^}]*)\}", lambda m: m.group(0) if m.group(1) in printed else r"{\footnotesize\color{black!55}[not in POC]}", body)
        return body


def write_poc() -> str:
    out = BOOK / "generated"
    out.mkdir(parents=True, exist_ok=True)
    body = POC().body()
    (out / "poc_body.tex").write_text(body, encoding="utf-8")
    return str(out / "poc_body.tex")
