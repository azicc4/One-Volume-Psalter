"""The full one-volume book, generated from build/lh.sqlite (`python -m lh book`).

Every object is printed once, at the location `object.home_label` gives it (lh/model/attribute.py), with a LaTeX label;
every other use is a page reference to that label. Book order and ribbons (docs/architecture.md):

  1 Proper of Saints · 2 Commons (+ Office of the Dead, Saturday memorial of the BVM) · 3 Ordinary (incl. the weekly
  Compline cycle, invitatory psalms, complementary psalmody, dismissals, Marian antiphons, Te Deum) · 4 Proper of Time
  (four-week grid with the seasons side by side, Ordinary Time weekly propers, wholly proper days) · 5 Hymns ·
  6-9 Psalter and Canticles · 10 Office of Readings readings · Indexes.

`\\budget{<section>/<part>}` labels mark the parts counted by the page-budget report (lh/render/budget.py).
"""
from __future__ import annotations

import collections
import json
import re

from lh.config import BOOK
from lh.model.attribute import (COMMON_ORDER, HOURS, ORD_ORDER, PROPER_DAYS, WD, Order, content, day_section,
                                 is_grid, location, ord_chapter, saint_date)
from lh.model.canon import paragraphs, plain, plain_text, psalm_base
from lh.model.days import DAY_NAMES
from lh.render import latex as L
from lh.render.common import (DB, GOSPEL, HOUR_TITLE, ROMAN, SEASON_LABEL, SEASON_ORDER, SLOT_NAME, SLOT_ORDER,
                              SUB_TITLE, Obj, PsalterWriter, canticle_ref, cant_key, cond_text, finding_the_office,
                              labels_for, load_supplement, opening_block, psalm_unit_ref, ribbon_refs, slot_groups,
                              unit_anchor)
from lh.render.latex import esc, label, tex

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
RANK_EN = {"solemnity": "Solemnity", "feast": "Feast", "feast_lord": "Feast of the Lord", "memorial": "Memorial",
           "optional_memorial": "Optional memorial", "all_souls": "Commemoration of all the faithful departed",
           "commemoration": "Commemoration"}
COMMON_LA = {"COMMON.DEDICATION": "Dedicationis ecclesiæ", "COMMON.BVM": "Beatæ Mariæ Virginis",
             "COMMON.APOSTLES": "Apostolorum", "COMMON.MARTYRS.SEVERAL": "plurium Martyrum",
             "COMMON.MARTYRS.ONE": "unius Martyris", "COMMON.PASTORS": "Pastorum",
             "COMMON.DOCTORS": "Doctorum Ecclesiæ", "COMMON.VIRGINS": "Virginum",
             "COMMON.HOLY_MEN": "Sanctorum virorum", "COMMON.HOLY_WOMEN": "Sanctarum mulierum"}
SOURCE_SEASON = {"PA": "Per annum", "SPA": "Per annum", "SP": "Eastertide", "SQ": "Lent",
                 "SADV": "Advent and Christmas", "ADV": "Advent and Christmas", "LQP": "Lent and Eastertide",
                 "COM": "Commons"}
COM_COPY = {"OT": "Per annum", "ADV": "Advent and Christmas", "LENT": "Lent", "EAS": "Eastertide"}
SKIP_SLOTS = {"OPENING", "PREP_PRAYER", "GOSPEL_CANT", "PATER", "CONCLUSION"}
PSALMODY = re.compile(r"^(ANT\d?|PS\d+)$")
BOILER = re.compile(r"^(Quæ tamen omittuntur|Ante Officium quod a solo|Psalmus invitatorius|Postea laudabiliter"
                    r"|Deinde dicitur, etiam a solo|In fine huius cantici non dicitur|_+$|Vel:?$|Alia$|Vel$)")
TIME_PARTS = [
    ("Advent: 17–24 December", lambda k: k.startswith("ADV.")),
    ("Christmas Time", lambda k: k.startswith(("CHR.", "FEAST.")) or k in ("SOL.CHRISTMAS", "SOL.MARY_MOTHER_OF_GOD",
                                                                          "SOL.EPIPHANY")),
    ("Ash Wednesday and the days after", lambda k: k.startswith("LENT.0.")),
    ("Holy Week and the Paschal Triduum", lambda k: k.startswith(("HOLY.", "TRIDUUM."))),
    ("Easter Sunday and its Octave", lambda k: k.startswith("EAS.")),
    ("Ascension and Pentecost", lambda k: k in ("SOL.ASCENSION", "SOL.PENTECOST")),
    ("Solemnities of the Lord in Ordinary Time", lambda k: k.startswith("SOL.")),
]


def card_line(gospel: str) -> str:
    """After the Gospel canticle antiphon: the canticle and the Pater noster are on the Ordinary card (B-14), and in
    the Ordinary at the pages given."""
    card = "2" if gospel == "Magnificat" else "1"
    return (r"\par{\footnotesize\rubric{" + gospel + r":} \cardref{" + card + r"}, \pgref{ord:" + gospel.lower()
            + r"}; \rubric{Pater noster:} \cardref{1}, \pgref{ord:pater}.}\par")


def hh_label(where: str, hour: str) -> str:
    """Invisible label at an hour heading (hh:<day key or grid:pw.DOW>:<hour>), so lh/sim can find where each hour
    starts. It sits inside the heading text, so it cannot move a line or page break."""
    return r"\objlabel{hh:" + where + ":" + hour + "}"


def hour_title(hour: str) -> str:
    return HOUR_TITLE.get(hour) or "Texts"


def copy_label(h) -> str:
    """Readable label of a printing (variant) of an hour."""
    cp = h["copy"] or ""
    src = h["source"]
    if src == "COM" and cp in COM_COPY:
        return COM_COPY[cp]
    if cp.startswith("altera"):
        rest = cp[6:].strip()
        return f"Alternative office ({rest})" if rest else "Alternative office"
    if cp == "commemoratio":
        return "Commemoration"
    if cp == "propria":
        return "Proper parts"
    if cp == "sollemnitas":
        return "Solemnity"
    if cp.startswith("Ascension"):
        return "Ascension on " + ("Sunday" if "Sun" in cp else "Thursday")
    m = re.match(r"^(\d+ \w+)(?:, Epiphany (6 Jan|Sunday))?( #\d+)?$", cp)
    if src == "ADV" and m:
        s = f"Advent from {m.group(1)}"
        if m.group(2):
            s += "; Epiphany " + ("on 6 Jan" if m.group(2) == "6 Jan" else "on Sunday")
        return s
    if not cp:
        return SOURCE_SEASON.get(src, src)
    return cp


def incipit(o: Obj, n: int = 6) -> str:
    t = plain_text(o.type, o.payload)
    if o.type == "lectio_brevis" and o.payload.get("ref"):
        pass
    w = t.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


