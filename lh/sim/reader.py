"""A reader with the book's ten ribbons, turning through the steps of a day.

Moving to another spread is one of:
  turn    the next or previous spread (a page turn)
  ribbon  open the book at a ribbon that lies in the target spread
  search  look the page up by its number (riffle the edge, check the folio)
and, after arriving, the reader may lay a ribbon there (lay).

Ribbon policies:
  roles  the book's design: each ribbon keeps its section (1 Saints, 2 Commons, 3 Ordinary, 4 Proper of Time,
         5 Hymns, 6–9 Psalter 1–4, 10 Readings; the n-th psalm of an hour → Psalter n, the Invitatory psalm →
         Psalter 4). Arriving at a page of a section that will be needed again (later today or tomorrow), the
         reader moves that section's ribbon there, unless the place it marks now is needed sooner.
  free   any ribbon may mark any place; a ribbon is laid only where the reader will come back, taking the ribbon
         whose place is needed last (Belady's rule): the best ten ribbons can do for this layout.
  none   no ribbons: a lower baseline.
Ribbons stay where they are from one day to the next.

Cost: seconds per action, rough handling times for a ~2,800-page book; the counts are the primary result.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RIBBONS = ["S", "C", "O", "T", "H", "P1", "P2", "P3", "P4", "R"]
COST = {"turn": 1.5, "ribbon": 2.5, "search": 8.0, "lay": 3.0}


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
    ribbons: dict = field(default_factory=lambda: {r: None for r in RIBBONS})
    at: int | None = None
    split_ordinary: bool = False           # roles variant: ribbon 9 keeps the Ordinary's end-of-hour parts

    END_PARTS = {"PATER", "CONCLUSION", "BLESSING", "MARIAN"}

    def role_ribbon(self, step) -> str | None:
        role = self.layout.role(step.page)
        if self.split_ordinary and role == "O" and (step.slot in self.END_PARTS or step.hour.startswith("COMPLINE")):
            return "P4"
        if step.slot == "INV_PSALM":
            return "O" if self.split_ordinary else "P4"
        if role == "P":
            n = step.slot[2:3] if step.slot.startswith("PS") else "1"
            return {"1": "P1", "2": "P2", "3": "P3"}.get(n, "P1")
        return {"S": "S", "C": "C", "O": "O", "T": "T", "H": "H", "R": "R"}.get(role)

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
        if self.policy == "roles":
            r = self.role_ribbon(st)
            if r is None:
                return
            cur = self.ribbons[r]
            # keep the ribbon where it is if that place is needed again before this one
            if nxt == float("inf") or cur is not None and self.next_use(spreads, i, cur) < nxt:
                return
        else:                                    # free: only where the reader will come back; Belady's eviction
            if nxt == float("inf"):
                return
            r = max(RIBBONS, key=lambda k: (self.next_use(spreads, i, self.ribbons[k]), self.ribbons[k] is None))
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
