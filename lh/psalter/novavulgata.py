"""Nova Vulgata psalter (vatican.va) → fill psalm verses that the Liturgia Horarum never prints.

The LH psalter text IS the Nova Vulgata (with accents and * † pointing added). Verses the LH omits — the three
"cursing" psalms 58, 83, 109, imprecatory verses, superscriptions — are taken from the plain Nova Vulgata text and
stored with source='NV', used=0 so the book prints them in smaller type. Anchors are Hebrew-numbered ("PSALMUS 63").
Also cross-checks the computed omissions against Felix Just's Psalter-Omissions table.
"""
from __future__ import annotations

import collections
import html
import re
import sqlite3

from lh.config import DB_PATH, REPORTS, SOURCES_WEB
from lh.psalter.felix import table_rows
from lh.psalter.refs import parse_ref

NV_HTML = SOURCES_WEB / "nova_vulgata" / "psalmorum.html"
INLINE_V = re.compile(r"<v>\(?(\d+)")


def parse_nv() -> dict[int, dict]:
    """{psalm: {"vulg": "41", "verses": [(verse:int, [line markup…], title_only:bool)]}}"""
    s = NV_HTML.read_text(encoding="latin-1")
    out: dict[int, dict] = {}
    parts = re.split(r'<a name="PSALMUS (\d+)"[^>]*>[^<]*</a>', s)
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1]
        body = body.split('<a name="PSALMUS', 1)[0]
        m = re.match(r"\s*(?:</?(?:b|font)[^>]*>\s*)*\(([^)]*)\)", body)
        vulg = m.group(1) if m else ""
        body = body[m.end():] if m else body
        body = re.sub(r'<p align="center">.*', "", body, flags=re.S)        # book divisions (LIBER III …)
        body = re.sub(r"</?(?:font|b|p|a)\b[^>]*>", "", body)
        segs = [html.unescape(x).replace("\xa0", " ").strip() for x in re.split(r"<br\s*/?>", body)]
        verses: list = []
        for seg in segs:
            seg = re.sub(r"\s+", " ", seg).strip()
            if not seg:
                continue
            vm = re.match(r"^(\d+)\s+(.*)$", seg)
            if vm:
                verses.append([int(vm.group(1)), [vm.group(2)]])
                continue
            if not verses:
                continue
            # a verse can begin mid-line: "Exaltant 10 caput, qui circumdant me;" (only the next verse number)
            nxt = verses[-1][0] + 1
            im = re.search(rf"(?:^|\s){nxt}\s", seg)
            if im:
                head, tail = seg[:im.start()].strip(), seg[im.end():].strip()
                if head:
                    verses[-1][1].append(head)
                verses.append([nxt, [tail]])
            else:
                verses[-1][1].append(seg)
        cleaned = []
        for v, lines in verses:
            joined = " ".join(lines)
            rest = re.sub(r"<i>.*?</i>", "", joined)
            title_only = "<i>" in joined and not re.sub(r"[\s.,;:]", "", rest)
            cleaned.append((v, lines, title_only))
        out[num] = {"vulg": vulg, "verses": cleaned}
    return out


SPLIT_VULGATE = {9: "9A", 10: "9B", 114: "113A", 115: "113B", 116: "114–115", 147: "146–147"}


def vulgate_label(num: int, nv: str) -> str:
    """Vulgate number as printed in the book: the LH convention for split psalms, else the Nova Vulgata number."""
    if num in SPLIT_VULGATE:
        return SPLIT_VULGATE[num]
    nv = nv.replace(" ", "")
    return nv if re.fullmatch(r"\d+", nv) else str(num)


def felix_omissions() -> dict[int, set[int]]:
    """{psalm: {omitted verse numbers}} from Felix Just's Psalter-Omissions.html (references only)."""
    out: dict[int, set[int]] = {}
    for cells in table_rows("Psalter-Omissions.html"):
        if len(cells) < 3 or not cells[1].startswith("Ps "):
            continue
        num = int(re.match(r"Ps (\d+)", cells[1]).group(1))
        spec = re.sub(r"^omit (?:final )?vv?\. ", "", cells[2])
        vs: set[int] = set()
        for part in re.split(r",\s*", spec):
            m = re.match(r"^(\d+)([a-c]*)(?:-(\d+))?$", part.strip())
            if m and not m.group(2):
                a, b = int(m.group(1)), int(m.group(3) or m.group(1))
                vs.update(range(a, b + 1))
            elif m:
                vs.add(-int(m.group(1)))    # partial verse omitted (e.g. 3ab) — negative marks "partial"
        out[num] = vs
    for num in (58, 83, 109):
        out[num] = {"ALL"}
    return out


