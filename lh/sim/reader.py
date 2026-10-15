"""A reader with the book's ribbons, turning through the steps of a day.

Moving to another spread is one of:
  turn    the next or previous spread (a page turn)
  ribbon  open the book at a ribbon that lies in the target spread
  search  look the page up by its number (riffle the edge, check the folio)
and, after arriving, the reader may lay a ribbon there (lay).

Ribbon policies:
  roles  each ribbon keeps a part of the book, as a ribbon scheme says (SCHEMES). Arriving at a page of a part
         that will be needed again (later today or tomorrow), the reader moves one of that part's ribbons there —
         the one whose place is needed last — unless every one of them marks a place needed sooner.
  free   any ribbon may mark any place; a ribbon is laid only where the reader will come back, taking the ribbon
         whose place is needed last (Belady's rule): the best these ribbons can do for this layout.
  none   no ribbons: a lower baseline.
Ribbons stay where they are from one day to the next.

Cost: seconds per action, rough handling times for a ~2,800-page book; the counts are the primary result.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COST = {"turn": 1.5, "ribbon": 2.5, "search": 8.0, "lay": 3.0}

# A scheme: the ribbons in order, (id, name, part). Parts: S Saints, C Commons, O Ordinary, T Proper of Time,
# H Hymns, P Psalter and Canticles, R Readings; P1–P3 the n-th psalm of an hour, P4 the Invitatory psalm.
SCHEMES = {
    "by_section": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary", "O"),
                   ("T", "4 Proper of Time", "T"), ("H", "5 Hymns", "H"), ("P1", "6 Psalter — first psalm", "P1"),
                   ("P2", "7 Psalter — second psalm", "P2"), ("P3", "8 Psalter — third psalm", "P3"),
                   ("P4", "9 Psalter — Invitatory psalm", "P4"), ("R", "10 Readings", "R")],
    # the scheme of the book (B-16): nine ribbons (lh/render/common.py RIBBONS; tools/viewer)
    "by_use": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary: Compline, Daytime Prayer", "O"),
               ("T1", "4 Proper of Time: the hour", "T"), ("T3", "5 Proper of Time: the week", "T"),
               ("H", "6 Hymns", "H"), ("P1", "7 Psalter", "P"), ("P2", "8 Psalter, Canticles", "P"),
               ("R", "9 Readings", "R")],
    # the first B-16 scheme: ten ribbons, with a third for the Proper of Time (where the hour continues)
    "by_use10": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary", "O"),
                 ("T1", "4 Time: the hour", "T"), ("T2", "5 Time: next page", "T"), ("T3", "6 Time: the week", "T"),
                 ("H", "7 Hymns", "H"), ("P1", "8 Psalter", "P"), ("P2", "9 Psalter, Canticles", "P"),
                 ("R", "10 Readings", "R")],
    "use_b": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary", "O"), ("T1", "4 Time", "T"),
              ("T2", "5 Time", "T"), ("H", "6 Hymns", "H"), ("P1", "7 Psalter", "P"), ("P2", "8 Psalter", "P"),
              ("P3", "9 Psalter", "P"), ("R", "10 Readings", "R")],
    "use_c": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary", "O"), ("T1", "4 Time", "T"),
              ("T2", "5 Time", "T"), ("T3", "6 Time", "T"), ("T4", "7 Time", "T"), ("H", "8 Hymns", "H"),
              ("P1", "9 Psalter", "P"), ("R", "10 Readings", "R")],
    "use_e": [("S", "1 Saints, Commons", "S/C"), ("C", "2 Saints, Commons", "S/C"), ("O", "3 Ordinary", "O"),
              ("T1", "4 Time", "T"), ("T2", "5 Time", "T"), ("T3", "6 Time", "T"), ("H", "7 Hymns", "H"),
              ("P1", "8 Psalter", "P"), ("P2", "9 Psalter", "P"), ("R", "10 Readings", "R")],
    "use_f": [("S", "1 Saints, Commons", "S/C"), ("C", "2 Saints, Commons, Time", "S/C/T"), ("O", "3 Ordinary", "O"),
              ("T1", "4 Time", "T"), ("T2", "5 Time", "T"), ("T3", "6 Time, Hymns", "T/H"), ("H", "7 Hymns", "H"),
              ("P1", "8 Psalter", "P"), ("P2", "9 Psalter, Readings", "P/R"), ("R", "10 Readings", "R")],
    "use_d": [("S", "1 Saints", "S"), ("C", "2 Commons", "C"), ("O", "3 Ordinary", "O"), ("T1", "4 Time", "T"),
              ("T2", "5 Time", "T"), ("T3", "6 Time", "T"), ("H", "7 Hymns", "H"), ("P1", "8 Psalter", "P"),
              ("R1", "9 Readings", "R"), ("R2", "10 Readings", "R")],
}
RIBBONS = [r for r, _, _ in SCHEMES["by_section"]]          # ids of the by-section scheme (logs, report)


def ribbon_names(scheme: str) -> dict[str, str]:
    return {r: n for r, n, _ in SCHEMES[scheme]}


@dataclass
class Event:
    i: int                                 # step index in the day
    hour: str
    slot: str
    what: str
    frm: int | None                        # spread before
    to: int                                # spread after
    action: str                            # stay | turn | ribbon | search
    ribbon: str | None = None              # ribbon used (ribbon) or laid (lay)
    laid: str | None = None
    laid_from: int | None = None
    cost: float = 0.0

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Reader:
    layout: object
    policy: str = "roles"
    split_ordinary: bool = False           # by-section variant: ribbon 9 keeps the Ordinary's end-of-hour parts
    scheme: str = "by_section"
    ribbons: dict = field(default_factory=dict)
    at: int | None = None

    END_PARTS = {"PATER", "CONCLUSION", "BLESSING", "MARIAN"}

    def __post_init__(self):
        if not self.ribbons:
            self.ribbons = {r: None for r, _, _ in SCHEMES[self.scheme]}
        self.part = {r: p for r, _, p in SCHEMES[self.scheme]}

    def part_of(self, step) -> str | None:
        """The part of the book a step's page belongs to, in the terms of the scheme."""
        role = self.layout.role(step.page)
        if self.scheme == "by_section":
            if self.split_ordinary and role == "O" and (step.slot in self.END_PARTS or step.hour.startswith("COMPLINE")):
                return "P4"
            if step.slot == "INV_PSALM":
                return "O" if self.split_ordinary else "P4"
            if role == "P":
                n = step.slot[2:3] if step.slot.startswith("PS") else "1"
                return {"1": "P1", "2": "P2", "3": "P3"}.get(n, "P1")
        return role if role in "SCOTHPR" else None

    def next_use(self, spreads: list[int], i: int, s: int | None) -> float:
        if s is None:
            return float("inf")
        for j in range(i + 1, len(spreads)):
            if spreads[j] == s:
                return j
        return float("inf")

    def day(self, steps: list, ahead: list = ()) -> list[Event]:
        """Turn through one day's steps. `ahead` (tomorrow's steps) only informs where ribbons are worth leaving:
        a reader who knows the routine keeps a ribbon at a page used every day."""
        L = self.layout
        spreads = [L.spread(s.page) for s in steps] + [L.spread(s.page) for s in ahead]
        events = []
        for i, st in enumerate(steps):
            to = spreads[i]
            frm = self.at
            ev = Event(i, st.hour, st.slot, st.what, frm, to, "stay")
            if frm != to:
                held = [r for r, s in self.ribbons.items() if s == to]
                if frm is not None and abs(to - frm) == 1:
                    ev.action = "turn"
                elif held:
                    ev.action, ev.ribbon = "ribbon", held[0]
                else:
                    ev.action = "search"
                ev.cost += COST[ev.action]
                self.at = to
            self.lay(ev, st, i, spreads)
            events.append(ev)
        return events

    def lay(self, ev: Event, st, i: int, spreads: list[int]):
        to = spreads[i]
        if self.policy == "none" or any(s == to for s in self.ribbons.values()):
            return
        nxt = self.next_use(spreads, i, to)
        if nxt == float("inf"):
            return
        if self.policy == "roles":
            part = self.part_of(st)
            pool = [r for r, p in self.part.items() if part in p.split("/")]      # "S/C": either part
        else:                                    # free: any ribbon
            pool = list(self.ribbons)
        if not pool:
            return
        # Belady within the pool: the ribbon whose place is needed last (or that marks nothing)
        r = max(pool, key=lambda k: (self.next_use(spreads, i, self.ribbons[k]), self.ribbons[k] is None))
        if self.next_use(spreads, i, self.ribbons[r]) < nxt:
            return
        ev.laid, ev.laid_from = r, self.ribbons[r]
        self.ribbons[r] = to
        ev.cost += COST["lay"]


def summarize(events: list[Event]) -> dict:
    out = {"steps": len(events), "moves": 0, "turn": 0, "ribbon": 0, "search": 0, "lay": 0, "seconds": 0.0}
    for e in events:
        if e.action != "stay":
            out["moves"] += 1
            out[e.action] += 1
        if e.laid:
            out["lay"] += 1
        out["seconds"] += e.cost
    return out
