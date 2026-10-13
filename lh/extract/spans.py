"""L1: dump every text line of a source PDF (with span styles), its links and its outline.

One SQLite file per PDF in build/l1/<KEY>.sqlite. Deterministic and cacheable: re-run only when the
PDF hash changes. Nothing here interprets liturgy; it only records what is on the page.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time

import pymupdf

from lh.config import L1_DIR, pdf_path

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE line (
    id INTEGER PRIMARY KEY,          -- global reading order within the PDF
    page INTEGER NOT NULL,           -- 1-based page number
    block INTEGER NOT NULL,          -- PyMuPDF block number (stanza / paragraph grouping)
    x0 REAL, y0 REAL, x1 REAL, y1 REAL,
    text TEXT NOT NULL,              -- concatenated span text
    spans TEXT NOT NULL,             -- JSON list of [text, size, color, flags]
    link_page INTEGER                -- 1-based target page if a link overlaps this line
);
CREATE INDEX line_page ON line(page);
CREATE TABLE link (page INTEGER, x0 REAL, y0 REAL, x1 REAL, y1 REAL, target INTEGER);
CREATE TABLE outline (seq INTEGER PRIMARY KEY, level INTEGER, title TEXT, page INTEGER);
"""


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def l1_path(key: str):
    return L1_DIR / f"{key}.sqlite"


def is_current(key: str) -> bool:
    p = l1_path(key)
    if not p.exists():
        return False
    con = sqlite3.connect(p)
    try:
        row = con.execute("SELECT value FROM meta WHERE key='sha256'").fetchone()
        return bool(row) and row[0] == sha256(pdf_path(key))
    except sqlite3.Error:
        return False
    finally:
        con.close()


def extract(key: str, force: bool = False) -> None:
    if not force and is_current(key):
        print(f"[L1] {key}: up to date")
        return
    L1_DIR.mkdir(parents=True, exist_ok=True)
    out = l1_path(key)
    if out.exists():
        out.unlink()
    src = pdf_path(key)
    t0 = time.time()
    doc = pymupdf.open(src)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('sha256', ?)", (sha256(src),))
    con.execute("INSERT INTO meta VALUES ('pdf', ?)", (src.name,))
    con.execute("INSERT INTO meta VALUES ('pages', ?)", (str(doc.page_count),))
    con.executemany(
        "INSERT INTO outline VALUES (?,?,?,?)",
        [(i, lvl, title, page) for i, (lvl, title, page) in enumerate(doc.get_toc(simple=True))],
    )
    rows, links = [], []
    for pno in range(doc.page_count):
        page = doc[pno]
        plinks = []
        for ln in page.get_links():
            if ln.get("kind") == pymupdf.LINK_GOTO and ln.get("page", -1) >= 0:
                r = ln["from"]
                plinks.append((r.x0, r.y0, r.x1, r.y1, ln["page"] + 1))
        links.extend((pno + 1, *pl) for pl in plinks)
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                spans = [[s["text"], round(s["size"], 1), f"{s['color']:06x}", s["flags"]] for s in l["spans"]]
                text = "".join(s[0] for s in spans)
                if not text.strip():
                    continue
                x0, y0, x1, y1 = l["bbox"]
                target = None
                for lx0, ly0, lx1, ly1, tgt in plinks:
                    # vertical overlap of at least half the line height
                    if min(y1, ly1) - max(y0, ly0) > (y1 - y0) / 2 and min(x1, lx1) > max(x0, lx0):
                        target = tgt
                        break
                rows.append((pno + 1, b["number"], x0, y0, x1, y1, text,
                             json.dumps(spans, ensure_ascii=False), target))
        if len(rows) > 20000:
            con.executemany("INSERT INTO line (page,block,x0,y0,x1,y1,text,spans,link_page) VALUES (?,?,?,?,?,?,?,?,?)", rows)
            rows.clear()
    con.executemany("INSERT INTO line (page,block,x0,y0,x1,y1,text,spans,link_page) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO link VALUES (?,?,?,?,?,?)", links)
    con.commit()
    n = con.execute("SELECT count(*) FROM line").fetchone()[0]
    con.close()
    print(f"[L1] {key}: {doc.page_count} pages, {n} lines in {time.time() - t0:.0f}s -> {out}")


def open_l1(key: str) -> sqlite3.Connection:
    con = sqlite3.connect(l1_path(key))
    con.row_factory = sqlite3.Row
    return con