class Book(PsalterWriter):
    def __init__(self):
        self.db = DB()
        self.objs = self.db.load_all()
        self.supp = load_supplement()
        self.order = Order(self.db.c)
        self.printed: set[str] = set()
        self.homed: dict[str, list[str]] = collections.defaultdict(list)
        for o in self.objs.values():
            if o.home_label:
                self.homed[o.home_label].append(o.id)
        self.kind: dict[tuple, tuple] = {}
        for r in self.db.c.execute("SELECT * FROM reference"):
            self.kind[(r["hour_id"], r["object_id"])] = (r["kind"], r["target"])
        self.link_obj = {r["occurrence_id"]: r["object_id"]
                         for r in self.db.c.execute("SELECT occurrence_id, object_id FROM link_target")}
        self.days = self.db.day_rows
        self.read_days: set[str] = set()        # days with a heading in the readings section (rd:<key>)
        self.aliases: dict[str, str] = {}       # printing variant → printed object (psalms/canticles/Te Deum)
        self.stats = collections.Counter()
        self.compline_units = {}               # weekly form -> psalm units (for "as on Sunday" references)
        self.flushed: list[tuple] = []          # (location, object) printed by the end-of-hour fallback
        self.cp_labels: set[str] = set()        # labels of texts printed again in full (whole Compline)

    # ================================================================== emit: print at home, refer elsewhere
    def anchor(self, o: Obj) -> str:
        if o.id in self.aliases:
            return self.anchor(self.objs[self.aliases[o.id]])
        return unit_anchor(o)

    def full(self, o: Obj) -> str:
        self.printed.add(o.id)
        self.stats["printed"] += 1
        lab = f"\\objlabel{{{label(o.id)}}}"
        p = o.payload
        if o.type == "ant":
            return lab + L.ant(p)
        if o.type in ("psalm", "canticle"):
            head = psalm_unit_ref(p) if o.type == "psalm" else "Canticle " + canticle_ref(p)
            return lab + r"{\footnotesize\rubric{" + esc(head) + r"}}\par " + L.canticle_lines(p["lines"])
        if o.type == "reading":
            return lab + L.reading(p)
        if o.type == "hymn":
            return lab + L.hymn(p)
        return lab + L.render(o.type, p)

    def ref(self, o: Obj, hour_id=None) -> str:
        self.stats["refs"] += 1
        p = o.payload
        pg = r"\enspace\seepage{" + self.anchor(o) + "}"
        kind = self.kind.get((hour_id, o.id)) if hour_id else None
        pre = ""
        if kind and kind[0] == "de_communi":
            pre = r"{\footnotesize\rubric{de Communi " + esc(COMMON_LA.get(kind[1], kind[1])) + r":}} "
            self.stats["de_communi"] += 1
        if o.type == "psalm":
            return pre + f"{esc(psalm_unit_ref(p))} {{\\footnotesize ({esc(p['vulg'])})}}" + pg
        if o.type == "canticle":
            return pre + "Canticle " + esc(canticle_ref(p)) + pg
        if o.type == "hymn":
            return pre + r"\textit{" + tex(p["stanzas"][0][0], marks=False) + "}" + pg
        if o.type == "reading":
            intro = plain(" ".join(p.get("intro", []))) or incipit(o, 8)
            return pre + r"{\small " + esc(intro) + "}" + pg
        if o.type == "te_deum":
            return pre + "Te Deum" + pg
        return pre + r"{\small " + esc(incipit(o)) + "}" + pg

    def copy(self, o: Obj, loc: str) -> str:
        """A text printed again in full where it is said (whole Compline, B-15). Its home stays the one place
        references point to; the copy carries only a cp: label, so lh/sim knows it is there."""
        self.stats["copies"] += 1
        p = o.payload
        cp = f"cp:{loc}:{label(o.id)}"
        lab = "" if cp in self.cp_labels else f"\\objlabel{{{cp}}}"
        self.cp_labels.add(cp)
        if o.type in ("psalm", "canticle"):
            head = psalm_unit_ref(p) if o.type == "psalm" else "Canticle " + canticle_ref(p)
            return lab + r"{\footnotesize\rubric{" + esc(head) + r"}}\par " + L.canticle_lines(p["lines"]) + r"\gloria"
        if o.type == "ant":
            return lab + L.ant(p)
        if o.type == "hymn":
            return lab + L.hymn(p)
        return lab + L.render(o.type, p)

    def emit(self, oid: str, loc: str, hour_id=None, whole: bool = False) -> str:
        o = self.objs[oid]
        if o.home_label == loc and oid not in self.printed and oid not in self.aliases:
            return self.full(o)
        if whole:
            return self.copy(self.objs[self.aliases.get(oid, oid)], loc)
        return self.ref(o, hour_id)

    def flush(self, locs, title: str = "") -> list[str]:
        """Print every object homed at these locations that has not been printed yet."""
        out = []
        for loc in locs:
            for oid in self.homed.get(loc, []):
                if oid in self.printed or oid in self.aliases:
                    continue
                o = self.objs[oid]
                if not out and title:
                    out.append(r"\sublabel{" + title + "}")
                out.append(r"\variant{" + esc(SLOT_NAME.get(o.type.upper(), o.type.replace("_", " ").title()))
                           + "}{" + L.citation(o.type, o.payload) + "}{" + self.full(o) + "}")
                self.stats["flushed"] += 1
                self.flushed.append((loc, oid))
        return out

    def flush_prefix(self, prefix: str, title: str) -> str:
        locs = sorted((l for l in self.homed if l.startswith(prefix)), key=self.order.loc_rank)
        out = self.flush(locs)
        if not out:
            return ""
        return "\n".join([r"\section{" + title + "}", r"\rubr{Texts of this part not printed above.}"] + out)

    # ================================================================== generic hour renderer
    def items_by_slot(self, h) -> "collections.OrderedDict":
        od = collections.OrderedDict()
        for o in content(self.db.occ(h["id"])):
            if o["slot"] in SKIP_SLOTS:
                continue
            od.setdefault((o["slot"] or "", o["sub"] or ""), []).append((cond_text(o["cond"]), o["object_id"]))
        return od

    def slot_title(self, slot: str, sub: str, hour: str) -> str:
        name = SLOT_NAME.get(slot.replace("_R", ""), slot.replace("_", " ").title())
        if slot.startswith("PS") and slot[2:].isdigit() and int(slot[2:]) > 3:
            name = f"Psalm {slot[2:]}"
        if slot == "GOSPEL_ANT":
            name = f"Antiphon at the {GOSPEL.get(hour, 'Gospel canticle')}"
        if sub and slot in ("HYMN", "ANT") and sub in SUB_TITLE:
            name += f" ({SUB_TITLE[sub]})"
        return name

    def item_lines(self, items, loc, hour_id, whole: bool = False) -> str:
        return r"\par ".join((r"\condlabel{" + esc(c) + "}" if c else "") + self.emit(oid, loc, hour_id, whole)
                             for c, oid in items)

    def link_line(self, o) -> str | None:
        slot = o["slot"] or ""
        txt = json.loads(o["extra"] or "{}").get("text") or (self.objs[o["object_id"]].payload.get("text", "")
                                                              if o["object_id"] else "")
        if slot in ("CONCLUSION", "INV_PSALM", "MARIAN"):
            return None
        tgt = self.link_obj.get(o["id"])
        if slot in ("HYMN_ALT", "LECT2") and tgt and self.objs[tgt].type in ("hymn", "reading"):
            name = "Or the hymn" if slot == "HYMN_ALT" else "Second reading"
            return r"\variant{}{}{\condlabel{" + name + ":}" + self.ref(self.objs[tgt]) + "}"
        return r"\par{\lrubr{" + tex(txt, marks=False) + r"}}\par" if txt else None

    def compline_as(self, h) -> str | None:
        units = tuple(o["object_id"] for o in content(self.db.occ(h["id"])) if re.fullmatch(r"PS\d", o["slot"] or ""))
        for form, us in self.compline_units.items():
            if us == units:
                return form
        return None

    def render_hour(self, day_key: str, hour: str, loc: str, extra_head: str = "") -> list[str]:
        insts = self.db.instances(day_key, hour)
        if not insts:
            return []
        base = insts[0]
        bid = base["id"]
        out = [r"\hourhead{" + hh_label(day_key, hour) + hour_title(hour) + extra_head + "}{"
               + self.hour_ribbons(day_key, hour, base) + "}"]
        if hour in ("COMPLINE", "COMPLINE1") and not any(
                oid not in self.printed and self.objs[oid].home_label == loc
                for h in insts for _, its in self.items_by_slot(h).items() for _, oid in its):
            form = self.compline_as(base)
            if form:
                out.append(r"{\footnotesize\rubric{As in the Ordinary:} " + FORM_NAME[form] + r", \pgref{ord:compline:"
                           + form + r"}.\par}")
                self.stats["compline_as_form"] += 1
                return out
        base_items = self.items_by_slot(base)
        others = [(copy_label(h), h, self.items_by_slot(h)) for h in insts[1:]]
        # Saints/Commons: "Omnia de Communi" when every text of the hour is the same Common's
        if day_section(day_key) == "saints":
            allitems = [oid for its in base_items.values() for _, oid in its]
            kinds = {self.kind.get((bid, oid)) for oid in allitems}
            if allitems and len(kinds) == 1 and None not in kinds and next(iter(kinds))[0] == "de_communi" \
                    and not others and all(self.objs[oid].home_label != loc for oid in allitems):
                ck = next(iter(kinds))[1]
                out.append(r"\variant{}{}{\rubric{Omnia de Communi " + esc(COMMON_LA.get(ck, ck)) + r",} \pgref{"
                           + f"hr:{ck}:{hour}" + "}.}")
                self.stats["omnia_de_communi"] += 1
                self.stats["de_communi"] += len(allitems)
                return out
        done_slots = set()
        cur_sub = None
        last_rubric = None
        occs = self.db.occ(bid)
        i = 0
        while i < len(occs):
            o = occs[i]
            i += 1
            if o["type"] in ("label", "marker"):
                continue
            if o["type"] == "rubric":
                txt = self.objs[o["object_id"]].payload.get("text", "") if o["object_id"] else ""
                if not txt or BOILER.match(plain(txt)) or (o["cond"] and len(plain(txt)) < 60) or txt == last_rubric:
                    continue
                last_rubric = txt
                out.append(r"\par{\lrubr{" + tex(txt, marks=False) + r"}}\par")
                continue
            if o["type"] == "link":
                ln = self.link_line(o)
                if ln:
                    out.append(ln)
                continue
            key = (o["slot"] or "", o["sub"] or "")
            if key in done_slots or key not in base_items:
                continue
            done_slots.add(key)
            slot, sub = key
            if sub and sub != cur_sub and sub in SUB_TITLE and slot in ("LB", "V", "ORATIO"):
                out.append(r"\sublabel{" + SUB_TITLE[sub] + "}")
                cur_sub = sub
            elif sub and sub != cur_sub and sub not in SUB_TITLE:
                out.append(r"\sublabel{" + esc(sub) + "}")
                cur_sub = sub
            if PSALMODY.match(slot):
                # antiphons and psalms under one heading, one line each (Ant. 1 …, Ps …)
                keys = [key] + [k for k in base_items if k not in done_slots and k[1] == sub and PSALMODY.match(k[0])]
                done_slots.update(keys)
                block = [r"\slotname{Psalmody}{}"]
                for k in keys:
                    block += self.slot_lines(k, base_items[k], others, loc, bid, psalmody=True)
                out.append("\n".join(block))
                continue
            items = base_items[key]
            cites = {L.citation(self.objs[oid].type, self.objs[oid].payload) for _, oid in items} - {""}
            cite = next(iter(cites)) if len(cites) == 1 else ""
            block = [r"\slotname{" + self.slot_title(slot, sub, hour) + "}{" + cite + "}"]
            block += self.slot_lines(key, items, others, loc, bid)
            out.append("\n".join(block))
        # slots printed only in another printing
        for lab_, h, its in others:
            for key, v in its.items():
                if key in base_items:
                    continue
                slot, sub = key
                out.append(r"\slotname{" + self.slot_title(slot, sub, hour) + "}{}"
                           + r"\variant{" + esc(lab_) + "}{}{" + self.item_lines(v, loc, h["id"]) + "}")
                base_items[key] = v
        if hour in GOSPEL and hour not in ("COMPLINE", "COMPLINE1"):
            out.append(card_line(GOSPEL[hour]))
        out += self.flush([loc])
        return out

    def slot_lines(self, key, items, others, loc, bid, psalmody: bool = False) -> list[str]:
        """The base printing's texts of one slot, then each other printing's when they differ."""
        slot = key[0]
        tag = ""
        if psalmody and slot.startswith("ANT"):
            tag = r"\rubric{Ant." + (r"\," + slot[3:] if slot[3:] else "") + r"}\enspace "
        lines = [r"\variant{}{}{" + tag + self.item_lines(items, loc, bid) + "}"]
        seen_var = {tuple(items)}
        for lab_, h, its in others:
            v = its.get(key)
            if v and tuple(v) not in seen_var:
                seen_var.add(tuple(v))
                lines.append(r"\variant{" + esc(lab_) + "}{}{" + tag + self.item_lines(v, loc, h["id"]) + "}")
        return lines

    def hour_ribbons(self, day_key: str, hour: str, base) -> str:
        # B-16: the fixed parts are on the Ordinary card; the Ordinary is marked (ribbon 3) for Daytime Prayer and
        # Compline only
        if hour == "INV":
            return r"\cardref{1}"
        anchor = {"MIDDAY": "ord:midday", "COMPLINE": "ord:compline", "COMPLINE1": "ord:compline"}.get(hour)
        parts = [r"\ribbon{O}{\pg{" + anchor + "}}"] if anchor else []
        labs = []
        for o in content(self.db.occ(base["id"])):
            if re.fullmatch(r"PS\d", o["slot"] or ""):
                labs.append(r"\pg{" + self.anchor(self.objs[o["object_id"]]) + "}")
        if labs:
            parts.append(r"\ribbon{P}{" + ", ".join(dict.fromkeys(labs)) + "}")
        if hour == "OR" and day_key in self.read_days:
            parts.append(r"\ribbon{R}{\pg{rd:" + day_key + "}}")
        return r"\enspace ".join(parts)

    def day_hours(self, day_key: str) -> list[str]:
        hs = {h for (k, h) in self.db._inst if k == day_key}
        hs |= {r["hour"] for r in self.db.c.execute("SELECT DISTINCT hour FROM hour_instance WHERE day_key=?", (day_key,))}
        return sorted(hs, key=lambda h: HOURS.index(h) if h in HOURS else 99)

    def render_day(self, day_key: str, head: str) -> list[str]:
        d = self.days[day_key]
        out = [head]
        for hour in self.day_hours(day_key):
            loc = location(d, hour, "")
            if loc.startswith("ord:compline:"):
                insts = self.db.instances(day_key, hour)
                form = loc.split(":")[2]
                out.append(r"\hourhead{" + hh_label(day_key, hour) + hour_title(hour)
                           + r"}{\ribbon{O}{\pg{ord:compline:" + form + "}}}")
                out.append(r"{\footnotesize\rubric{As in the Ordinary:} " + FORM_NAME.get(form, form)
                           + r", \pgref{ord:compline:" + form + r"}.\par}")
                continue
            out += self.render_hour(day_key, hour, loc)
        return out

    # ================================================================== 3. ORDINARY
    def ordinary(self) -> str:
        db, s = self.db, self.supp
        out = [r"\chapter{The Ordinary}", r"\objlabel{sec:ordinary}", finding_the_office(),
               opening_block(s)]
        fixed = [self.objs[oid] for oid in self.homed.get("ord:fixed", [])]
        if fixed:
            out.append(r"\par\vspace{4pt}\rubr{As printed (abbreviated) in the Propers, and the prayer before the "
                       r"Office said alone:}\par")
            out += [r"\variant{}{}{" + self.full(o) + "}" for o in sorted(fixed, key=lambda o: -o.n_occ)]

        def ordhour(title, anchor, refs):
            r = r" \enspace·\enspace ".join(f"{name} \\pg{{{lab}}}" for name, lab in refs)
            return [f"\\objlabel{{{anchor}}}", f"\\hourhead{{\\large {title}}}{{{r}}}",
                    f"\\addcontentsline{{toc}}{{section}}{{{title}}}\\markright{{{title}}}"]

        # --- invitatory psalms (B-8)
        inv = self.chapter_instances("INVITATORY")
        main_ps = [o for o in content(db.occ(inv[0]["id"])) if self.objs[o["object_id"]].type == "psalm"] if inv else []
        self.inv_label = label(main_ps[0]["object_id"]) if main_ps else "ord:invitatory"
        out += ordhour("Invitatory", "ord:invitatory", [("Ps 95", self.inv_label)]) + [
            r"\rubr{Said before the first hour of the day (Office of Readings or Lauds).}\par",
            sup_pairs(s["invitatory_opening"]),
            r"\par\rubr{The antiphon of the day (Propers) is said, then repeated after each strophe of the psalm: "
            r"Psalm 95, or in its place Psalm 100, 67 or 24.}"]
        out.append(self.ordinary_psalms(inv, "INVITATORY"))
        # --- Office of Readings, Te Deum
        steps = ORD_STEPS
        out += ordhour("Office of Readings", "ord:or", [("Te Deum", "ord:tedeum"), ("Dismissal", "ord:dismissal:or")])
        out.append(enum(steps["OR"]))
        tedeums = sorted((o for o in self.objs.values() if o.type == "te_deum"), key=lambda o: -o.n_occ)
        if tedeums:
            out += [r"\subsection{Te Deum}", r"\objlabel{ord:tedeum}"]
            out += [f"\\objlabel{{{label(o.id)}}}" for o in tedeums]
            out.append(L.te_deum(tedeums[0].payload))
            self.printed.add(tedeums[0].id)
            for o in tedeums[1:]:
                self.aliases[o.id] = tedeums[0].id
        # --- Lauds, Vespers: Gospel canticles
        gospels = collections.defaultdict(list)
        for o in self.objs.values():
            if o.type == "canticle" and o.payload.get("gospel"):
                gospels[cant_key(o.payload["ref"])].append(o)
        def gospel_canticle(name, key):
            vs = sorted(gospels.get(key, []), key=lambda o: -o.n_occ)
            if not vs:
                return [r"\objlabel{ord:" + name.lower() + "}"]
            self.printed.add(vs[0].id)
            for o in vs[1:]:
                self.aliases[o.id] = vs[0].id
            return ([f"\\subsection{{{name}}}", f"\\objlabel{{ord:{name.lower()}}}"]
                    + [f"\\objlabel{{{label(o.id)}}}" for o in vs]
                    + [r"{\centering\footnotesize " + esc(vs[0].payload["ref"]) + r"\par}",
                       L.canticle_lines(vs[0].payload["lines"]), r"\gloria"])
        out += ordhour("Lauds", "ord:lauds", [("Benedictus", "ord:benedictus"), ("Pater", "ord:pater"),
                                              ("Dismissal", "ord:dismissal:lauds")])
        out.append(enum(steps["LAUDS"]))
        out += gospel_canticle("Benedictus", cant_key("Lc 1, 68-79"))
        out += ordhour("Daytime Prayer", "ord:midday", [("Complementary psalmody", "ord:complementary"),
                                                         ("Dismissal", "ord:dismissal:midday")])
        out.append(enum(steps["MIDDAY"]))
        for chap, title in (("MIDDAY_HYMNS", "Hymns at Terce, Sext and None"),
                            ("MIDDAY_HYMNS_ALT", "Other hymns at Terce, Sext and None"),
                            ("AD_TERTIAM_SEXTAM_ET_NONAM", "Hymns at Terce, Sext and None in Lent and Eastertide")):
            out += self.ordinary_chapter(chap, title)
        out += [r"\subsection{Complementary psalmody}", r"\objlabel{ord:complementary}",
                r"\rubr{At Terce, Sext and None, whoever prays more than one of these hours takes the psalmody of the "
                r"day at one of them and the complementary psalmody at the others (GILH 81–83).}"]
        out += self.ordinary_chapter("COMPLEMENTARY", "", sub=True)
        out += self.ordinary_chapter("COMPLEMENTARY_NO_ANT", "Complementary psalmody without antiphons", sub=True)
        out += ordhour("Vespers", "ord:vespers", [("Magnificat", "ord:magnificat"), ("Pater", "ord:pater"),
                                                  ("Dismissal", "ord:dismissal:vespers")])
        out.append(enum(steps["VESPERS"]))
        out += gospel_canticle("Magnificat", cant_key("Lc 1, 46-55"))
        # --- Pater noster, conclusions, dismissals
        out += [r"\section{Pater noster}", r"\objlabel{ord:pater}", tex(s["pater_noster"]),
                r"\par\vspace{4pt}\rubr{Prayer endings abbreviated in the Propers:}\par\begin{itemize}[leftmargin=1em,itemsep=0pt]"]
        out += [r"\item \rubric{" + esc(k) + "} " + tex(v) for k, v in s["conclusions"].items()]
        out.append(r"\end{itemize}")
        out += [r"\section{Dismissal}", r"\objlabel{ord:dismissal}"]
        for hr in ("OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE"):
            out.append(r"\objlabel{ord:dismissal:" + hr.lower() + "}")
            out += self.ordinary_chapter("DISMISSAL", HOUR_TITLE[hr], hours=[hr])
        out += self.ordinary_chapter("DISMISSAL_EASTER", "In the Easter Octave")
        # --- Marian antiphons
        out += [r"\section{Antiphons of the Blessed Virgin Mary}", r"\objlabel{ord:marian}"]
        out += self.ordinary_chapter("MARIAN", "", sub=True)
        # --- Compline: the weekly cycle and the Easter Octave
        out += ordhour("Compline", "ord:compline", [("Nunc dimittis", "ord:nunc dimittis"), ("B.V.M.", "ord:marian")])
        out.append(enum(steps["COMPLINE"]))
        out += gospel_canticle("Nunc dimittis", cant_key("Lc 2, 29-32"))
        for form in ("SAT1", "SUN", "MON", "TUE", "WED", "THU", "FRI"):
            out += self.compline_form(form)
        out += [r"\subsection{Compline in the Easter Octave}", r"\objlabel{ord:compline:EASTER}"]
        out += self.ordinary_chapter("compline:EASTER", "", sub=True, whole=True)
        out += self.flush(["ord:compline:EASTER"])
        out += [r"\subsection{Compline in the Christmas Octave}", r"\objlabel{ord:compline:CHRISTMAS}",
                r"\rubr{From 26 to 31 December Compline is that of Sunday, after First or Second Vespers "
                r"(\pgref{ord:compline:SAT1}, \pgref{ord:compline:SUN}), as each day's office indicates. On "
                r"solemnities: after First Vespers the Compline of Saturday, after Second Vespers that of Sunday.}"]
        out += self.ordinary_chapter("COMPLETORIUM", "Compline after First Vespers (Advent and Christmas volume)")
        out += self.ordinary_chapter("COMPLINE_HYMNS", "Hymns at Compline")
        out += [r"\section{Psalms of Sunday, Week I}", r"\objlabel{ord:sundaywk1}",
                r"\rubr{Used at Lauds of solemnities and feasts.}"]
        out += self.ordinary_chapter("SUNDAY_WK1_PSALMS", "", sub=True)
        rest = self.flush_prefix("ord:", "Other texts of the Ordinary")
        out.append(rest)
        return "\n".join(x for x in out if x)

    def chapter_instances(self, chap: str) -> list:
        keys = [k for k in self.days if ord_chapter(k) == chap]
        rows = []
        for k in keys:
            rows += self.db.c.execute("SELECT * FROM hour_instance WHERE day_key=? ORDER BY id", (k,)).fetchall()
        src = {"PA": 0, "LQP": 1, "ADV": 2, "COM": 3, "SPA": 4, "SP": 5, "SQ": 6, "SADV": 7}
        return sorted(rows, key=lambda h: (src.get(h["source"], 9), h["id"]))

    def ordinary_psalms(self, insts, chap) -> str:
        """Invitatory psalms with their refrain marks, printed once (later volumes' printings = aliases)."""
        out, by_num = [], collections.defaultdict(list)
        for h in insts:
            for o in content(self.db.occ(h["id"])):
                ob = self.objs[o["object_id"]]
                if ob.type == "psalm" and ob.home == "ordinary":
                    if ob.id not in by_num[ob.payload["psalm"]]:
                        by_num[ob.payload["psalm"]].append(ob.id)
        for num, ids in by_num.items():
            main = self.objs[ids[0]]
            self.printed.add(main.id)
            for a in ids[1:]:
                self.aliases[a] = main.id
            p = main.payload
            out.append(f"\\psalmhead[6]{{Psalm {esc(p['psalm'])} ({esc(p['vulg'])})}}{{{tex(p.get('title', ''), marks=False)}}}")
            out += [f"\\objlabel{{{label(i)}}}" for i in ids]
            out.append(L.canticle_lines(p["lines"]))
        return "\n".join(out)

    def ordinary_chapter(self, chap: str, title: str, sub: bool = False, hours=None, whole: bool = False) -> list[str]:
        """An Ordinary appendix chapter: rubrics and texts of the first printing, plus texts that only other
        volumes' printings have."""
        insts = [h for h in self.chapter_instances(chap) if hours is None or h["hour"] in hours]
        if not insts:
            return []
        out = [r"\subsection{" + title + "}"] if title and not sub else ([r"\sublabel{" + title + "}"] if title else [])
        seen: set[str] = set()
        cur_sub = None
        for n, h in enumerate(insts):
            d = self.days[h["day_key"]]
            for o in self.db.occ(h["id"]):
                if o["type"] in ("label", "marker"):
                    continue
                if o["type"] in ("rubric", "link"):
                    if n == 0 and o["object_id"]:
                        txt = self.objs[o["object_id"]].payload.get("text", "")
                        if txt and not re.match(r"^_+$|^(Vel|Alia):?$", plain(txt)):
                            out.append(r"\par{\lrubr{" + tex(txt, marks=False) + r"}}\par")
                    continue
                oid = o["object_id"]
                if not oid or oid in seen or (o["slot"] or "").endswith("_R"):
                    continue
                seen.add(oid)
                ob = self.objs[oid]
                if ob.type == "psalm" and ob.home == "ordinary":
                    continue                            # invitatory psalms: printed above
                if (o["sub"] or "") != (cur_sub or "") and o["sub"]:
                    cur_sub = o["sub"]
                    out.append(r"\sublabel{" + esc(SUB_TITLE.get(cur_sub, cur_sub)) + "}")
                loc = location(d, h["hour"], o["slot"] or "")
                c = cond_text(o["cond"])
                name = self.slot_title(o["slot"] or "", "", h["hour"]) if o["slot"] not in ("TEXT", "VR", "") else ""
                if ob.type == "ant":
                    name = "Ant."
                body = (r"\condlabel{" + esc(c) + "}" if c else "") + self.emit(
                    oid, loc, h["id"], whole and (o["slot"] or "") != "MARIAN")
                if n > 0 and ob.home_label == loc:
                    name = (name + " · " if name else "") + SOURCE_SEASON.get(h["source"], h["source"])
                out.append(r"\variant{" + esc(name) + "}{" + L.citation(ob.type, ob.payload) + "}{" + body + "}")
        return out

    def compline_form(self, form: str) -> list[str]:
        db = self.db
        hour = "COMPLINE1" if form == "SAT1" else "COMPLINE"
        wd = "SUN" if form == "SAT1" else form
        days = []
        for pw in (1, 2, 3, 4):
            days += [d for d in db.days(pw, wd) if is_grid(d)]
        days.sort(key=lambda d: (SEASON_ORDER[d["season"]], d["week"]))
        loc = f"ord:compline:{form}"
        out = [r"\subsection{" + FORM_NAME[form] + "}", r"\objlabel{" + loc + "}"]
        ot = [d for d in days if d["season"] == "OT"]
        if ot:
            h = db.hour(ot[0]["key"], hour)
            if h:
                self.compline_units[form] = tuple(o["object_id"] for o in content(db.occ(h["id"]))
                                                  if re.fullmatch(r"PS\d", o["slot"] or ""))
        # every text printed here in full (B-15): the psalms, hymns, shared responsory, antiphons, Nunc dimittis
        order = list(SLOT_ORDER["COMPLINE"])
        order.insert(order.index("GOSPEL_ANT") + 1, "GOSPEL_CANT")
        for slot in order:
            groups = slot_groups(db, days, hour, slot, "")
            groups = [g for g in groups]
            if not groups:
                continue
            for g in groups:
                g.label = self.season_label(g.days)
            name = self.slot_title(slot, "", hour)
            lines = []
            if slot == "GOSPEL_CANT":
                groups = groups[:1]                     # the Nunc dimittis once, whatever the season
                name = "Nunc dimittis"
            for g in groups:
                lines.append(r"\variant{" + (esc(g.label) if len(groups) > 1 else "") + "}{}{"
                             + self.item_lines(g.items, loc, None, whole=slot != "MARIAN") + "}")
            out.append(r"\slotname{" + name + "}{}" + "\n".join(lines))
        out.append(r"\par{\footnotesize\rubric{Antiphon of the Blessed Virgin Mary:} card 2, or \pgref{ord:marian}"
                   r"\rubric{; in Eastertide Regína cæli.}}\par")
        out += self.flush([loc])
        return out

    @staticmethod
    def season_label(days) -> str:
        seasons = sorted({d["season"] for d in days}, key=lambda s: SEASON_ORDER[s])
        names = {"OT": "Per annum", "ADV": "Advent", "LENT": "Lent", "EAS": "Eastertide"}
        return " · ".join(names[s] for s in seasons)

    # ================================================================== 4. PROPER OF TIME
    def proper_of_time(self) -> str:
        out = [r"\chapter{Proper of Time}", r"\objlabel{sec:propers}", r"\budget{time/grid}",
               r"\rubr{The four-week cycle, day by day and hour by hour. Under each part, the texts for every season "
               r"that uses this psalter week are given side by side: \rubric{\scshape Per annum} (all weeks of "
               r"Ordinary Time on this psalter week), \rubric{\scshape Adv.}, \rubric{\scshape Lent}, "
               r"\rubric{\scshape Easter} with the week of the season. Where a season has its own text it is listed; "
               r"otherwise the Per annum text serves. Each text is printed once; later uses give its page. Fixed parts "
               r"are in the Ordinary; Compline is in the Ordinary. The days with wholly proper offices (17–24 December, "
               r"Christmas Time, Ash Wednesday, Holy Week, the Triduum, the Easter Octave, Ascension, Pentecost and the "
               r"solemnities of the Lord) follow the four-week cycle.}"]
        for pw in (1, 2, 3, 4):
            for wd in WD:
                out.append(self.grid_day(pw, wd))
        out += [r"\budget{time/otweeks}", r"\section{Ordinary Time: proper to each week}", r"\objlabel{time:otweeks}",
                r"\rubr{The Gospel canticle antiphons of Sunday follow the Sunday Gospel of Years A, B and C; the collect "
                r"of the Sunday is said at all the hours of Sunday (except Compline) and at the Office of Readings of the "
                r"weekdays of that week.}"]
        for wk in range(1, 35):
            out += self.ot_week(wk)
        out.append(r"\budget{time/proper}")
        done = set()
        for title, pred in TIME_PARTS:
            keys = [k for k in PROPER_DAYS if pred(k) and k in self.days and k not in done]
            if not keys:
                continue
            out += [r"\section{" + title + "}"]
            for k in keys:
                done.add(k)
                out += self.render_day(k, self.day_head(k))
        rest = [k for k in self.days if day_section(k) == "time" and not is_grid(self.days[k]) and k not in done]
        if rest:
            out.append(r"\section{Other days}")
            for k in sorted(rest, key=lambda k: self.order.time.get(k, 9999)):
                out += self.render_day(k, self.day_head(k))
        out.append(self.flush_prefix("time:", "Other texts of the Proper of Time"))
        return "\n".join(x for x in out if x)

    def day_head(self, k: str, sub: str = "", rank: str = "") -> str:
        d = self.days[k]
        title = esc(d["title"] or k)
        return (r"\dayhead{" + title + "}{" + sub + "}{" + rank + "}{" + "day:" + k + "}")

    def grid_day(self, pw: int, wd: str) -> str:
        db = self.db
        days = [d for d in db.days(pw, wd) if is_grid(d)]
        title = f"Week {ROMAN[pw]} — {DAY_NAMES[wd]}"
        ot_weeks = sorted(d["week"] for d in days if d["season"] == "OT")
        others = ", ".join(f"{SEASON_LABEL[d['season']]} {d['week']}" for d in days if d["season"] != "OT")
        out = [f"\\section{{{title}}}", f"\\objlabel{{grid:{pw}.{wd}}}",
               r"{\footnotesize\rubric{Used on:} Ordinary Time weeks " + ", ".join(map(str, ot_weeks))
               + ("; " + esc(others) if others else "") + r".\par}"]
        hours = sorted({h["hour"] for d in days for h in db.c.execute(
            "SELECT DISTINCT hour FROM hour_instance WHERE day_key=?", (d["key"],))} - {"COMPLINE", "COMPLINE1"},
                       key=HOURS.index)
        for hour in hours:
            ht = r"First Vespers \rubric{\footnotesize (Saturday evening)}" if hour == "V1" else HOUR_TITLE[hour]
            out.append(r"\hourhead{" + hh_label(f"grid:{pw}.{wd}", hour) + ht + "}{"
                       + ribbon_refs(db, days, hour, self.inv_label, self.anchor) + "}")
            gloc = f"time:grid:{pw}.{wd}:{hour}"
            slots = list(SLOT_ORDER.get("VESPERS" if hour in ("V1", "V2") else hour, []))
            extra = []
            for d in days:
                for h in db.instances(d["key"], hour):
                    for o in content(db.occ(h["id"])):
                        k = (o["slot"], o["sub"] or "")
                        if o["slot"] in SKIP_SLOTS or o["slot"].endswith("_R"):
                            continue
                        if (k[0] if not k[1] else k) not in slots and k not in slots and k not in extra:
                            extra.append(k)
            cur_sub = None
            for s in slots + extra:
                slot, sub = (s if isinstance(s, tuple) else (s, ""))
                if slot in ("LECT1", "LECT2", "RESP1", "RESP2"):
                    if slot == "LECT1":
                        out.append(self.readings_line(days))
                    continue
                groups = slot_groups(db, days, hour, slot, sub)
                if not groups:
                    continue
                if sub and sub != cur_sub and slot == "LB":
                    out.append(r"\sublabel{" + SUB_TITLE[sub] + "}")
                    cur_sub = sub
                name = self.slot_title(slot, sub, hour)
                kept, weekly = [], []
                for g in groups:
                    d0 = g.days[0]
                    loc = location(d0, hour, slot)
                    if loc.startswith("time:otweek") and all(d["season"] == "OT" for d in g.days):
                        weekly.append(g)
                        continue
                    kept.append((g, loc))
                lines = []
                cites = {L.citation(self.objs[oid].type, self.objs[oid].payload) for g, _ in kept for _, oid in g.items}
                cites.discard("")
                shared = next(iter(cites)) if len(cites) == 1 else ""
                for g, loc in kept:
                    first = self.objs[g.items[0][1]]
                    cite = "" if shared or not cites else L.citation(first.type, first.payload)
                    lead = r"\par " if any(c for c, _ in g.items) else ""
                    hid = self.grid_hour_id(g.days[0], hour)
                    lines.append(r"\variant{" + esc(g.label) + "}{" + cite + "}{" + lead
                                 + self.item_lines(g.items, loc, hid) + "}")
                if weekly:
                    lines.append(r"\variant{Per annum}{}{\rubr{Proper to each week of Ordinary Time,} \pgref{time:otweeks}.}")
                out.append(r"\slotname{" + name + "}{" + shared + "}" + "\n".join(lines))
            # ad libitum hymns reached by a link (Salve dies, Dies ætásque: Sunday First Vespers, T-PA-2)
            alt = []
            for d in days:
                for h in db.instances(d["key"], hour):
                    for o in db.occ(h["id"]):
                        if o["slot"] == "HYMN_ALT" and self.link_obj.get(o["id"]):
                            t = self.link_obj[o["id"]]
                            if self.objs[t].type == "hymn" and t not in alt:
                                alt.append(t)
            if alt:
                out.append(r"\variant{}{}{\condlabel{Ad libitum:}" + "; ".join(self.ref(self.objs[t]) for t in alt) + "}")
            if hour in ("LAUDS", "VESPERS", "V1", "V2"):
                out.append(card_line(GOSPEL[hour]))
            if hour == "OR" and wd == "SUN":
                out.append(r"\par{\footnotesize\rubric{Te Deum} (except in Lent): \cardref{2}, \pgref{ord:tedeum}.}\par")
            out += self.flush([gloc])
        form = "SUN" if wd == "SUN" else wd
        if wd != "SAT":
            out.append(r"\hourhead{" + hh_label(f"grid:{pw}.{wd}", "COMPLINE") + r"Compline}{\ribbon{O}{\pg{ord:compline:"
                       + form + "}}}")
        if wd == "SUN":
            out.append(r"{\footnotesize After First Vespers: \pgref{ord:compline:SAT1}; after Second Vespers: "
                       r"\pgref{ord:compline:SUN}.\par}")
        return "\n".join(out)

    def grid_hour_id(self, d, hour):
        h = self.db.hour(d["key"], hour)
        return h["id"] if h else None

    def readings_line(self, days) -> str:
        refs = []
        for d in sorted(days, key=lambda d: (SEASON_ORDER[d["season"]], d["week"])):
            if d["key"] in self.read_days:
                refs.append(f"{SEASON_LABEL[d['season']]} {d['week']} " + r"\pg{rd:" + d["key"] + "}")
        if not refs:
            return ""
        return (r"\slotname{Readings}{}\variant{}{}{\footnotesize\rubric{Office of Readings (ribbon 10):} "
                + " · ".join(refs) + "}")

    def ot_week(self, wk: int) -> list[str]:
        loc = f"time:otweek:{wk:02d}"
        sun = f"OT.{wk:02d}.SUN"
        if not self.homed.get(loc) and sun not in self.days:
            return []
        out = [r"\sublabel{" + f"Week {wk} of Ordinary Time" + "}", r"\objlabel{otweek:" + str(wk) + "}"]
        if sun in self.days:
            for hour in ("V1", "LAUDS", "V2"):
                h = self.db.hour(sun, hour)
                if not h:
                    continue
                items = [(cond_text(o["cond"]), o["object_id"]) for o in content(self.db.occ(h["id"]))
                         if o["slot"] == "GOSPEL_ANT"]
                if items:
                    hn = {"V1": "I Vespers", "LAUDS": "Lauds", "V2": "II Vespers"}[hour]
                    out.append(r"\variant{" + hn + r"}{}{\par " + self.item_lines(items, loc, h["id"]) + "}")
            h = self.db.hour(sun, "LAUDS")
            if h:
                col = [o["object_id"] for o in content(self.db.occ(h["id"])) if o["slot"] == "ORATIO"]
                if col:
                    out.append(r"\variant{Collect}{}{" + self.emit(col[0], loc, h["id"]) + "}")
        # the weekdays' Office of Readings prayer when it is printed differently from the Sunday collect (or the
        # week has no Sunday: week 1, Baptism of the Lord)
        for oid in self.homed.get(loc, []):
            if oid not in self.printed:
                out.append(r"\variant{Collect (weekdays, Office of Readings)}{}{" + self.full(self.objs[oid]) + "}")
        return out

    # ================================================================== 2. COMMONS
    def commons(self) -> str:
        out = [r"\chapter{Commons}", r"\objlabel{sec:commons}", r"\budget{commons/commons}",
               r"\rubr{Each Common with its seasonal forms: the Per annum text first, then the texts proper to Advent "
               r"and Christmas, Lent and Eastertide where they differ. Sub-variants (for a pope, a bishop, several "
               r"pastors …) are marked in italics.}"]
        for k in COMMON_ORDER[:10]:
            if k not in self.days:
                continue
            out += [r"\section{" + esc(self.days[k]["title"]) + "}", r"\objlabel{day:" + k + "}"]
            for hour in self.day_hours(k):
                out.append(r"\objlabel{hr:" + k + ":" + hour + "}")
                out += self.render_hour(k, hour, location(self.days[k], hour, ""))
        out += [r"\budget{commons/additional}", r"\section{Additional and votive offices}"]
        for k, title in (("DEAD", "Office for the Dead"), ("MEM.BVM_SATURDAY", "Saturday memorial of the Blessed Virgin Mary")):
            if k not in self.days:
                continue
            out.append(self.day_head(k).replace("{" + esc(self.days[k]["title"] or k) + "}", "{" + title + "}", 1))
            for hour in self.day_hours(k):
                out.append(r"\objlabel{hr:" + k + ":" + hour + "}")
                out += self.render_hour(k, hour, location(self.days[k], hour, ""))
        out.append(self.flush_prefix("com:", "Other texts of the Commons"))
        return "\n".join(x for x in out if x)

    # ================================================================== 1. PROPER OF SAINTS
    def saints(self) -> str:
        out = [r"\chapter{Proper of Saints}", r"\objlabel{sec:saints}",
               r"\rubr{By date. Only what is proper to the celebration is printed; the rest is taken from the Common "
               r"named (\rubric{de Communi}, ribbon 2), from the psalter of the current weekday (\rubric{de feria}), "
               r"or from the page given. On memorials the psalms and antiphons and the first reading are of the "
               r"current weekday unless proper ones are given (GILH 234–236).}"]
        month = None
        tp_saints = {"12-26": "CHR.DEC26", "12-27": "CHR.DEC27", "12-28": "CHR.DEC28"}
        keys = list(self.order.saints)
        for mmdd, k in tp_saints.items():
            if k in self.days:
                keys.append(("TP", mmdd, k))
        def sk(k):
            if isinstance(k, tuple):
                return (k[1], 0, k[2])
            return (saint_date(k), 1 + self.order.saints[k], k)
        for k in sorted(keys, key=sk):
            if isinstance(k, tuple):
                _, mmdd, tk = k
                out.append(r"\par\vspace{4pt}\noindent{\scshape\color{rubric}" + date_en(mmdd) + r"}\enspace "
                           + esc(self.days[tk]["title"]) + r"\enspace{\footnotesize in the Proper of Time,} \pgref{day:"
                           + tk + r"}\par")
                continue
            mmdd = saint_date(k)
            m = int(mmdd[:2]) if mmdd[0].isdigit() and mmdd != "99-99" else None
            if m != month:
                month = m
                out.append(r"\section{" + (MONTHS[m - 1] if m else "Movable celebrations") + "}")
            out += self.saint_day(k)
        out.append(self.flush_prefix("sanct:", "Other texts of the Proper of Saints"))
        return "\n".join(x for x in out if x)

    def saint_day(self, k: str) -> list[str]:
        d = self.days[k]
        x = json.loads(d["extra"] or "{}")
        title = x.get("printed_title") or d["title"] or k
        mmdd = saint_date(k)
        date = date_en(mmdd) if mmdd != "99-99" else ""
        rank = RANK_EN.get(d["rank"], d["rank"] or "")
        sub = esc(d["title"] or "")
        head = (r"\dayhead{" + (esc(date) + r"\enspace·\enspace " if date else "") + esc(nice_case(title)) + "}{"
                + sub + "}{" + esc(rank) + "}{day:" + k + "}")
        out = [head]
        if x.get("rubrics"):
            out.append(r"{\lrubr{" + tex(x["rubrics"], marks=False) + r"}\par}")
        if x.get("bio"):
            out.append(r"{\footnotesize " + tex(x["bio"], marks=False) + r"\par}")
        for hour in self.day_hours(k):
            out += self.render_hour(k, hour, location(d, hour, ""))
        return out

    # ================================================================== 5. HYMNS
    def hymn_group(self, o: Obj) -> tuple:
        loc = (o.home_label or "hymns:")[6:]
        p = loc.split(":")
        hour = p[-1] if p and p[-1] in HOURS else ""
        hn = {"OR": "Office of Readings", "LAUDS": "Lauds", "MIDDAY": "Daytime Prayer", "VESPERS": "Vespers",
              "V1": "Vespers", "V2": "Vespers", "INV": "Invitatory", "COMPLINE": "Compline", "COMPLINE1": "Compline"}
        if p[0] == "ord":
            if p[1] == "compline" or "COMPL" in p[1]:
                return (6, "Compline")
            return (5, "Daytime Prayer")
        if p[0] == "hymns":
            return (7, "Hymns ad libitum")
        if p[0] == "time":
            if p[1] in ("grid", "otweek"):
                day = self.first_day(o.id)
                season = self.days[day]["season"] if day else "OT"
                if season == "OT":
                    return (0, "Ordinary Time: " + hn.get(hour, "other hours"), HOURS.index(hour) if hour in HOURS else 9)
                return {"ADV": (1, "Advent"), "LENT": (3, "Lent"), "EAS": (4, "Eastertide")}[season]
            k = p[2]
            if k.startswith(("ADV.", "CHR.", "FEAST.")) or k in ("SOL.CHRISTMAS", "SOL.EPIPHANY", "SOL.MARY_MOTHER_OF_GOD"):
                return (2, "Advent and Christmas Time" if k.startswith("ADV.") else "Christmas Time")
            if k.startswith(("LENT.", "HOLY.", "TRIDUUM.")):
                return (3, "Lent")
            if k.startswith("EAS.") or k in ("SOL.ASCENSION", "SOL.PENTECOST"):
                return (4, "Eastertide")
            return (4.5, "Solemnities of the Lord")
        if p[0] == "com":
            if p[1] == "DEAD":
                return (9, "Office for the Dead")
            return (8, "Commons")
        if p[0] == "sanct":
            return (10, "Proper of Saints")
        return (11, "Other hymns")

    def first_day(self, oid: str) -> str | None:
        best = None
        for r in self.db.c.execute("""SELECT h.day_key, h.hour, o.slot FROM occurrence o JOIN hour_instance h ON h.id=o.hour_id
                                      WHERE o.object_id=?""", (oid,)):
            d = self.days[r["day_key"]]
            rk = self.order.loc_rank(location(d, r["hour"], r["slot"] or ""))
            if best is None or rk < best[0]:
                best = (rk, r["day_key"])
        return best[1] if best else None

    def hymns(self) -> str:
        out = [r"\chapter{Hymns}", r"\objlabel{sec:hymns}",
               r"\rubr{Each hymn is printed once, grouped by the season and hour where it is first used; the Propers, "
               r"the Commons and the Proper of Saints refer to it by page. An index of first lines is at the end of "
               r"the book. \emph{Salve dies} and \emph{Dies ætásque} (among the hymns ad libitum) may be sung at First "
               r"Vespers of Sundays in weeks II–XXXIII; \emph{Dies iræ} in week XXXIV.}"]
        hyms = [o for o in self.objs.values() if o.type == "hymn" and o.home == "hymns"]
        groups = collections.defaultdict(list)
        for o in hyms:
            g = self.hymn_group(o)
            groups[(g[0], g[2] if len(g) > 2 else 0, g[1])].append(o)
        self.hymn_index = []
        for gk in sorted(groups):
            out.append(r"\section{" + esc(gk[2]) + "}")
            for o in sorted(groups[gk], key=lambda o: self.order.loc_rank(o.home_label[6:]) if o.home_label else ()):
                first = tex(o.payload["stanzas"][0][0], marks=False)
                out.append(r"\needspace{6\baselineskip}\par\vspace{0.5\baselineskip}{\scshape\color{rubric}"
                           + first.rstrip(",.;:") + r"}\par" + f"\\objlabel{{{label(o.id)}}}")
                out.append(L.hymn(o.payload))
                self.printed.add(o.id)
                self.hymn_index.append((plain(o.payload["stanzas"][0][0]), o.id))
        return "\n".join(out)

    # ================================================================== 6-9. PSALTER
    def psalter(self) -> str:
        out = [r"\chapter{The Psalter}", r"\objlabel{sec:psalter}", r"\budget{psalter/psalms}", self.PSALTER_INTRO,
               r"\par\vspace{\baselineskip}"]
        for num in range(1, 151):
            out.append(self.psalm(num))
        for o in self.objs.values():
            if o.type == "psalm" and o.home == "psalter":
                self.printed.add(o.id)
        out += [r"\budget{psalter/canticles}", r"\chapter{Canticles}", r"\objlabel{sec:canticles}",
                r"\rubr{Old and New Testament canticles of Lauds and Vespers, and the canticles of the vigils. The Gospel "
                r"canticles (Benedictus, Magnificat, Nunc dimittis) are in the Ordinary. Printings of the same canticle "
                r"that differ only in punctuation or line breaks (TODO.md T-DUP) are given once.}"]
        groups = collections.defaultdict(list)
        for o in self.objs.values():
            if o.type == "canticle" and o.home == "psalter":
                groups[cant_key(o.payload["ref"])].append(o)
        self.cant_index = []
        for key in sorted(groups, key=lambda k: canticle_sort(groups[k][0].payload["ref"])):
            vs = sorted(groups[key], key=lambda o: -o.n_occ)
            # distinct line counts → genuinely different texts: print each
            main = vs[0]
            for o in vs[1:]:
                if abs(len(o.payload["lines"]) - len(main.payload["lines"])) > 2:
                    out.append(self.canticle(o))
                    self.printed.add(o.id)
                    self.cant_index.append((o.payload["ref"], o.id))
                else:
                    self.aliases[o.id] = main.id
            out.append(self.canticle(main, [o.id for o in vs[1:] if self.aliases.get(o.id) == main.id]))
            self.printed.add(main.id)
            self.cant_index.append((main.payload["ref"], main.id))
        return "\n".join(out)

    # ================================================================== 10. READINGS
    def reading_days(self) -> list[str]:
        keys = [k for k in sorted(self.order.time, key=self.order.time.get)]
        keys += [k for k in COMMON_ORDER if k in self.days]
        keys += list(self.order.saints)
        return keys

    def collect_read_days(self):
        for k in self.reading_days():
            for hour in ("OR", "APPX"):
                for h in self.db.instances(k, hour):
                    if any(self.objs[o["object_id"]].type in ("reading", "responsory")
                           for o in content(self.db.occ(h["id"]))):
                        self.read_days.add(k)

    def readings(self) -> str:
        out = [r"\chapter{Readings of the Office of Readings}", r"\objlabel{sec:readings}",
               r"\rubr{The readings and responsories of the Office of Readings, in the order of the liturgical year, then "
               r"the Commons, the Office for the Dead and the Proper of Saints. Each is printed once; a reading used on "
               r"several days is given at its first day and referred to afterwards.}"]
        part = None
        for k in self.reading_days():
            if k not in self.read_days:
                continue
            p = reading_part(k)
            if p != part:
                part = p
                out.append(r"\section{" + p + "}")
            d = self.days[k]
            title = d["title"] or k
            if k.startswith("SANCT.") or k == "SOL.IMMACULATE_CONCEPTION":
                title = f"{date_en(saint_date(k))} · {title}"
            out.append(r"\readhead{" + esc(title) + "}{rd:" + k + "}")
            loc = f"read:{k}"
            seen = set()
            for hour in ("OR", "APPX"):
                for h in self.db.instances(k, hour):
                    for o in self.db.occ(h["id"]):
                        oid = o["object_id"]
                        if o["type"] == "link" and o["slot"] == "LECT2" and self.link_obj.get(o["id"]):
                            t = self.link_obj[o["id"]]
                            if t not in seen and self.objs[t].type == "reading" and not (
                                    self.objs[t].home_label == loc and t not in self.printed):
                                seen.add(t)
                                out.append(r"\slotname{Second reading}{}\variant{}{}{" + self.ref(self.objs[t]) + "}")
                            continue
                        if not oid or oid in seen or self.objs[oid].type not in ("reading", "responsory"):
                            continue
                        seen.add(oid)
                        ob = self.objs[oid]
                        c = cond_text(o["cond"])
                        lab_ = ""
                        cl = (r"\condlabel{" + esc(c) + "}" if c else "") + (r"\condlabel{" + esc(lab_) + ":}" if lab_ else "")
                        if ob.home_label == loc and oid not in self.printed:
                            self.printed.add(oid)
                            self.stats["printed"] += 1
                            if ob.type == "reading":
                                title_ = {"LECT1": "First reading", "LECT2": "Second reading", "GOSPEL": "Gospel",
                                          "LECT3": "Third reading", "LECT4": "Fourth reading"}.get(o["slot"], "Reading")
                                out.append(r"\slotname{" + title_ + "}{" + L.citation(ob.type, ob.payload) + "}"
                                           + f"\\objlabel{{{label(oid)}}}" + (r"\par " + cl if cl else ""))
                                out.append(L.reading(dict(ob.payload, intro=[])))
                            else:
                                out.append(r"\slotname{Responsory}{" + L.citation(ob.type, ob.payload) + "}"
                                           + f"\\objlabel{{{label(oid)}}}" + (r"\par " + cl if cl else ""))
                                out.append(L.pairs(ob.payload))
                        else:
                            nm = "Responsory" if ob.type == "responsory" else "Reading"
                            out.append(r"\slotname{" + nm + r"}{}\variant{}{}{" + cl + self.ref(ob) + "}")
        out.append(self.flush_prefix("read:", "Other readings"))
        return "\n".join(x for x in out if x)

    # ================================================================== INDEXES
    def indexes(self) -> str:
        out = [r"\chapter{Indexes}", r"\objlabel{sec:indexes}",
               r"\section{Psalms}", r"\begin{multicols}{3}\footnotesize\raggedright"]
        rows = self.db.c.execute("SELECT num, vulgate FROM psalm ORDER BY num").fetchall()
        vul = {r["num"]: r["vulgate"] for r in rows}
        for n in range(1, 151):
            v = vul.get(n) or str(n)
            out.append(f"Ps {n}" + (f" ({esc(v)})" if v != str(n) else "") + r"\dotfill\pg{" + label(f"ps:{n}") + r"}\par")
        out += [r"\end{multicols}", r"\section{Canticles}", r"\begin{multicols}{2}\footnotesize\raggedright"]
        for ref, oid in sorted(self.cant_index, key=lambda x: canticle_sort(x[0])):
            out.append(esc(ref) + r"\dotfill\pg{" + label(oid) + r"}\par")
        for nm in ("Benedictus", "Magnificat", "Nunc dimittis"):
            out.append(nm + r"\dotfill\pg{ord:" + nm.lower() + r"}\par")
        out += [r"\end{multicols}", r"\section{Hymns (first lines)}", r"\begin{multicols}{2}\footnotesize\raggedright"]
        for first, oid in sorted(self.hymn_index, key=lambda x: fold_sort(x[0])):
            out.append(r"\hangindent=1em " + esc(first.rstrip(",.;:")) + r"\dotfill\pg{" + label(oid) + r"}\par")
        out += [r"\end{multicols}", r"\section{Saints by date}", r"\begin{multicols}{2}\footnotesize\raggedright"]
        saints = [(saint_date(k), self.days[k]["title"] or k, k) for k in self.order.saints]
        for mmdd, title, k in sorted(saints):
            out.append(r"\hangindent=1em " + esc(date_en(mmdd)) + " · " + esc(title) + r"\dotfill\pg{day:" + k + r"}\par")
        out += [r"\end{multicols}", r"\section{Saints by name}", r"\begin{multicols}{2}\footnotesize\raggedright"]
        for mmdd, title, k in sorted(saints, key=lambda x: fold_sort(name_key(x[1]))):
            out.append(r"\hangindent=1em " + esc(title) + r"\dotfill\pg{day:" + k + r"}\par")
        out.append(r"\end{multicols}")
        return "\n".join(out)

    # ================================================================== whole book
    def body(self) -> str:
        self.collect_read_days()
        self.inv_label = "ord:invitatory"
        # build in priority order (homes are printed where attribution put them; references are page numbers, so the
        # order of generation does not matter for correctness), then assemble in book order
        parts = {}
        parts["ordinary"] = self.ordinary()
        parts["psalter"] = self.psalter()
        parts["hymns"] = self.hymns()
        parts["time"] = self.proper_of_time()
        parts["commons"] = self.commons()
        parts["saints"] = self.saints()
        parts["readings"] = self.readings()
        missing = [o for o in self.objs.values() if o.home in SECTIONS_PRINTED and o.id not in self.printed
                   and o.id not in self.aliases]
        tail = ""
        if missing:
            tail = "\n".join([r"\chapter{Other texts}", r"\budget{other}"]
                             + [r"\variant{" + esc(o.type) + "}{}{" + self.full(o) + "}" for o in missing])
        self.stats["unprinted_fallback"] = len(missing)
        parts["indexes"] = self.indexes()
        order = ["saints", "commons", "ordinary", "time", "hymns", "psalter", "readings"]
        body = "\n\n".join(r"\cleardoublepage\budget{" + k + "}" + PART_PAGE[k] + "\n" + parts[k] for k in order) \
            + "\n\n" + tail + "\n\n" + r"\cleardoublepage\budget{indexes}" + "\n" + parts["indexes"] + "\n" \
            + r"\budget{end}"
        return body


