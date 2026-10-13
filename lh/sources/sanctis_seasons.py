"""Shared Proper-of-Saints header parsing for the seasonal Sanctis volumes SP, SQ and SADV (workstream WS4b).

NOTE: WS4a implements the same header for SPA in parallel; unify the two modules after both are merged.

Day header (docs/source-pdf-format.md §4):

    Die 5 februarii                       14.4 bold   — date line ("Eodem die 8 februarii" for a second saint)
    S. AGATHÆ, VIRGINIS ET MARTYRIS       16.6 bold   — title, may wrap over two lines
    Pro commemoratione                    14.4 italic red — rank (Sollemnitas / Festum / Memoria / Pro commemoratione;
                                                        none = optional memorial); SQ 14 Feb adds a blue link
                                                        "Vel ubi celebratur ut festum." and a second rank "Memoria"
    Martyrium subiit Catanæ …             biography (prose)

The L2 classifier sees the date line as a 14.4 bold "subhour"; `classify_lines` turns it into a `day` line so the
segmenter joins it with the title ("Die 5 februarii / S. AGATHÆ, VIRGINIS ET MARTYRIS"). Rank and biography are
the day's preamble (source_line role day_extra) and reach `day_info` as `extra`.

Day keys: SANCT.MM-DD.<slug>, where <slug> is the folded title up to its first comma, without "S." / "SS." / "IN"
(e.g. SANCT.02-05.agathae, SANCT.03-19.ioseph, SANCT.03-25.annuntiatione-domini). These are title slugs, not LitCal
keys (no LitCal data in the repo yet): the date prefix is the stable part, the slug can be mapped to LitCal keys when
WS4a's table lands. Days the Proper of Time already prints keep their temporale key (SOL.IMMACULATE_CONCEPTION,
CHR.DEC26-28), so the same celebration resolves to one day across volumes.

Seasonal forms are recorded on hour_instance.copy: "commemoratio" (Lent, 17-24 Dec, Christmas octave: OR second
reading + responsory + prayer, Lauds/Vespers antiphon), "altera <label>" (unoutlined ALTERA sections: alternative
offices, labelled as in the volume's index: Pastor, Virgo, Festum …), "sollemnitas" (SADV 26-28 Dec: Vespers where
the feast is kept as a solemnity).
"""
from __future__ import annotations

import re

from lh.model.canon import fold

MONTHS = {"ianuarii": 1, "februarii": 2, "martii": 3, "aprilis": 4, "maii": 5, "iunii": 6, "iulii": 7,
          "augusti": 8, "septembris": 9, "octobris": 10, "novembris": 11, "decembris": 12}
MONTH_NAMES = {"IANUARIUS": 1, "FEBRUARIUS": 2, "MARTIUS": 3, "APRILIS": 4, "MAIUS": 5, "IUNIUS": 6, "IULIUS": 7,
               "AUGUSTUS": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12}
DATE_RE = re.compile(r"^(Eodem )?[Dd]ie (\d{1,2}) ([a-z]+)$")

# printed rank line -> (rank, precedence in the GILH table of liturgical days)
RANKS = {
    "Sollemnitas": ("solemnity", 3),
    "Festum": ("feast", 7),
    "Memoria": ("memorial", 10),
    "Memoria ad libitum": ("optional_memorial", 12),
    "Pro commemoratione": ("commemoration", 12),
}
NO_RANK = ("optional_memorial", 12)
SMALL_WORDS = {"ET", "DE", "A", "AC", "IN", "DEI", "AB"}


def classify_lines(lines) -> None:
    """L2 hook (called by lh/extract/lines.py for this source): Sanctis date lines start a day."""
    for L in lines:
        if L.kind == "subhour" and DATE_RE.match(L.text):
            L.kind = "day"


def split_day(day: str) -> tuple[int, int, str, bool]:
    """'Die 24 aprilis / S. FIDELIS … ET / MARTYRIS' -> (4, 24, 'S. FIDELIS … ET MARTYRIS', eodem=False)."""
    parts = day.split(" / ")
    m = DATE_RE.match(parts[0])
    if not m or m.group(3) not in MONTHS:
        raise ValueError(f"Sanctis day without a date line: {day!r}")
    return MONTHS[m.group(3)], int(m.group(2)), " ".join(parts[1:]).strip(), bool(m.group(1))


