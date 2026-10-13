"""Proper of Saints: shared parsing for the four Sanctis volumes SPA, SP, SQ, SADV (workstreams WS4a + WS4b).

Layout of a Sanctis volume (docs/source-pdf-format.md):

  IANUARIUS                                  20.2pt month heading                     (kind week)
  Die 13 ianuarii | Eodem die 20 ianuarii    14.4 bold date line; once without "Die"  (L2 "subhour" → "day" here)
  S. HILARII, EPISCOPI ET ECCLESIÆ DOCTORIS  16.6 bold title, may wrap                (kind day; Assumption: 14.4)
  Memoria | Festum | Sollemnitas |           14.4 italic red rank line; none = optional memorial; SQ 14 Feb adds
  Pro commemoratione                         "Vel ubi celebratur ut festum." and a second rank line
  Infra memoria ut martyr, vel altera …      red rubric (+ link to the ALTERA office), optional
  Pictavii natus est …                       biography (prose)
  Ad Invitatorium / Ad Officium lectionis …  hours
  ALTERA                                     alternative offices (Pastor, Virgo, Festum …), labelled in the index only
  ALIA EX ORDINARIO                          appendix (lh/parse/appendix.py)

`classify_lines` (L2 hook) turns the date line, and the Assumption's non-bold title, into `day` lines, so the
standard segmenter joins date and title: hour.day = "Die 13 ianuarii / S. HILARII, …". The rank line, rubrics and
biography are the day's preamble (Hour.day_extra; source_line role day_extra) and reach `sanct_day_info` as `extra`.

Day keys: SANCT.MM-DD.<litcal_key> — the printed date and the Liturgical Calendar API event key (Apache-2.0 data,
`lh fetch` → sources/web/litcal/), e.g. SANCT.01-13.StHilaryPoitiers, SANCT.03-19.StJoseph;
SANCT.MOVABLE.ImmaculateHeart. Rank and precedence are LitCal's current grade, the same for every volume that prints
the day; what a volume prints is recorded per printing:
  hour_instance.copy  "commemoratio" (Lent, 17-24 Dec, Christmas octave: OR reading + responsory + prayer, Lauds /
                      Vespers antiphon), "propria" (proper parts only), "altera <label>" (ALTERA offices, label from
                      the volume's index: Pastor, Virgo, Festum …), "sollemnitas" (SADV 26-28 Dec Vespers)
  day.extra           printed date, title, rank line, rubrics, biography (`day_meta`; ALTERA under "copies"), LitCal
                      key, grade and decrees
A celebration without a LitCal match falls back to SANCT.MM-DD.<title slug> with its printed rank (day.extra
"litcal": null; none at present — Escrivá, missing from the data, has a hand-made event in lh/sources/spa.py). Days
the Proper of Time also prints keep its key (plug-in `SPECIAL`: SOL.IMMACULATE_CONCEPTION, CHR.DEC26-28).

Plug-in hooks provided here: classify_lines, day_info (via sanct_day_info), day_meta, required_slots, check_index.
"""
from __future__ import annotations

import functools
import json
import re
import unicodedata

from lh.config import SOURCES_WEB
from lh.model.canon import fold

MONTHS = {"ianuarii": 1, "februarii": 2, "martii": 3, "aprilis": 4, "maii": 5, "iunii": 6, "iulii": 7,
          "augusti": 8, "septembris": 9, "octobris": 10, "novembris": 11, "decembris": 12}
MONTH_NAMES = {"IANUARIUS": 1, "FEBRUARIUS": 2, "MARTIUS": 3, "APRILIS": 4, "MAIUS": 5, "IUNIUS": 6, "IULIUS": 7,
               "AUGUSTUS": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12}
# "Die 13 ianuarii", "Eodem die 20 ianuarii", and twice without "Die" ("16 septembris", SPA 1379, 1483)
DATE_RE = re.compile(r"^(?:(Eodem )?[Dd]ie )?(\d{1,2}) (" + "|".join(MONTHS) + r")$")
# movable celebrations printed in a Sanctis volume (date line → LitCal key)
MOVABLE = {"Sabbato post dominicam II post Pentecosten": "ImmaculateHeart"}

