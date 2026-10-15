"""Layout what-ifs: the same days, with some texts printed (or carried) elsewhere, and what that would cost in pages.

A variant transforms the steps of a day before the reader turns through them:
  card_short   a loose card (or the inside cover) with the short fixed parts: opening verses, Pater noster,
               dismissals, Compline blessing and Marian antiphon — nothing to look up
  card_full    card_short + the Gospel canticles (Benedictus, Magnificat, Nunc dimittis), Psalm 95 and the Te Deum
  psalmody     the psalms of the four-week cycle printed with their antiphons at each hour of the cycle (a psalter
               in weekly order, as in the four-volume breviary), in addition to the psalter in biblical order;
               proper days and saints keep their page references
  hymn         the hymns of the four-week cycle printed at each hour of the cycle
  compline     each weekly Compline form printed whole (its psalm and the parts it shares with other forms)
  cycle        the Psalter printed in the order of the four-week cycle instead of biblical order: each hour's psalms
               and canticles follow one another, and each hour follows the one before; every text once (a repeat
               refers to its first printing); psalms the cycle does not use stay in biblical order after it.
               Pages are virtual (lh.sim.layout.VIRTUAL), sized by text length.
  block        cycle, with each hour's antiphons printed beside its psalms (psalmody blocks, as the four-volume
               breviary's psalter): the hour's grid page keeps the rest (hymn, reading, responsory, prayers)
Extra pages are estimated from the length of every text that would be printed again at a new place, at the text
density of the section it now lives in.
"""
from __future__ import annotations

import dataclasses
import re

from lh.model.attribute import GRID_RE, PROPER_DAYS, WD, content, is_grid
from lh.sim.layout import VIRTUAL