def title_slug(title: str) -> str:
    """Folded title up to its first comma, without S./SS./IN: 'S. AGATHÆ, VIRGINIS…' -> 'agathae'; two saints
    named around their titles keep both names: 'SS. CYRILLI, MONACHI, ET METHODII, EPISCOPI' -> 'cyrilli-et-methodii'."""
    head = title.split(",")[0]
    m = re.match(r"^SS\. ([^ ,]+), [^,]+, ET ([^ ,]+)", title)
    if m:
        head = f"{m.group(1)} ET {m.group(2)}"
    words = [w for w in re.findall(r"[a-z0-9]+", fold(head)) if w not in ("s", "ss")]
    if words and words[0] == "in":
        words = words[1:]
    return "-".join(words[:6]) or "x"


def nice_title(title: str) -> str:
    """'S. GREGORII VII, PAPÆ' -> 'S. Gregorii VII, Papæ' (roman numerals and small words kept)."""
    out = []
    for i, w in enumerate(title.split(" ")):
        core = w.strip(",.;:")
        if re.fullmatch(r"[IVXL]+", core) and i > 0 or w in ("S.", "SS."):
            out.append(w)
        elif core in SMALL_WORDS and i > 0:
            out.append(w.lower())
        else:
            out.append(w[:1] + w[1:].lower())
    return " ".join(out)


def rank_of(extra: list[str] | None) -> tuple[str, int]:
    for t in extra or []:
        if t.strip() in RANKS:
            return RANKS[t.strip()]
    return NO_RANK


def sanct_day_info(section: str, day: str, extra: list[str] | None = None, special: dict | None = None) -> dict:
    """Day record for a Sanctis day. `special` maps 'MM-DD' to a fixed record (temporale key) for days that the
    Proper of Time also prints."""
    mm, dd, title, _ = split_day(day)
    mmdd = f"{mm:02d}-{dd:02d}"
    rank, prec = rank_of(extra)
    if special and mmdd in special:
        info = dict(special[mmdd])
    else:
        info = {"key": f"SANCT.{mmdd}.{title_slug(title)}", "season": "SANCT", "week": None, "weekday": None,
                "psalter_week": None, "title": nice_title(title), "rank": rank, "precedence": prec}
    if rank == "commemoration":
        info["copy"] = "commemoratio"
    elif any(t.startswith("Omnia de die, præter sequentia") for t in extra or []):
        info["copy"] = "propria"              # only the proper parts are printed (SADV 180, Holy Name)
    return info


# --------------------------------------------------------------------------------------------- structure (GILH)

# GILH 239: in Lent, 17-24 Dec and the Christmas octave a memorial becomes a commemoration — Office of Readings:
# the saint's (hagiographical) reading with its responsory and the prayer; Lauds and Vespers: the antiphon (the
# saint's prayer is the one printed at the Office of Readings; SADV prints it again at each hour)
COMMEMORATION = {"OR": ["LECT2", "RESP2", "ORATIO"], "LAUDS": ["ANT"], "VESPERS": ["ANT"]}
# "Omnia de die, præter sequentia": the proper parts only
PROPRIA = {"OR": ["LECT2", "RESP2", "ORATIO"], "LAUDS": ["GOSPEL_ANT", "GOSPEL_CANT", "ORATIO", "CONCLUSION"],
           "VESPERS": ["GOSPEL_ANT", "GOSPEL_CANT", "ORATIO", "CONCLUSION"]}


def required_slots(day_key: str, hour: str, copy: str | None, default: list[str]) -> list[str]:
    """Structure-check hook (lh/verify/checks.py): slots a printed hour of this form must contain."""
    if copy == "commemoratio":
        return COMMEMORATION.get(hour, [])
    if copy == "propria":
        return PROPRIA.get(hour, [])
    return default


# --------------------------------------------------------------------------------------------- volume index

INDEX_CODES = {"CP1": "COMPLINE1", "INV": "INV", "OL": "OR", "LD": "LAUDS", "HM": "MIDDAY", "VP": "VESPERS",
               "VP2": "V2", "CP2": "COMPLINE"}
CODES_RE = re.compile(r"^(?:(.+?) )??((?:(?:CP1|INV|OL|LD|HM|VP2|VP|CP2)(?: |$))+)$")