# printed rank line -> (rank, precedence): used for the form of a printing, and for days without a LitCal match
RANKS = {
    "Sollemnitas": ("solemnity", 3),
    "Festum": ("feast", 7),
    "Memoria": ("memorial", 10),
    "Memoria ad libitum": ("optional_memorial", 12),
    "Pro commemoratione": ("commemoration", 12),
}
NO_RANK = ("optional_memorial", 12)
# LitCal grade -> (rank, precedence in the Table of Liturgical Days, UNLY 59; docs/loth-model.md §4)
GRADES = {1: ("commemoration", 12), 2: ("optional_memorial", 12), 3: ("memorial", 10), 4: ("feast", 7),
          5: ("feast_lord", 5), 6: ("solemnity", 3), 7: ("solemnity", 2)}
SPECIAL_RANK = {"AllSouls": ("all_souls", 3)}       # ranks with the solemnities, but the office is of the dead
SMALL_WORDS = {"ET", "DE", "A", "AC", "IN", "DEI", "AB"}


# --------------------------------------------------------------------------------------------- L2 hook

def is_date(text: str) -> bool:
    return bool(DATE_RE.match(text)) or text in MOVABLE


def classify_lines(lines) -> None:
    """L2 hook (lh/extract/lines.py): a Sanctis date line starts a day; so does the Assumption's title, set in 14.4
    regular instead of 16.6 bold (SPA 1111) right after its date line."""
    prev = None
    for L in lines:
        if L.kind == "subhour" and is_date(L.text):
            L.kind = "day"
        elif (prev is not None and prev.kind == "day" and is_date(prev.text) and L.kind == "text" and L.x0 > 100
              and L.text.isupper()):
            L.kind = "day"
        prev = L


# --------------------------------------------------------------------------------------------- day header

def split_day(day: str) -> tuple[int | None, int | None, str, bool]:
    """'Die 24 aprilis / S. FIDELIS … ET / MARTYRIS' -> (4, 24, 'S. FIDELIS … ET MARTYRIS', eodem=False);
    the movable 'Sabbato post dominicam II post Pentecosten / …' -> (None, None, title, False)."""
    parts = day.split(" / ")
    title = " ".join(parts[1:]).strip()
    if parts[0] in MOVABLE:
        return None, None, title, False
    m = DATE_RE.match(parts[0])
    if not m:
        raise ValueError(f"Sanctis day without a date line: {day!r}")
    return MONTHS[m.group(3)], int(m.group(2)), title, bool(m.group(1))


def mmdd_of(month: int | None, dd: int | None) -> str:
    return f"{month:02d}-{dd:02d}" if month else "MOVABLE"


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
    """Printed rank line of a day's preamble (the first one: SQ 14 Feb prints a second, 'Memoria', for the feast)."""
    for t in extra or []:
        if t.strip() in RANKS:
            return RANKS[t.strip()]
    return NO_RANK


def printed_rank_line(extra: list[str] | None) -> str | None:
    return next((t.strip() for t in extra or [] if t.strip() in RANKS), None)


# --------------------------------------------------------------------------------------------- calendar (LitCal)

def _load(name: str):
    p = SOURCES_WEB / "litcal" / name
    if not p.exists():
        raise SystemExit(f"{p} is missing: run `python -m lh fetch` (Liturgical Calendar API data for the Sanctis "
                         f"day keys), or point LH_WEB_DIR at a checkout that has sources/web/litcal/")
    return json.loads(p.read_text(encoding="utf-8"))


def have_calendar() -> bool:
    return (SOURCES_WEB / "litcal" / "propriumdesanctis_1970.json").exists()