SECTIONS_PRINTED = {"ordinary", "psalter", "hymns", "time", "commons", "saints", "readings"}
PART_PAGE = {
    "saints": r"\partpage{Proprium de Sanctis}{Proper of Saints · ribbon 1}",
    "commons": r"\partpage{Commune Sanctorum}{Commons, Office for the Dead · ribbon 2}",
    "ordinary": r"\partpage{Ordinarium}{The Ordinary · ribbon 3}",
    "time": r"\partpage{Proprium de Tempore}{Proper of Time · ribbon 4}",
    "hymns": r"\partpage{Hymni}{Hymns · ribbon 5}",
    "psalter": r"\partpage{Psalterium}{Psalter and Canticles · ribbons 6–9}",
    "readings": r"\partpage{Lectiones}{Readings of the Office of Readings · ribbon 10}",
}
FORM_NAME = {"SAT1": "Saturday (after First Vespers of Sunday)", "SUN": "Sunday (after Second Vespers)",
             "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday",
             "EASTER": "Easter Octave", "CHRISTMAS": "Christmas Octave"}
ORD_STEPS = {
    "OR": ["Opening (\\pgref{ord:opening})", "Hymn", "Psalmody (three psalms with antiphons)", "Versicle",
           "First reading and responsory; second reading and responsory (ribbon 10)",
           r"Te Deum on Sundays (outside Lent), solemnities and feasts, \pgref{ord:tedeum}", "Concluding prayer"],
    "LAUDS": ["Opening", "Hymn", "Psalmody: morning psalm, Old Testament canticle, psalm of praise",
              "Short reading and short responsory", "Benedictus with its antiphon (below)",
              "Intercessions", r"Pater noster, \pgref{ord:pater}", "Concluding prayer", r"Dismissal, \pgref{ord:dismissal}"],
    "MIDDAY": ["Opening", "Hymn (Terce, Sext or None)", "Psalmody: of the day, or the complementary "
               "psalmody (Pss 120–128, below) at the other hours", "Short reading and versicle", "Concluding prayer",
               r"\Vs Benedicámus Dómino. \Rs Deo grátias."],
    "VESPERS": ["Opening", "Hymn", "Psalmody: two psalms and a New Testament canticle",
                "Short reading and short responsory", "Magnificat with its antiphon (below)",
                "Intercessions", r"Pater noster, \pgref{ord:pater}", "Concluding prayer", r"Dismissal, \pgref{ord:dismissal}"],
    "COMPLINE": ["Opening", "Examination of conscience (penitential act)", "Hymn", "Psalmody of the day (below)",
                 "Short reading", "Responsory", "Nunc dimittis with antiphon", "Concluding prayer", "Blessing",
                 r"Antiphon of the Blessed Virgin Mary, \pgref{ord:marian}"],
}