def read_index(source: str) -> list[dict]:
    """Entries of a Sanctis volume's own index (pages after 'Index' up to the first divider):
    '5 S. Agathæ, Virginis et Martyris' then optional code lines 'OL LD HM VP' / 'Pastor OL LD VP' (an ALTERA
    office with that label) / 'CP1 INV OL LD HM VP2 CP2'. Returns [{mmdd, n, title, label, hours}] where n is the
    entry's ordinal among the entries of that date and hours is None when no code line is printed."""
    from lh.extract.spans import open_l1
    from lh.sources import plugin
    p0, p1 = next((a, b) for a, b, why in plugin(source).NON_CONTENT if "index" in why)
    l1 = open_l1(source)
    rows = l1.execute("SELECT page, text FROM line WHERE page BETWEEN ? AND ? ORDER BY id", (p0, p1)).fetchall()
    l1.close()
    out: list[dict] = []
    month, seen = None, {}
    for page, text in rows:
        t = re.sub(r"\s+", " ", text).strip()
        if t.upper() in MONTH_NAMES and page > p0:      # p0 lists the months themselves
            month = MONTH_NAMES[t.upper()]
            continue
        if month is None:
            continue
        m = re.match(r"^(\d{1,2}) (.+)$", t)
        if m:
            mmdd = f"{month:02d}-{int(m.group(1)):02d}"
            seen[mmdd] = seen.get(mmdd, 0) + 1
            out.append({"mmdd": mmdd, "n": seen[mmdd], "title": m.group(2), "label": None, "hours": None})
            continue
        m = CODES_RE.match(t)
        if m and out:
            hours = {INDEX_CODES[c] for c in m.group(2).split()}
            if "COMPLINE1" in hours:
                hours.add("V1")              # the date link itself leads to I Vespers
            label = m.group(1)
            e = out[-1]
            if label or e["hours"] is not None:  # a second code line = an alternative (ALTERA) office
                out.append({**e, "label": label, "hours": hours})
            else:
                e["hours"] = hours
    return out


def check_index(con, source: str, record) -> dict:
    """Index-check hook (lh/verify/checks.py): every entry of the volume's index must be a parsed day, with the
    hours its code line lists (an entry without a code line — commemorations, 26-28 Dec — only has to exist).
    Hours of a day are matched by date and by the entry's ordinal on that date ("Eodem die …"); ALTERA entries by
    their label. Index titles that differ from the printed titles are recorded as `index_title` notes."""
    printings: dict[tuple, set] = {}
    order: dict[str, list] = {}
    titles: dict[tuple, str] = {}
    for key, hour, copy, title, page in con.execute(
            "SELECT day_key, hour, copy, day_title, page_start FROM hour_instance WHERE source=? AND day_title LIKE "
            "'%ie %' ORDER BY page_start", (source,)):
        mm, dd, t, _ = split_day(title)
        mmdd = f"{mm:02d}-{dd:02d}"
        if key not in order.setdefault(mmdd, []):
            order[mmdd].append(key)
        n = order[mmdd].index(key) + 1
        label = copy[len("altera "):] if copy and copy.startswith("altera ") else None
        printings.setdefault((mmdd, n, label), set()).add(hour)
        titles.setdefault((mmdd, n), t)
    from lh.sources import plugin
    errata = getattr(plugin(source), "INDEX_ERRATA", {})     # reviewed index errors: {"MM-DD #n": reason}
    entries = read_index(source)
    mism = []
    for e in entries:
        got = printings.get((e["mmdd"], e["n"], e["label"]))
        exp = e["hours"]
        entry = f"{e['mmdd']} #{e['n']}" + (f" ({e['label']})" if e["label"] else "")
        subj = f"{source} {entry}"
        if got is not None and exp is not None and "OR" in exp:
            exp = exp | {"INV"} if "INV" in got else exp     # the index omits INV when it lists OL
        if got is None or (exp is not None and exp != got):
            missing, unexpected = sorted((exp or {"(day)"}) - (got or set())), sorted((got or set()) - (exp or got or set()))
            detail = {"title": e["title"], "missing": missing, "unexpected": unexpected}
            if entry in errata:
                record(con, "index", subj, "note", {**detail, "erratum": errata[entry]})
                continue
            mism.append((subj, missing, unexpected))
            record(con, "index", subj, "fail", detail)
        t = titles.get((e["mmdd"], e["n"]), "")
        if t and fold(t).replace(" ", "") != fold(e["title"]).replace(" ", "") and not e["label"]:
            record(con, "index_title", subj, "note", {"index": e["title"], "printed": t})
    record(con, "index", source, "pass" if not mism else "fail", f"{len(entries) - len(mism)}/{len(entries)} entries match")
    return {"days_in_index": len(entries), "mismatches": mism[:20], "n_mismatch": len(mism)}
