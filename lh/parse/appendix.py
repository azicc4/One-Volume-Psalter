"""Parse the unoutlined appendices at the end of each temporale PDF:

  ALIA EX ORDINARIO  — invitatory psalms, Hora media hymns, complementary psalmody, Sunday-week-I Ps 117 (118),
                       Compline hymns, dismissals (DIMISSIO, per hour), Marian antiphons
  ALIA EX PROPRIO …  — optional hymns (Dies iræ, Salve dies …), Saturday memorial of the BVM (a full office)

Each 16.6pt chapter heading (or a bare "Ad Invitatorium") starts a chapter with day key ORD.<chapter> or
PROP.<chapter>. A chapter that contains hour headers is split into real hours (OR, LAUDS, …) of that day;
otherwise the whole chapter is one pseudo-hour with code APPX. All are parsed with the normal HourParser.
"""
from __future__ import annotations

from lh.extract.lines import HOUR_HEADERS, Line
from lh.model.canon import slug
from lh.parse.hour import Hour, parse_hour

ORD_KEYS = {
    "Ad Invitatorium": "ORD.INVITATORY",
    "Hymni ad Tertiam, Sextam et Nonam seu ad Horam mediam": "ORD.MIDDAY_HYMNS",
    "PSALMODIA COMPLEMENTARIS / PRO TERTIA, SEXTA ET NONA": "ORD.COMPLEMENTARY",
    "PSALMI DOMINICÆ HEBDOMADÆ I": "ORD.SUNDAY_WK1_PSALMS",
    "Hymni ad Completorium": "ORD.COMPLINE_HYMNS",
    "DIMISSIO": "ORD.DISMISSAL",
    "Antiphonæ finales de Beata Maria Virgine": "ORD.MARIAN",
    "ANTIPHONÆ FINALES DE BEATA MARIA VIRGINE": "ORD.MARIAN",
}
# second printings of the same chapter: Hora media alternates ("Vel alter") and complementary psalms without antiphons
SECOND = {"ORD.MIDDAY_HYMNS": "ORD.MIDDAY_HYMNS_ALT", "ORD.COMPLEMENTARY": "ORD.COMPLEMENTARY_NO_ANT"}


def chapters(lines: list[Line]) -> list[dict]:
    out: list[dict] = []
    part = ""
    for L in lines:
        if L.kind == "week":
            part = "ORD" if "ORDINARIO" in L.text else "PROP"
            continue
        starts = L.kind == "day" or L.text.upper() == "ANTIPHONÆ FINALES DE BEATA MARIA VIRGINE" or (
            L.kind == "hour" and L.text == "Ad Invitatorium" and part == "ORD"
                                      and (not out or out[-1]["title"] != "Ad Invitatorium" or len(out[-1]["lines"]) > 1))
        if starts and out and out[-1]["lines"] and out[-1]["lines"][-1].kind == "day" and L.kind == "day":
            out[-1]["title"] += f" / {L.text}"        # two-line chapter heading
            out[-1]["head"].append(L)
            continue
        if starts:
            out.append({"part": part, "title": L.text, "head": [L], "lines": [L]})
            continue
        if out:
            out[-1]["lines"].append(L)
    return out


def split_appendices(lines: list[Line]) -> list[Hour]:
    hours: list[Hour] = []
    seen: dict[str, int] = {}
    for ch in chapters(lines):
        base = ORD_KEYS.get(ch["title"]) or f"{ch['part']}.{slug(ch['title'], 5).upper().replace('-', '_')}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        key = base if n == 0 else SECOND.get(base, f"{base}.{n + 1}")
        section = f"ALIA EX {'ORDINARIO' if ch['part'] == 'ORD' else 'PROPRIO'}"
        body = [L for L in ch["lines"] if L not in ch["head"]]
        # chapter heading line(s) first, so the parser skips/marks them
        hour_idx = [i for i, L in enumerate(body) if L.kind == "hour"]
        if ch["title"] == "Ad Invitatorium" or not hour_idx:
            h = Hour("", section, ch["title"], [], ch["title"], "APPX", lines=ch["head"] + body)
            h.day_key, h.day_title = key, ch["title"]
            hours.append(h)
            continue
        if hour_idx[0] > 0:            # chapter preface before the first hour
            h = Hour("", section, ch["title"], [], ch["title"], "APPX", lines=ch["head"] + body[:hour_idx[0]])
            h.day_key, h.day_title = key, ch["title"]
            hours.append(h)
        for j, i in enumerate(hour_idx):
            end = hour_idx[j + 1] if j + 1 < len(hour_idx) else len(body)
            hl = body[i]
            h = Hour("", section, ch["title"], [], hl.text, HOUR_HEADERS[hl.text], lines=body[i:end])
            h.day_key, h.day_title = key, ch["title"]
            hours.append(h)
    return hours


def parse_appendices(lines: list[Line], pdf: str) -> list[Hour]:
    hours = split_appendices(lines)
    for h in hours:
        h.pdf = pdf
        parse_hour(h)
    return hours