def enum(items) -> str:
    return (r"\begin{enumerate}[leftmargin=1.4em,itemsep=0pt,label=\rubric{\arabic*.}]"
            + "".join(r"\item " + x for x in items) + r"\end{enumerate}")


def sup_pairs(prs) -> str:
    return r"\par ".join((r"\Vs " if k == "V" else r"\Rs ") + tex(v) for k, v in prs)


def date_en(mmdd: str) -> str:
    try:
        m, d = (int(x) for x in mmdd.split("-"))
        return f"{d} {MONTHS[m - 1]}"
    except (ValueError, IndexError):
        return ""


def nice_case(t: str) -> str:
    """Printed titles are upper case in the sources: render in title case for the small-caps heading."""
    if t.isupper():
        return t.lower().capitalize()
    return t


def fold_sort(s: str) -> str:
    from lh.model.canon import fold
    return fold(s)


def name_key(title: str) -> str:
    return re.sub(r"^(Saints?|Blessed|The|Our|Most|Holy)\s+", "", title)


def canticle_sort(ref: str):
    books = ["Ex", "Deut", "1 Sam", "1 Chr", "Tob", "Iudt", "Sap", "Eccli", "Is", "Ier", "Ez", "Dan", "Hab",
             "Psalmi", "Lc", "Eph", "Phil", "Col", "1 Tim", "1 Petr", "Ap"]
    r = re.sub(r"^\(?Cf\.\s*", "", ref)
    for i, b in enumerate(books):
        if r.startswith(b + " "):
            nums = [int(x) for x in re.findall(r"\d+", r[len(b):])[:2]]
            return (i, nums)
    return (99, [ref])


