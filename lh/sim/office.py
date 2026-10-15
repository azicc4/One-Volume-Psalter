"""One hour of a celebration as the ordered steps a reader takes: each text said, the page it is printed on, and the
page that announces it (the hour heading of the office it comes from).

Assembly (GILH 234–236, simplified):
- the office of the day as printed (its hour instance in the database);
- memorials: the weekday's hour, with every slot the memorial supplies taken from the memorial (Daytime Prayer and
  Compline entirely of the weekday);
- feasts and solemnities of saints: missing slots from the Common referred to, then the psalms of Sunday Week I
  (Lauds, Vespers), then the weekday (Daytime Prayer);
- Daytime Prayer: Sext; the Invitatory: Psalm 95; alternatives ("Vel …") are not taken; OT Sunday antiphons follow
  the year A/B/C.
"""
from __future__ import annotations

import collections
import json
import re
from dataclasses import dataclass

from lh.model.attribute import compline_form, is_grid

ORDER = {
    "INV": ["OPENING", "INV_ANT", "INV_PSALM", "INV_ANT_R"],
    "OR": ["OPENING", "HYMN", "ANT1", "PS1", "ANT1_R", "ANT2", "PS2", "ANT2_R", "ANT3", "PS3", "ANT3_R", "OR_VERSE",
           "LECT1", "RESP1", "LECT2", "RESP2", "TE_DEUM", "ORATIO", "CONCLUSION"],
    "LAUDS": ["OPENING", "HYMN", "ANT1", "PS1", "ANT1_R", "ANT2", "PS2", "ANT2_R", "ANT3", "PS3", "ANT3_R", "LB", "RB",
              "GOSPEL_ANT", "GOSPEL_CANT", "GOSPEL_ANT_R", "PRECES", "PATER", "ORATIO", "CONCLUSION"],
    "MIDDAY": ["OPENING", "HYMN", "ANT", "ANT1", "PS1", "ANT1_R", "ANT2", "PS2", "ANT2_R", "ANT3", "PS3", "ANT3_R",
               "ANT_R", "LB", "V", "ORATIO", "CONCLUSION"],
    "COMPLINE": ["OPENING", "HYMN", "ANT", "ANT1", "PS1", "ANT_R", "ANT1_R", "ANT2", "PS2", "ANT2_R", "LB", "RB",
                 "GOSPEL_ANT", "GOSPEL_CANT", "GOSPEL_ANT_R", "ORATIO", "BLESSING", "MARIAN"],
}
for _h in ("VESPERS", "V1", "V2"):
    ORDER[_h] = ORDER["LAUDS"]
ORDER["COMPLINE1"] = ORDER["COMPLINE"]
PSALM_SLOT = re.compile(r"^PS\d$")
DISMISSAL = {"OR": "or", "LAUDS": "lauds", "MIDDAY": "midday", "VESPERS": "vespers", "V1": "vespers", "V2": "vespers",
             "COMPLINE": "compline", "COMPLINE1": "compline"}
SUNDAY_WK1 = "OT.05.SUN"                     # a Sunday of psalter week I (its Lauds and Vespers psalms)


@dataclass
class Step:
    hour: str
    slot: str
    what: str                                # object id, or the Ordinary label of a fixed part
    page: int | None                         # page index where it is printed
    via: int | None                          # page index of the heading that announces it
    source: str                              # day key the text comes from

    def as_dict(self):
        return {"slot": self.slot, "what": self.what, "page": self.page, "via": self.via, "source": self.source}


