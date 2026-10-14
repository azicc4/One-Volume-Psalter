"""Proof-of-concept book: Psalter-week I, Sunday and Monday, generated entirely from build/lh.sqlite.

Sections follow the planned book order: Psalter (+ Canticles) · Hymns · Ordinary · Propers of Time · OR Readings.
Every object is printed once at its home and referenced elsewhere by \\pageref, so page numbers stay correct.
Shared pieces (data access, variant grid, Psalter writer) are in lh/render/common.py; the full book is book.py.
"""
from __future__ import annotations

import collections
import json
import re

from lh.config import BOOK
from lh.model.canon import plain, psalm_base
from lh.model.days import DAY_NAMES
from lh.render import latex as L
from lh.render.common import (DB, GOSPEL, HOUR_TITLE, ROMAN, SEASON_LABEL, SEASON_ORDER, SLOT_NAME, SLOT_ORDER,
                              SUB_TITLE, PsalterWriter, finding_the_office, labels_for, load_supplement, obj_ref,
                              opening_block, ribbon_refs, slot_groups, unit_anchor)
from lh.render.latex import esc, label, tex


class POC(PsalterWriter):
    PW, WEEKDAYS = 1, ("SUN", "MON")

    def __init__(self):
        self.db = DB()
        self.supp = load_supplement()
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
    def psalter(self) -> str:
        out = [r"\chapter{The Psalter}", r"\objlabel{sec:psalter}", self.PSALTER_INTRO, r"\par\vspace{\baselineskip}"]
        for num in self.psalms_needed():
            out.append(self.psalm(num))
        out.append(self.canticles())
        return "\n".join(out)

    def canticles(self) -> str:
        out = [r"\chapter{Canticles}", r"\objlabel{sec:canticles}",
               r"\rubr{Old and New Testament canticles of Lauds and Vespers. The Gospel canticles (Benedictus, "
               r"Magnificat, Nunc dimittis) are in the Ordinary.}"]
        cants = {oid: self.db.obj(oid) for oid in self.used_objects if self.db.obj(oid).type == "canticle"
                 and not self.db.obj(oid).payload.get("gospel")}
        for o in sorted(cants.values(), key=lambda o: (o.payload["ref"], o.id)):
            out.append(self.canticle(o))
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
        out += [finding_the_office(), opening_block(s)]
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
        return ribbon_refs(self.db, days, hour)

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