def reading_part(k: str) -> str:
    if k.startswith("ADV."):
        return "Advent"
    if k.startswith(("CHR.", "FEAST.")) or k in ("SOL.CHRISTMAS", "SOL.MARY_MOTHER_OF_GOD", "SOL.EPIPHANY"):
        return "Christmas Time"
    if k.startswith("LENT."):
        return "Lent"
    if k.startswith(("HOLY.", "TRIDUUM.")):
        return "Holy Week and the Paschal Triduum"
    if k.startswith("EAS.") or k in ("SOL.ASCENSION", "SOL.PENTECOST"):
        return "Eastertide"
    if k.startswith(("OT.", "SOL.")) and k != "SOL.IMMACULATE_CONCEPTION":
        return "Ordinary Time"
    if k.startswith("COMMON."):
        return "Commons"
    if k == "DEAD":
        return "Office for the Dead"
    if k.startswith("MEM."):
        return "Saturday memorial of the Blessed Virgin Mary"
    return "Proper of Saints"


def write_book() -> tuple[str, Book]:
    out = BOOK / "generated"
    out.mkdir(parents=True, exist_ok=True)
    b = Book()
    body = b.body()
    (out / "book_body.tex").write_text(body, encoding="utf-8")
    return str(out / "book_body.tex"), b