class Offices:
    def __init__(self, con, layout, calendar):
        self.con, self.L, self.cal = con, layout, calendar
        self.days = calendar.days
        self.links = {r["occurrence_id"]: r["object_id"] for r in con.execute("SELECT * FROM link_target")}
        self.missing = collections.Counter()       # texts whose page could not be found

    # ------------------------------------------------------------------ database
    EVENING = {"HOLY.THU": "TRIDUUM.THU"}         # Holy Thursday: Vespers and Compline belong to the Triduum

    def instance(self, key: str, hour: str):
        q = "SELECT * FROM hour_instance WHERE day_key=? AND hour=? ORDER BY (copy IS NOT NULL), id"
        return self.con.execute(q, (key, hour)).fetchone() or (
            self.con.execute(q, (self.EVENING[key], hour)).fetchone() if key in self.EVENING else None)

    def heading(self, key: str, hour: str) -> int | None:
        d = self.days.get(key)
        if d is not None and hour in ("COMPLINE", "COMPLINE1"):
            form = compline_form(d, hour)
            if form:
                return self.L.page(f"ord:compline:{form}")
        if d is not None and is_grid(d):
            return self.L.page(f"hh:grid:{d['psalter_week']}.{d['weekday']}:{hour}") \
                or self.L.page(f"grid:{d['psalter_week']}.{d['weekday']}")
        for k in (key, self.EVENING.get(key)):
            p = k and (self.L.page(f"hh:{k}:{hour}") or self.L.page(f"hr:{k}:{hour}"))
            if p is not None:
                return p
        return self.L.page(f"day:{key}")

    def groups(self, key: str, hour: str, cel) -> "collections.OrderedDict[str, tuple]":
        """slot → (what, page) of one printed hour; one choice per slot."""
        h = self.instance(key, hour)
        out = collections.OrderedDict()
        if not h:
            return out
        for o in self.con.execute("SELECT * FROM occurrence WHERE hour_id=? ORDER BY seq", (h["id"],)):
            slot, sub = o["slot"] or "", o["sub"] or ""
            if o["type"] in ("label", "marker", "rubric") or not slot or slot in ("PREP_PRAYER", "HYMN_ALT", "SUBST",
                                                                                     "MEMORIAL", "COMPLEMENTARY"):
                continue
            if hour == "MIDDAY" and sub and sub != "SEXT":
                continue
            cond = json.loads(o["cond"] or "{}")
            if cond.get("alt") or cond.get("variant") == "night":
                continue
            if cond.get("year") and cond["year"] != cel.year_cycle:
                continue
            if slot == "LINK":                          # "Ps 117 (118) I" on a feast's Daytime Prayer
                tgt = self.links.get(o["id"])
                if not tgt:
                    continue
                n = sum(1 for k in out if PSALM_SLOT.match(k)) + 1
                slot = f"PS{n}"
            if slot in out:
                continue
            what, page = self.locate(o, slot, hour)
            if what:
                out[slot] = (what, page)
        return out

    def locate(self, o, slot: str, hour: str) -> tuple[str | None, int | None]:
        if o["type"] in ("link", "ordinary_ref"):
            tgt = self.links.get(o["id"])
            if tgt and slot not in ("CONCLUSION", "MARIAN", "PATER"):
                return tgt, self.L.object_page(tgt)
            lab = {"PATER": "ord:pater", "MARIAN": "ord:marian", "INV_PSALM": self.L.book.inv_label,
                   "CONCLUSION": f"ord:dismissal:{DISMISSAL.get(hour, '')}"}.get(slot)
            if not lab:
                return None, None
            return lab, self.L.page(lab) or self.L.page("ord:dismissal")
        if not o["object_id"]:
            return None, None
        return o["object_id"], self.L.object_page(o["object_id"])

    # ------------------------------------------------------------------ assembly
    def common_of(self, key: str) -> str | None:
        rows = self.con.execute("SELECT r.target, count(*) n FROM reference r JOIN hour_instance h ON h.id=r.hour_id "
                                "WHERE h.day_key=? AND r.kind='de_communi' GROUP BY r.target ORDER BY n DESC", (key,))
        r = rows.fetchone()
        return r["target"] if r else None

    def hour(self, cel, hour: str) -> list[Step]:
        """Steps of one hour of the celebration `cel` (hour: INV OR LAUDS MIDDAY VESPERS V1 V2 COMPLINE COMPLINE1)."""
        layers = []                                     # (key, hour) in order of precedence
        key, temporal = cel.office, cel.temporal
        if hour in ("COMPLINE", "COMPLINE1"):
            base = key if self.instance(key, hour) and not cel.is_saint else temporal
            if not self.instance(base, hour):
                base = SUNDAY_WK1 if hour == "COMPLINE1" or cel.rank <= 7 else temporal
            layers = [(base, hour)]
        elif cel.is_saint and cel.kind in ("memorial", "optional_memorial"):
            if hour == "MIDDAY":
                layers = [(temporal, hour)]
            else:
                th = hour if self.instance(temporal, hour) else "VESPERS"
                layers = [(key, hour), (temporal, th)]
                com = self.common_of(key)
                if com:
                    layers.append((com, "VESPERS" if hour in ("V2", "VESPERS") and not self.instance(com, hour)
                                   else hour))
        else:
            layers = [(key, hour)]
            if cel.is_saint:
                com = self.common_of(key)
                if com:
                    layers.append((com, hour if self.instance(com, hour) else ("V2" if hour == "VESPERS" else hour)))
            if hour in ("LAUDS", "V1", "V2", "VESPERS"):
                layers.append((SUNDAY_WK1, "LAUDS" if hour == "LAUDS" else ("V1" if hour == "V1" else "V2")))
            if hour == "MIDDAY":
                layers.append((temporal, hour))
        chosen = collections.OrderedDict()
        for k, h in layers:
            g = self.groups(k, h, cel)
            via = self.heading(k, h)
            psalms_taken = any(PSALM_SLOT.match(s) for s in chosen)
            for slot, (what, page) in g.items():
                if slot in chosen:
                    continue
                # psalmody comes whole from one layer (antiphons with their psalms)
                if psalms_taken and (PSALM_SLOT.match(slot) or slot.startswith("ANT") and slot[3:4].isdigit()):
                    continue
                chosen[slot] = Step(hour, slot, what, page, via, k)
        order = ORDER.get(hour, list(chosen))
        k0, h0 = layers[0]
        head = self.heading(k0, h0)
        steps = [Step(hour, "HEAD", f"heading {k0} {h0}", head, head, k0)]        # open the book at the hour
        te_deum = cel.kind in ("sunday", "solemnity", "feast", "feast_lord", "octave", "triduum") \
            and not cel.temporal.startswith(("LENT.", "HOLY."))
        steps += [chosen[s] for s in order if s in chosen and (s != "TE_DEUM" or te_deum)]
        if hour == "INV" and steps and any(s.slot == "INV_ANT" for s in steps):
            ant = next(s for s in steps if s.slot == "INV_ANT")
            steps.append(Step(hour, "INV_ANT_R", ant.what, ant.page, ant.via, ant.source))
        self.copies(steps, layers)
        for s in steps:
            if s.page is None:
                self.missing[(s.slot, s.what)] += 1
        return [s for s in steps if s.page is not None]

    def copies(self, steps, layers):
        """A text printed again in full where it is said (whole Compline, B-15; the weekly psalter of
        exp/weekly-psalter) carries a cp:<location>:<label> label: the reader says it there."""
        from lh.model.attribute import location
        from lh.render.latex import label
        aliases = self.L.book.aliases
        hours = dict(layers)
        for s in steps:
            d = self.days.get(s.source)
            if d is None or s.slot == "HEAD":
                continue
            loc = location(d, hours.get(s.source, s.hour), s.slot)
            p = self.L.page(f"cp:{loc}:{label(aliases.get(s.what, s.what))}")
            if p is not None:
                s.page = p

    # ------------------------------------------------------------------ a whole day
    def day(self, cel, tomorrow, hours=("INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE")) -> list[Step]:
        """The hours of one civil day. The evening follows tomorrow when tomorrow begins with First Vespers."""
        steps = []
        first_v = self.cal.has_first_vespers(tomorrow) and self.instance(tomorrow.office, "V1") is not None
        for h in hours:
            if h == "VESPERS":
                if first_v:
                    steps += self.hour(tomorrow, "V1")
                else:
                    steps += self.hour(cel, "V2" if self.instance(cel.office, "V2") else "VESPERS")
            elif h == "COMPLINE":
                steps += self.hour(tomorrow, "COMPLINE1") if first_v else self.hour(cel, "COMPLINE")
            else:
                steps += self.hour(cel, h)
        return steps
