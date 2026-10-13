"""Per-source plug-ins: one module per source PDF, so parallel workstreams touch only their own file.

Each plug-in module defines
  KEY            short source key (PA, ADV, …) — see lh/config.py PDFS
  TITLE          human title of the volume
  NON_CONTENT    [(first_page, last_page, reason)] pages with no liturgical text (cover, title, index, dividers).
                 The coverage check (lh/verify/coverage.py) requires every other line to be in the database.
  day_info(section, day) -> dict
                 map a parsed day (20pt section heading, 16pt day title) to a day record:
                 {key, season, week, weekday, psalter_week, title, rank, precedence}
  COPIES         optional [(first_page, last_page, label)] for volumes that print the same days several times
                 (e.g. Advent once per possible start date); hours in a copy get that label in hour_instance.copy.
  APPENDIX_DAYS  optional {appendix chapter title: day record} for ALIA EX … chapters that are days of their own
                 (e.g. PA: the Saturday memorial of the BVM → MEM.BVM_SATURDAY); others keep ORD./PROP. keys.

Plug-ins for sources that are not parsed yet raise NotImplementedError in day_info; their workstream in TODO.md
implements them.
"""
from __future__ import annotations

import importlib
from types import ModuleType

MODULES = {"PA": "pa", "ADV": "adv", "LQP": "lqp", "COM": "com", "SPA": "spa", "SADV": "sadv", "SP": "sp", "SQ": "sq"}


def plugin(key: str) -> ModuleType:
    return importlib.import_module(f"lh.sources.{MODULES[key]}")


def copy_label(key: str, page: int) -> str | None:
    for p0, p1, lab in getattr(plugin(key), "COPIES", None) or []:
        if p0 <= page <= p1:
            return lab
    return None


def non_content(key: str, page: int) -> str | None:
    for p0, p1, reason in plugin(key).NON_CONTENT:
        if p0 <= page <= p1:
            return reason
    return None