@functools.lru_cache(maxsize=None)
def calendar() -> dict[str, dict]:
    """The General Roman Calendar's celebrations by LitCal event key, as of the newest decree in the cached data:
    {key: {key, month, day, grade, name_la, name_en, edition, changes: [decree…], movable}}."""
    events: dict[str, dict] = {}
    for ed in ("1970", "2002", "2008"):
        la, en = _load(f"propriumdesanctis_{ed}.la.json"), _load(f"propriumdesanctis_{ed}.en.json")
        for e in _load(f"propriumdesanctis_{ed}.json"):
            if e.get("calendar", "GENERAL ROMAN") != "GENERAL ROMAN":
                continue
            k = e["event_key"]
            events[k] = {"key": k, "month": e["month"], "day": e["day"], "grade": e["grade"],
                         "name_la": la.get(k, ""), "name_en": en.get(k, ""), "edition": ed, "changes": [],
                         "movable": False}
    la, en = _load("propriumdetempore.la.json"), _load("propriumdetempore.en.json")
    for e in _load("propriumdetempore.json"):
        if e["event_key"] in MOVABLE.values():
            k = e["event_key"]
            events[k] = {"key": k, "month": None, "day": None, "grade": e["grade"], "name_la": la.get(k, ""),
                         "name_en": en.get(k, ""), "edition": "1970", "changes": [], "movable": True}
    la, en = _load("decrees.la.json"), _load("decrees.en.json")
    for d in sorted(_load("decrees.json"), key=lambda d: d["decree_date"]):
        ev, meta = d["liturgical_event"], d["metadata"]
        k, action = ev["event_key"], meta["action"]
        change = {"date": d["decree_date"], "action": action, "since_year": meta.get("since_year"),
                  "property": meta.get("property")}
        if action == "createNew":
            events[k] = {"key": k, "month": ev.get("month"), "day": ev.get("day"), "grade": ev["grade"],
                         "name_la": la.get(k, ""), "name_en": en.get(k, ""), "edition": f"decree {d['decree_date']}",
                         "changes": [], "movable": ev.get("type") == "mobile"}
            change["grade"] = ev["grade"]
        elif k in events:
            if action == "setProperty" and meta.get("property") == "grade":
                change["old_grade"], change["grade"] = events[k]["grade"], ev["grade"]
                events[k]["grade"] = ev["grade"]
            elif la.get(k):                                   # name change, new doctor of the Church
                change["old_name"] = events[k]["name_la"]
                events[k]["name_la"] = la[k]
                events[k]["name_en"] = en.get(k, events[k]["name_en"])
        else:
            continue
        events[k]["changes"].append(change)
    return events