CYCLE_HOURS = ("V1", "INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "V2")
PSALM = re.compile(r"^PS(\d)$")
ANTIPHON = re.compile(r"^ANT(\d?)(_R)?$")


def in_grid(key: str) -> bool:
    """A day of the four-week cycle (printed in the grid of the Proper of Time)."""
    return bool(GRID_RE.match(key)) and key not in PROPER_DAYS

SHORT = {"OPENING", "PATER", "CONCLUSION", "BLESSING", "MARIAN"}
FULL = SHORT | {"GOSPEL_CANT", "INV_PSALM", "TE_DEUM"}


def text_len(x) -> int:
    if isinstance(x, str):
        return len(x)
    if isinstance(x, dict):
        return sum(text_len(v) for k, v in x.items() if k not in ("ref", "vulg", "x", "v", "id"))
    if isinstance(x, (list, tuple)):
        return sum(text_len(v) for v in x)
    return 0


class WhatIf:
    def __init__(self, layout):
        self.L = layout
        self.dups: dict[str, set] = {}               # variant → {(place, object id)} printed again
        b = layout.book
        self.len = {oid: text_len(o.payload) for oid, o in b.objs.items()}
        # characters per page of each section (its own texts over its pages)
        pages, chars = {}, {}
        for oid, o in b.objs.items():
            p = layout.object_page(oid)
            if p is None:
                continue
            sec = layout.section(p)[0]
            chars[sec] = chars.get(sec, 0) + self.len[oid]
        bounds = layout.sections + [(layout.n, "", "")]
        for (a, t, _), (b2, _, _) in zip(bounds, bounds[1:]):
            pages[t] = b2 - a
        self.density = {t: chars.get(t, 0) / max(1, pages.get(t, 1)) for t in pages}
        self._cycle = None

    def cycle_pages(self) -> dict[str, int]:
        """Virtual page of every psalm and canticle of the four-week cycle in a Psalter printed in cycle order
        (week I Sunday First Vespers … week IV Saturday), each text at its first use, antiphons beside them."""
        if self._cycle is not None:
            return self._cycle
        db = self.L.book.db
        dens = self.density.get("The Psalter") or 1800
        pos, pages = 0.0, {}
        order = {"OT": 0, "ADV": 1, "LENT": 2, "EAS": 3}
        for pw in (1, 2, 3, 4):
            for wd in WD:
                days = sorted((d for d in db.days(pw, wd) if is_grid(d)), key=lambda d: (order[d["season"]], d["week"]))
                for hour in CYCLE_HOURS:
                    for d in days:
                        h = db.hour(d["key"], hour)
                        if not h:
                            continue
                        for o in content(db.occ(h["id"])):
                            oid, slot = o["object_id"], o["slot"] or ""
                            if PSALM.match(slot) and oid not in pages:
                                pages[oid] = VIRTUAL + int(pos)
                                pos += self.len.get(oid, 0) / dens
                            elif ANTIPHON.match(slot) and not slot.endswith("_R"):
                                pos += self.len.get(oid, 0) / dens
        self._cycle, self.cycle_length = pages, pos
        return pages

    def transform(self, names: tuple[str, ...]):
        forms = {p for k, p in self.L.page_label.items() if k.startswith("ord:compline:")}
        cyc = self.cycle_pages() if ("cycle" in names or "block" in names) else {}

        def f(steps):
            out = []
            ant_page = {}
            head = form = None
            # psalmody blocks: each hour's psalm pages in the cycle-order Psalter, by psalm number
            block = {}
            seg = 0
            for s in steps:
                seg += s.slot == "HEAD"
                m = PSALM.match(s.slot)
                if m and s.what in cyc and in_grid(s.source) and not s.hour.startswith("COMPLINE"):
                    block.setdefault((seg, m.group(1)), cyc[s.what])
                    block.setdefault((seg, ""), cyc[s.what])
            seg = 0
            for i, s in enumerate(steps):
                seg += s.slot == "HEAD"
                if s.slot == "HEAD":
                    head, ant_page = s.page, {}
                    # Compline is printed in the Ordinary's weekly forms (a proper day's heading only points there)
                    form = next((t.page for t in steps[i:] if t.hour == s.hour and t.page in forms), s.page)
                if s.slot.startswith("ANT") and not s.slot.endswith("_R"):
                    ant_page[s.slot[3:] or "*"] = s.page
                card = FULL if "card_full" in names else SHORT if "card_short" in names else set()
                if s.slot in card:
                    continue
                page = s.page
                cycle = in_grid(s.source) and not s.hour.startswith("COMPLINE")
                if "psalmody" in names and cycle and s.slot[:2] == "PS" and s.slot[2:].isdigit():
                    page = ant_page.get(s.slot[2:], ant_page.get("*", head))
                if "hymn" in names and cycle and s.slot == "HYMN" and head is not None:
                    page = head
                if "compline" in names and s.hour.startswith("COMPLINE") and s.slot != "HEAD" and form is not None:
                    page = form
                moved = False
                if cyc:
                    # the cycle-order Psalter replaces the biblical one: a psalm is found there on every day
                    m, a = PSALM.match(s.slot), ANTIPHON.match(s.slot)
                    if m and s.what in cyc:
                        page, moved = cyc[s.what], True
                    elif a and cycle and "block" in names and (seg, a.group(1)) in block:
                        page, moved = block[(seg, a.group(1))], True
                if moved:
                    s = dataclasses.replace(s, page=page)      # reordered, not printed again
                elif page != s.page:
                    self.dups.setdefault(names, set()).add((self.L.spread(page), s.what))
                    s = dataclasses.replace(s, page=page)
                out.append(s)
            return out
        return f

    def extra_pages(self, names: tuple[str, ...]) -> float:
        """Rough page cost: every distinct text printed again on a new spread, at the text density of the section it
        is printed in now (psalms at the Psalter's, hymns at the Hymns', …)."""
        total = 0.0
        for spread, what in self.dups.get(names, ()):
            p = self.L.object_page(what)
            dens = self.density.get(self.L.section(p)[0]) if p is not None else None
            total += self.len.get(what, 0) / (dens or 1500)
        return total
