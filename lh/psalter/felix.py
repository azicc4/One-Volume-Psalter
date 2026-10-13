"""Import Felix Just's four-week psalter tables (catholic-resources.org/LoH) into data/seed/felix_just_psalter.csv.

Sources (cached in sources/web/felix_just/): Psalter.html (weekly charts: OR, MP, DP, EP1/EP2/EP),
Psalter-Hours.html (adds Night Prayer, complementary psalmody, invitatory). Numbering is Hebrew (US LOTH).
"""
from __future__ import annotations

import csv
import html
import re

from lh.config import SEED, SOURCES_WEB

FJ = SOURCES_WEB / "felix_just"
SEED_CSV = SEED / "felix_just_psalter.csv"
HOURS = {"EP1": "V1", "OR": "OR", "MP": "LAUDS", "DP": "MIDDAY", "EP2": "V2", "EP": "VESPERS"}
DAYS = {"Sunday": "SUN", "Monday": "MON", "Tuesday": "TUE", "Wednesday": "WED", "Thursday": "THU",
        "Friday": "FRI", "Saturday": "SAT"}
FIELDS = ["week", "day", "hour", "slot", "ref", "season", "note", "source"]


def table_rows(name: str) -> list[list[str]]:
    s = (FJ / name).read_text(encoding="latin-1")
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S | re.I):
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S | re.I)]
        out.append(cells)
    return out


def split_alt(ref: str) -> tuple[str, str]:
    """'Rev 19:1-7 ( Lent: 1 Pet 2:21-24)' → ('Rev 19:1-7', 'Lent: 1 Pet 2:21-24')."""
    m = re.match(r"^(.*?)\s*\(\s*(Lent:[^)]*)\)\s*$", ref)
    return (m.group(1).strip(), m.group(2).strip()) if m else (ref, "")


def import_felix() -> list[dict]:
    rows: list[dict] = []
    week = None
    for cells in table_rows("Psalter.html"):
        if len(cells) == 1 and (m := re.match(r"^WEEK (\d)$", cells[0])):
            week = int(m.group(1))
            continue
        if len(cells) < 4 or week is None or cells[0].startswith("Day"):
            continue
        m = re.match(r"^(\*)?(\w+): (\w+)(?: \((\d/\d)\))?$", cells[0])
        if not m:
            continue
        _, dayname, hour, vols = m.groups()
        season = {"1/2": "seasonal", "3/4": "per_annum"}.get(vols, "all")
        for slot, ref in enumerate(cells[1:4], 1):
            ref, note = split_alt(ref)
            rows.append({"week": week, "day": DAYS[dayname], "hour": HOURS[hour], "slot": f"PS{slot}", "ref": ref,
                         "season": season, "note": note, "source": "Psalter.html"})
    # Night Prayer (same every week) and complementary psalmody from Psalter-Hours.html
    section = ""
    for cells in table_rows("Psalter-Hours.html"):
        j = " | ".join(cells)
        if re.match(r"^(NIGHT PRAYER|Complementary Psalmody)", j):
            section = j.split(":")[0]
            continue
        if re.match(r"^[A-Z ]+:$", j):
            section = ""
            continue
        if section == "NIGHT PRAYER" and len(cells) >= 3 and not cells[0].startswith("Day"):
            name = cells[0]
            if name.startswith("Saturday"):
                day, hour = "SUN", "COMPLINE1"
            else:
                day, hour = DAYS[name.split()[0]], "COMPLINE"
            for slot, ref in enumerate(re.split(r"\s+and\s+", cells[1]), 1):
                rows.append({"week": "*", "day": day, "hour": hour, "slot": f"PS{slot}", "ref": ref.strip(),
                             "season": "all", "note": "", "source": "Psalter-Hours.html"})
            rows.append({"week": "*", "day": day, "hour": hour, "slot": "LB", "ref": cells[2], "season": "all",
                         "note": "", "source": "Psalter-Hours.html"})
        if section.startswith("Complementary Psalmody") and cells and re.match(r"^Series [IV]+ ", cells[0]):
            sub = {"I": "TERCE", "II": "SEXT", "III": "NONE"}[cells[0].split()[1]]
            for slot, ref in enumerate(cells[1:4], 1):
                rows.append({"week": "*", "day": "*", "hour": f"COMPLEMENTARY.{sub}", "slot": f"PS{slot}", "ref": ref,
                             "season": "all", "note": "", "source": "Psalter-Hours.html"})
    SEED.mkdir(parents=True, exist_ok=True)
    with open(SEED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


def load_felix() -> list[dict]:
    with open(SEED_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))
