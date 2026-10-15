"""Batches of simulated days: a timed trial, then whole liturgical years under each ribbon policy and layout variant.

Writes build/sim/events.jsonl.gz (every page move and ribbon movement of the baseline runs), build/sim/days.jsonl
(one summary per simulated day) and reports/simulation.md.
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import random
import sqlite3
import statistics
import time

from lh.config import BUILD, DB_PATH, REPORTS
from lh.sim.calendar import Calendar, advent1
from lh.sim.layout import Layout
from lh.sim.office import Offices
from lh.sim.reader import COST, RIBBONS, Reader, summarize

OUT = BUILD / "sim"
FULL_DAY = ("INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE")


def without_card(steps):
    """The texts on the Ordinary card (book/out/card.pdf, B-14) are said from the card: no page to find.
    In Compline the form prints them too, so they are read where the reader already is."""
    from lh.sim.whatif import FULL
    return [s for s in steps if s.slot not in FULL]


class Sim:
    def __init__(self):
        t0 = time.time()
        self.con = sqlite3.connect(DB_PATH)
        self.con.row_factory = sqlite3.Row
        self.L = Layout()
        _ = self.L.book
        self.cals = {False: Calendar(self.con, optional=False), True: Calendar(self.con, optional=True)}
        self.off = {k: Offices(self.con, self.L, c) for k, c in self.cals.items()}
        self.init_seconds = time.time() - t0
        self.steps_cache: dict = {}

    def steps(self, d: dt.date, optional=False, hours=FULL_DAY):
        key = (d, optional, hours)
        if key not in self.steps_cache:
            cal, off = self.cals[optional], self.off[optional]
            cel, tom = cal.celebration(d), cal.celebration(d + dt.timedelta(days=1))
            self.steps_cache[key] = (cel, off.day(cel, tom, hours))
        return self.steps_cache[key]

    def run_days(self, dates, policy="roles", optional=False, hours=FULL_DAY, transform=None, log=None, tag="",
                 ahead=True, split=False, card=True, scheme="by_use"):
        """Simulate consecutive days with one reader (ribbons carry over). Returns one summary per day.
        ahead: the reader leaves ribbons where tomorrow needs them too; split: two ribbons for the Ordinary;
        card: the Ordinary card is in hand (its texts need no page); scheme: which ribbon keeps which place."""
        reader = Reader(self.L, policy, split_ordinary=split, scheme=scheme)
        rows = []
        for d in dates:
            cel, steps = self.steps(d, optional, hours)
            nxt = self.steps(d + dt.timedelta(days=1), optional, hours)[1] if ahead else []
            if card:
                steps, nxt = without_card(steps), without_card(nxt)
            if transform:
                steps, nxt = transform(steps), transform(nxt)
            events = reader.day(steps, nxt)
            s = summarize(events)
            per_hour = collections.defaultdict(lambda: collections.Counter())
            for e in events:
                h = per_hour[e.hour]
                h["steps"] += 1
                if e.action != "stay":
                    h[e.action] += 1
                    h["moves"] += 1
                if e.laid:
                    h["lay"] += 1
                h["seconds"] += e.cost
            rows.append({"tag": tag, "date": d.isoformat(), "office": cel.office, "kind": cel.kind,
                         "season": cel.temporal.split(".")[0], "policy": policy, **s,
                         "hours": {k: dict(v) for k, v in per_hour.items()}})
            if log is not None:
                for e, st in zip(events, steps):
                    if e.action == "stay" and not e.laid:
                        continue
                    log.write(json.dumps({"tag": tag, "date": d.isoformat(), "office": cel.office, "hour": e.hour,
                                          "slot": e.slot, "what": e.what, "from": self.page_of_spread(e.frm),
                                          "to": self.L.label(st.page), "section": self.L.section(st.page)[0],
                                          "action": e.action, "ribbon": e.ribbon, "laid": e.laid,
                                          "laid_from": self.page_of_spread(e.laid_from), "cost": e.cost},
                                         ensure_ascii=False) + "\n")
        return rows

    def page_of_spread(self, s):
        if s is None:
            return None
        lo, hi = 2 * s - 1, 2 * s
        return f"{self.L.label(lo) if lo >= 0 else '-'}|{self.L.label(hi) if hi < self.L.n else '-'}"


def liturgical_year(y: int) -> list[dt.date]:
    """Every date of the liturgical year that begins at Advent of year y."""
    a, b = advent1(y), advent1(y + 1)
    return [a + dt.timedelta(days=i) for i in range((b - a).days)]


def trial(sim: Sim, n=10, seed=1):
    """Phase 1: n random single days, timed."""
    rng = random.Random(seed)
    dates = sorted(rng.sample(liturgical_year(2026), n))
    t0 = time.perf_counter()
    rows = []
    for d in dates:
        rows += sim.run_days([d], "roles", tag="trial")
    per = (time.perf_counter() - t0) / n
    return rows, per


EXPERIMENTS = [
    # the book as built now: Ordinary card (B-14), whole Compline (B-15), ribbons by use (B-16)
    {"name": "book as printed: card, whole Compline, ribbons by use (baseline)"},
    {"name": "the same, ribbons by section (the first scheme)", "scheme": "by_section"},
    {"name": "the same, a tenth ribbon for where the hour continues", "scheme": "by_use10"},
    {"name": "the same, ribbons used freely (best case for these ribbons)", "policy": "free"},
    {"name": "the same, without the Ordinary card", "card": False},
    {"name": "the same, no ribbons", "policy": "none"},
    {"name": "without the card, ribbons by section (close to the book before B-14..B-16)", "card": False,
     "scheme": "by_section"},
    {"name": "+ psalms of the four-week cycle printed at each hour", "variants": ("psalmody",)},
    {"name": "+ hymns of the four-week cycle printed at each hour", "variants": ("hymn",)},
    {"name": "+ psalms and hymns printed at each hour (exp/weekly-psalter)", "variants": ("psalmody", "hymn")},
    # proposals that only reorder what is printed (no text added): the Psalter in the order of the cycle
    {"name": "+ Psalter in the order of the four-week cycle", "variants": ("cycle",)},
    {"name": "+ psalmody blocks: cycle-order Psalter with each hour's antiphons", "variants": ("block",)},
    {"name": "+ psalmody blocks and hymns printed at each hour", "variants": ("block", "hymn")},
]


def experiments(sim: Sim, years: int, first_year: int = 2026, deadline: float | None = None):
    """Phase 3: every experiment over the same consecutive dates (one reader for the whole span)."""
    from lh.sim.whatif import WhatIf
    wi = WhatIf(sim.L)
    dates = [d for y in range(first_year, first_year + years) for d in liturgical_year(y)]
    results = []
    with (OUT / "experiments.jsonl").open("w", encoding="utf-8") as out:
        for e in EXPERIMENTS:
            name, variants = e["name"], tuple(e.get("variants", ()))
            policy, scheme, card = e.get("policy", "roles"), e.get("scheme", "by_use"), e.get("card", True)
            t0 = time.time()
            rows = sim.run_days(dates, policy, transform=wi.transform(variants) if variants else None,
                                tag=name, scheme=scheme, card=card)
            res = {"name": name, "policy": policy, "scheme": scheme, "card": card, "variants": list(variants),
                   "days": len(rows), "seconds_run": time.time() - t0,
                   "extra_pages": round(wi.extra_pages(variants)) if variants else 0}
            for k in ("steps", "moves", "turn", "ribbon", "search", "lay", "seconds"):
                res[k] = statistics.mean(r[k] for r in rows)
            hours = collections.defaultdict(collections.Counter)
            for r in rows:
                for h, c in r["hours"].items():
                    hours[h].update(c)
                    hours[h]["n"] += 1
            res["hours"] = {h: {k: v / c["n"] for k, v in c.items() if k != "n"} for h, c in hours.items()}
            out.write(json.dumps(res) + "\n")
            results.append(res)
            print(f"[sim] {name}: {res['search']:.1f} look-ups, {res['moves']:.1f} moves, "
                  f"{res['seconds'] / 60:.1f} min/day, +{res['extra_pages']} pp ({res['seconds_run']:.0f}s)")
            if deadline and time.time() > deadline:
                print("[sim] budget reached")
                break
    return results


PROFILES = [("all hours (Invitatory, Office of Readings, Lauds, Sext, Vespers, Compline)", FULL_DAY),
            ("Lauds, Vespers, Compline", ("LAUDS", "VESPERS", "COMPLINE")),
            ("Office of Readings, Lauds, Vespers, Compline", ("INV", "OR", "LAUDS", "VESPERS", "COMPLINE"))]


def profiles(sim: Sim, years: int, first_year: int = 2026):
    """Phase 4: who prays which hours — the book as printed against the weekly-psalter variant."""
    from lh.sim.whatif import WhatIf
    wi = WhatIf(sim.L)
    dates = [d for y in range(first_year, first_year + years) for d in liturgical_year(y)]
    out = []
    for pname, hours in PROFILES:
        for lname, variants in (("as printed", ()), ("+ psalms and hymns at each hour", ("psalmody", "hymn"))):
            rows = sim.run_days(dates, "roles", hours=hours, transform=wi.transform(variants) if variants else None,
                                tag=f"{pname} / {lname}", scheme="by_use")
            r = {"profile": pname, "layout": lname, "days": len(rows)}
            for k in ("moves", "search", "ribbon", "lay", "seconds"):
                r[k] = statistics.mean(x[k] for x in rows)
            out.append(r)
            print(f"[sim] {pname} / {lname}: {r['search']:.1f} look-ups, {r['seconds'] / 60:.1f} min/day")
    with (OUT / "profiles.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    return out


def main(budget_min: float = 90, seed: int = 1, first_year: int = 2026):
    OUT.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    sim = Sim()
    print(f"[sim] init {sim.init_seconds:.1f}s (book generator, page labels, calendar)")
    trial_rows, per_day = trial(sim, 10, seed)
    print(f"[sim] trial: 10 days, {per_day * 1000:.0f} ms per simulated day (all six hours)")
    for r in trial_rows:
        print(f"   {r['date']} {r['office']:<40} moves {r['moves']:3}  searches {r['search']:3}  ribbon {r['ribbon']:3}"
              f"  laid {r['lay']:3}  ~{r['seconds'] / 60:.1f} min handling")
    # Phase 2: plan whole liturgical years within the budget. One year ≈ 365 days per (policy, variant).
    variants = [("roles", False), ("free", False), ("none", False), ("roles", True)]   # ribbons by use
    year_cost = 365 * per_day * len(variants) * 1.3          # cached steps make re-runs cheaper; keep a margin
    budget = budget_min * 60 - (time.time() - t_start)
    years = max(1, min(28, int(budget / year_cost)))
    print(f"[sim] budget {budget_min:.0f} min → {years} liturgical years ({first_year}–{first_year + years}) × "
          f"{len(variants)} runs")
    days_log = (OUT / "days.jsonl").open("w", encoding="utf-8")
    ev_log = gzip.open(OUT / "events.jsonl.gz", "wt", encoding="utf-8")
    all_rows = trial_rows[:]
    for r in trial_rows:
        days_log.write(json.dumps(r) + "\n")
    for i in range(years):
        y = first_year + i
        dates = liturgical_year(y)
        for policy, optional in variants:
            tag = f"{policy}{'+optional' if optional else ''}"
            rows = sim.run_days(dates, policy, optional, tag=tag, log=ev_log if tag == "roles" else None)
            for r in rows:
                r["year"] = y
                days_log.write(json.dumps(r) + "\n")
            all_rows += rows
        if time.time() - t_start > budget_min * 60:
            print("[sim] budget reached")
            break
        print(f"[sim] {y}/{y + 1} done ({time.time() - t_start:.0f}s)")
    days_log.close()
    ev_log.close()
    timing = {"init": sim.init_seconds, "per_day_ms": per_day * 1000, "phase2_days": len(all_rows),
              "phase2_min": (time.time() - t_start) / 60, "years": years}
    deadline = t_start + budget_min * 60
    t3 = time.time()
    exp = experiments(sim, years, first_year, deadline)
    timing["phase3_min"] = (time.time() - t3) / 60
    t4 = time.time()
    prof = profiles(sim, years, first_year) if time.time() < deadline else []
    timing["phase4_min"] = (time.time() - t4) / 60
    timing["total_min"] = (time.time() - t_start) / 60
    timing["budget_min"] = budget_min
    from lh.sim.report import write_report
    path = write_report(sim, trial_rows, all_rows, exp, prof, timing)
    print(f"[sim] report -> {path}  ({timing['total_min']:.1f} min in all)")
    return path
