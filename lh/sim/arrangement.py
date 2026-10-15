"""The page arrangement table: for every hour of every day from a start date, the page each ribbon should mark.

Written to book/out/<file>-ribbons.json (book-ribbons.json, book-weekly-ribbons.json) after each build of the book
(python -m lh book; or python -m lh ribbons). The viewer shows it ("Page arrangement table") and lays the ribbons
for a chosen day and hour from it ("Set the ribbons").

A ribbon marks where the hour opens in its part of the book (lh/render/common.py RIBBONS, the nine ribbons by use):
the first page of the hour in the Proper of Saints (1), the Commons (2), the Ordinary (3), the Proper of Time (4; a
second place there, such as the week's collect, 5), the Hymns (6), the Psalter and Canticles (7; a second place, 8)
and the Readings (9). The fixed parts on the Ordinary card need no ribbon.
"""
from __future__ import annotations

import datetime as dt
import json

from lh.config import BOOK, VARIANTS

HOUR_NAME = {"INV": "Invitatory", "OR": "Office of Readings", "LAUDS": "Lauds", "MIDDAY": "Daytime Prayer",
             "VESPERS": "Vespers", "V1": "First Vespers", "V2": "Second Vespers", "COMPLINE": "Compline",
             "COMPLINE1": "Compline"}
# part of the book → the ribbons that keep it (1-based), in the order places are met within an hour
PART_RIBBONS = {"S": [1], "C": [2], "O": [3], "T": [4, 5], "H": [6], "P": [7, 8], "R": [9]}


def hour_ribbons(sim, steps) -> tuple[dict[int, int], int | None]:
    """{ribbon number: page index} for one hour's steps, and the page the hour starts on."""
    L = sim.L
    out: dict[int, int] = {}
    seen: dict[str, list[int]] = {}
    start = steps[0].page if steps else None
    for s in steps:
        part = L.role(s.page)
        free = PART_RIBBONS.get(part)
        if not free:
            continue
        spreads = seen.setdefault(part, [])
        sp = L.spread(s.page)
        if sp in spreads or len(spreads) >= len(free):
            continue
        spreads.append(sp)
        out[free[len(spreads) - 1]] = s.page
    return out, start


def build(variant: str = "main", start: dt.date | None = None, months: int = 6) -> dict:
    from lh.sim.run import Sim, without_card
    sim = Sim(variant)
    start = start or dt.date.today()
    end = start + dt.timedelta(days=round(months * 30.44))
    days = []
    d = start
    while d < end:
        cel, steps = sim.steps(d)
        steps = without_card(steps)
        hours, order = {}, []
        for s in steps:
            if s.hour not in hours:
                hours[s.hour] = []
                order.append(s.hour)
            hours[s.hour].append(s)
        rows = []
        for h in order:
            rib, first = hour_ribbons(sim, hours[h])
            rows.append({"hour": h, "name": HOUR_NAME.get(h, h), "start": sim.L.label(first) if first is not None else "",
                         "ribbons": {str(n): sim.L.label(p) for n, p in sorted(rib.items())}})
        days.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "office": cel.title, "kind": cel.kind,
                     "hours": rows})
        d += dt.timedelta(days=1)
    from lh.render.common import RIBBONS
    return {"file": VARIANTS[variant]["file"], "generated": dt.date.today().isoformat(), "from": start.isoformat(),
            "to": (end - dt.timedelta(days=1)).isoformat(),
            "ribbons": [use for _, use in RIBBONS], "days": days}


def write(variant: str = "main", start: dt.date | None = None, months: int = 6) -> str:
    data = build(variant, start, months)
    path = BOOK / "out" / f"{data['file']}-ribbons.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return str(path)