def lh_verse_ints(con, psalm: int) -> set[int]:
    vs: set[int] = set()
    for v, text in con.execute("SELECT verse, text FROM psalm_verse WHERE psalm=? AND source='LH'", (psalm,)):
        if v:
            m = re.match(r"\(?(\d+)", v)
            if m:
                vs.add(int(m.group(1)))
        vs.update(int(x) for x in INLINE_V.findall(text))
    return vs


def fill(db=DB_PATH) -> dict:
    nv = parse_nv()
    con = sqlite3.connect(db)
    con.execute("DELETE FROM psalm_verse WHERE source='NV'")
    report = []
    fj = felix_omissions()
    for num in range(1, 151):
        info = nv.get(num)
        if not info:
            report.append((num, "MISSING IN NOVA VULGATA PAGE", [], [], ""))
            continue
        lh = lh_verse_ints(con, num)
        first_lh = min(lh) if lh else None
        # superscription: italic-only in NV, or any verse before the first verse the LH prints (LH never prints titles)
        verses = [(v, lines, t or (first_lh is not None and v < first_lh)) for v, lines, t in info["verses"]]
        title_vs = [v for v, _, t in verses if t]
        missing = [(v, lines, t) for v, lines, t in verses if v not in lh]
        rows = con.execute("SELECT seq, verse, line, x, text, source, n_copies, n_agree, used FROM psalm_verse WHERE psalm=?",
                           (num,)).fetchall()
        merged = [(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in rows]
        for v, lines, t in missing:
            for k, ln in enumerate(lines):
                merged.append((str(v), k, 0 if k == 0 else 2, ln, "NVT" if t else "NV", 0, 0, 0))

        def key(r):
            m = re.match(r"\(?(\d+)(?:,(\d+))?([a-c]*)", r[0] or "0")
            return (int(m.group(1)), int(m.group(2) or 0), m.group(3), r[1]) if m else (0, 0, "", r[1])
        merged.sort(key=key)
        con.execute("DELETE FROM psalm_verse WHERE psalm=?", (num,))
        con.executemany("INSERT INTO psalm_verse VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [(num, seq, *r[:4], r[4], r[5], r[6], 1 if r[4] == "LH" else 0) for seq, r in enumerate(merged)])
        con.execute("INSERT OR REPLACE INTO psalm (num, vulgate, title, n_verses) VALUES "
                    "(?, ?, (SELECT title FROM psalm WHERE num=?), ?)",
                    (num, vulgate_label(num, info["vulg"]), num, max(v for v, _, _ in verses)))
        omitted_text = sorted(v for v, _, t in missing if not t)
        status = ""
        f = fj.get(num)
        if not lh:
            status = "LH: not printed in parsed sources" + (" (omitted from LOTH — matches Felix)" if f == {"ALL"} else " (pending seasonal volumes)")
        elif omitted_text or f:
            fset = {x for x in (f or set()) if isinstance(x, int) and x > 0}
            status = "matches Felix omission list" if set(omitted_text) == fset else f"Felix omits {sorted(fset) or '—'}"
            partial = sorted(-x for x in (f or set()) if isinstance(x, int) and x < 0)
            if partial:
                status += f"; partial verse(s) {partial} omitted per Felix (not split automatically)"
        report.append((num, info["vulg"], omitted_text, title_vs, status))
    con.commit()
    con.close()
    write_coverage(report)
    return {"psalms": len(report), "with_gaps": sum(1 for r in report if r[2])}


def write_coverage(report) -> None:
    L = ["# Psalter coverage (Liturgia Horarum text vs. Nova Vulgata)", "",
         "Generated by `python -m lh psalter`. For every psalm (Hebrew numbering): verses not printed anywhere in the parsed "
         "LH sources are filled from the Nova Vulgata (vatican.va) and marked *unused* (set smaller in the Psalter). "
         "Superscription-only verses (titles) are listed separately. The last column cross-checks against Felix Just's "
         "list of verses omitted from the four-week psalter.", "",
         "| Ps | Vulg. | Verses not in LH (filled from NV) | Title-only verses | Check |", "|---|---|---|---|---|"]
    for num, vulg, missing, titles, status in report:
        if not missing and not status:
            continue
        ms = ", ".join(map(str, missing)) if len(missing) < 25 else f"{missing[0]}–{missing[-1]} ({len(missing)} verses)"
        L.append(f"| {num} | {vulg} | {ms} | {', '.join(map(str, titles))} | {status} |")
    full = [r[0] for r in report if not r[2] and not r[4]]
    L += ["", f"Psalms fully printed in the parsed LH sources with no gaps: {len(full)}."]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "psalter_coverage.md").write_text("\n".join(L) + "\n", encoding="utf-8")