def _norm(s: str) -> str:
    s = s.replace("’", "'")
    s = "".join(c for c in unicodedata.normalize("NFKD", fold(s)) if not unicodedata.combining(c))
    s = re.sub(r"\bb\. ?m\. ?v\.", "beatae mariae virginis", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(sancti|sanctae|sanctorum|sanctarum|ss|s|in)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _score(a: str, b: str) -> float:
    from rapidfuzz import fuzz
    return fuzz.token_set_ratio(_norm(a), _norm(b))


def match(month: int | None, day: int | None, title: str, events: dict | None = None) -> tuple[dict | None, float]:
    """The LitCal celebration for a printed date + title, or (None, best score). `events` maps
    (month, day, title-substring) to a hand-made event for celebrations missing from the LitCal data."""
    cal = calendar()
    for (m, d, sub), ev in (events or {}).items():
        if m == month and d == day and sub in title:
            return ev, 100.0
    if month is None:
        cands = [e for e in cal.values() if e["movable"]]
    else:
        cands = [e for e in cal.values() if e["month"] == month and e["day"] == day]
    best = max(cands, key=lambda e: _score(title, e["name_la"]), default=None)
    if best is not None and _score(title, best["name_la"]) >= 60:
        return best, _score(title, best["name_la"])
    # not on that date: a celebration moved to another day since the data's edition (Jane Frances de Chantal)
    best = max(cal.values(), key=lambda e: _score(title, e["name_la"]))
    sc = _score(title, best["name_la"])
    return (best, sc) if sc >= 85 else (None, sc)


def sanct_day_info(section: str, day: str, extra: list[str] | None = None, special: dict | None = None,
                   events: dict | None = None) -> dict:
    """Day record for a Sanctis day. `special` maps 'MM-DD' to a fixed record (temporale key) for days that the
    Proper of Time also prints; `events` adds hand-made calendar entries (see `match`)."""
    month, dd, title, _ = split_day(day)
    mmdd = mmdd_of(month, dd)
    if special and mmdd in special:
        info = dict(special[mmdd])
    else:
        ev, _ = match(month, dd, title, events)
        if ev is not None:
            rank, prec = SPECIAL_RANK.get(ev["key"]) or GRADES[ev["grade"]]
            # keyed by the printed date (a celebration the data has on another date is reported, not moved)
            info = {"key": f"SANCT.{mmdd}.{ev['key']}", "title": ev["name_en"] or ev["name_la"]}
        else:
            rank, prec = rank_of(extra)
            info = {"key": f"SANCT.{mmdd}.{title_slug(title)}", "title": nice_title(title)}
        info.update({"season": "SANCT", "week": None, "weekday": None, "psalter_week": None, "rank": rank,
                     "precedence": prec})
    if printed_rank_line(extra) == "Pro commemoratione":
        info["copy"] = "commemoratio"
    elif any(t.startswith("Omnia de die, præter sequentia") for t in extra or []):
        info["copy"] = "propria"              # only the proper parts are printed (SADV 180, Holy Name)
    return info


# --------------------------------------------------------------------------------------------- day preamble

def preamble(hour) -> dict:
    """Printed date, title, rank line, rubrics and biography of the day an hour belongs to."""
    date, _, title = hour.day.partition(" / ")
    rank_line, rubrics, bio = None, [], []
    for t in hour.day_extra:
        if rank_line is None and not bio and not rubrics and t in RANKS:
            rank_line = t
        elif not bio and (t.startswith("Infra ") or t.startswith("Quando ") or t.startswith("Vel ubi")
                          or t in RANKS or rubrics and not t[:1].isupper()):
            rubrics.append(t)
        else:
            bio.append(t)
    out = {"printed_date": date, "printed_title": title.replace(" / ", " "), "printed_rank": rank_line,
           "printed_rank_code": RANKS.get(rank_line, NO_RANK)[0]}
    if rubrics:
        out["rubrics"] = " ".join(rubrics)
    if bio:
        out["bio"] = " ".join(bio)
    return out


def day_meta(info: dict, hour, copy: str | None, events: dict | None = None) -> None:
    """Plug-in hook (lh/model/build.py): record the printed preamble on the day (day.extra) — the main printing's at
    the top level, other printings' (ALTERA, commemoratio, another volume) under extra["copies"][<source> <copy>]."""
    x = info.setdefault("extra", {})
    month, dd, title, _ = split_day(hour.day)
    if "litcal" not in x:
        ev, score = match(month, dd, title, events)
        x["litcal"] = ev["key"] if ev else None
        x["match_score"] = round(score)
        if ev:
            x.update({"litcal_grade": ev["grade"], "name_la": ev["name_la"], "litcal_edition": ev["edition"]})
            if ev["changes"]:
                x["litcal_changes"] = ev["changes"]
    pre = preamble(hour)
    src = getattr(hour, "pdf", "")
    if "printed_date" not in x and not copy:
        x["source"] = src
        x.update(pre)
    else:
        x.setdefault("copies", {}).setdefault(" ".join(t for t in (src, copy) if t), pre)


# --------------------------------------------------------------------------------------------- structure (GILH)

# GILH 239: in Lent, 17-24 Dec and the Christmas octave a memorial becomes a commemoration — Office of Readings:
# the saint's (hagiographical) reading with its responsory and the prayer; Lauds and Vespers: the antiphon (the
# saint's prayer is the one printed at the Office of Readings; SADV prints it again at each hour)
COMMEMORATION = {"OR": ["LECT2", "RESP2", "ORATIO"], "LAUDS": ["ANT"], "VESPERS": ["ANT"]}
# "Omnia de die, præter sequentia": the proper parts only
PROPRIA = {"OR": ["LECT2", "RESP2", "ORATIO"], "LAUDS": ["GOSPEL_ANT", "GOSPEL_CANT", "ORATIO", "CONCLUSION"],
           "VESPERS": ["GOSPEL_ANT", "GOSPEL_CANT", "ORATIO", "CONCLUSION"]}


def required_slots(day_key: str, hour: str, copy: str | None, default: list[str]) -> list[str]:
    """Structure-check hook (lh/verify/checks.py): slots a printed hour of this form must contain. `default` already
    follows the day's rank (memorials: psalmody and first reading «de feria», RANK_REQUIRED in checks.py)."""
    if copy == "commemoratio":
        return COMMEMORATION.get(hour, [])
    if copy == "propria":
        return PROPRIA.get(hour, [])
    return default


# --------------------------------------------------------------------------------------------- volume index

INDEX_CODES = {"CP1": "COMPLINE1", "INV": "INV", "OL": "OR", "LD": "LAUDS", "HM": "MIDDAY", "VP": "VESPERS",
               "VP2": "V2", "CP2": "COMPLINE", "CP": "COMPLINE"}


def _index_hours(t: str) -> tuple[str | None, list[str]] | None:
    """'Pastor OL LD VP' → ('Pastor', ['OL', 'LD', 'VP']); 'OL LD VP' → (None, […]); other text → None."""
    words = t.split()
    n = len(words)
    while n and words[n - 1] in INDEX_CODES:
        n -= 1
    if n == len(words):
        return None
    return (" ".join(words[:n]) or None), words[n:]


@functools.lru_cache(maxsize=None)
def read_index(source: str) -> tuple[dict, ...]:
    """Entries of a Sanctis volume's own index (its NON_CONTENT "index" pages): '5 S. Agathæ, Virginis et Martyris'
    (link → date page) then optional code lines 'OL LD HM VP' / 'Pastor OL LD VP' (an ALTERA office with that label,
    link → its page) / 'CP1 INV OL LD HM VP2 CP2'. Returns ({mmdd, n, title, label, hours, page}, …): n is the
    entry's ordinal among the entries of that date, hours is None when no code line is printed."""
    from lh.extract.spans import open_l1
    from lh.sources import plugin
    p0, p1 = next((a, b) for a, b, why in plugin(source).NON_CONTENT if "index" in why)
    l1 = open_l1(source)
    rows = l1.execute("SELECT page, x0, text, link_page FROM line WHERE page BETWEEN ? AND ? ORDER BY id",
                      (p0, p1)).fetchall()
    l1.close()
    out: list[dict] = []
    month, seen = None, {}
    for page, x0, text, link in rows:
        t = re.sub(r"\s+", " ", text).strip()
        if t.upper() in MONTH_NAMES and page > p0:      # p0 lists the months themselves
            month = MONTH_NAMES[t.upper()]
            continue
        if month is None:
            continue
        ih = _index_hours(t)
        if ih and out and x0 > 80:
            label, codes = ih
            hours = {INDEX_CODES[c] for c in codes}
            if "OR" in hours:
                hours.add("INV")
            if "COMPLINE1" in hours:
                hours.add("V1")              # the date link itself leads to I Vespers
                if "VESPERS" in hours:      # Exaltation of the Cross: index "VP", page "Ad II Vesperas" (SPA 1336)
                    hours = (hours - {"VESPERS"}) | {"V2"}
            e = out[-1]
            if label or e["hours"] is not None:  # a second code line = an alternative (ALTERA) office
                out.append({**e, "label": label, "hours": hours, "page": link})
            else:
                e["hours"] = hours
            continue
        m = re.match(r"^(\d{1,2}) (.+)$", t)
        if m:
            mmdd = f"{month:02d}-{int(m.group(1)):02d}"
        elif link and x0 < 80:
            mmdd = "MOVABLE"                 # Immaculate Heart: no day number (SPA 9)
        else:
            if out and x0 < 90 and not link:
                out[-1]["title"] += " " + t  # wrapped index title ("… et Sociorum, / Martyrum")
            continue
        seen[mmdd] = seen.get(mmdd, 0) + 1
        out.append({"mmdd": mmdd, "n": seen[mmdd], "title": m.group(2) if m else t, "label": None, "hours": None,
                    "page": link})
    return tuple(out)


def altera_copies(source: str, last_page: int) -> list[tuple[int, int, str]]:
    """COPIES for a volume's ALTERA section, from its index: [(first page, last page, "altera <label>")]."""
    starts = sorted((e["page"], f"altera {e['label']}") for e in read_index(source) if e["label"])
    return [(p, (starts[i + 1][0] - 1) if i + 1 < len(starts) else last_page, lab)
            for i, (p, lab) in enumerate(starts)]


def check_index(con, source: str, record) -> dict:
    """Index-check hook (lh/verify/checks.py): every entry of the volume's index must be a parsed day, with the
    hours its code line lists (an entry without a code line — commemorations, 26-28 Dec — only has to exist), and
    every printed office must be in the index. Hours of a day are matched by date and by the entry's ordinal on that
    date ("Eodem die …"); ALTERA entries by their label. Index titles that differ from the printed titles are
    recorded as `index_title` notes; reviewed index errors (plug-in INDEX_ERRATA) as `index` notes."""
    printings: dict[tuple, set] = {}
    order: dict[str, list] = {}
    titles: dict[tuple, str] = {}
    for key, hour, copy, title, page in con.execute(
            "SELECT day_key, hour, copy, day_title, page_start FROM hour_instance WHERE source=? ORDER BY page_start",
            (source,)):
        try:
            mm, dd, t, _ = split_day(title)
        except ValueError:
            continue                          # appendix chapters
        mmdd = mmdd_of(mm, dd)
        if key not in order.setdefault(mmdd, []):
            order[mmdd].append(key)
        n = order[mmdd].index(key) + 1
        label = copy[len("altera "):] if copy and copy.startswith("altera ") else None
        printings.setdefault((mmdd, n, label), set()).add(hour)
        titles.setdefault((mmdd, n), t)
    from lh.sources import plugin
    errata = getattr(plugin(source), "INDEX_ERRATA", {})     # reviewed index errors: {"MM-DD #n": reason}
    entries = read_index(source)
    mism, matched = [], set()
    for e in entries:
        k = (e["mmdd"], e["n"], e["label"])
        got = printings.get(k)
        matched.add(k)
        exp = e["hours"]
        entry = f"{e['mmdd']} #{e['n']}" + (f" ({e['label']})" if e["label"] else "")
        subj = f"{source} {entry}"
        if got is not None and exp is not None and "OR" in exp and "INV" not in got:
            exp = exp - {"INV"}                # some volumes print no Invitatory where the index lists OL
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
    for k in sorted(set(printings) - matched):
        subj = f"{source} {k[0]} #{k[1]}" + (f" ({k[2]})" if k[2] else "")
        mism.append((subj, [], sorted(printings[k])))
        record(con, "index", subj, "fail", {"not in the volume index": sorted(printings[k])})
    n = len(entries)
    record(con, "index", source, "pass" if not mism else "fail", f"{n - len(mism)}/{n} entries match")
    return {"days_in_index": n, "mismatches": mism[:20], "n_mismatch": len(mism)}


# --------------------------------------------------------------------------------------------- calendar changes

def calendar_changes(since_year: int) -> list[dict]:
    """Decrees that took effect after `since_year`, oldest first (for the TODO.md §3 review list)."""
    out = []
    for ev in calendar().values():
        for ch in ev["changes"]:
            if (ch.get("since_year") or 0) > since_year or ch["date"] > f"{since_year}-12-31":
                out.append({"key": ev["key"], "month": ev["month"], "day": ev["day"], "grade": ev["grade"],
                            "name_la": ev["name_la"], **ch})
    return sorted(out, key=lambda c: c["date"])
