"""The full book prints every text once (WS6): run after `python -m lh book` (or `lh book --no-pdf`)."""
import re
import sqlite3

import pytest

from lh.config import BOOK, BUILD, DB_PATH
from lh.render.texcheck import check, labels

TEX = BOOK / "generated" / "book_body.tex"
pytestmark = pytest.mark.skipif(not TEX.exists() or not DB_PATH.exists(), reason="run `python -m lh book` first")
PRINTED = ("ordinary", "psalter", "hymns", "time", "commons", "saints", "readings")


@pytest.fixture(scope="module")
def body():
    return TEX.read_text(encoding="utf-8")


def anchor(oid: str, otype: str, home: str) -> str:
    s = re.sub(r"[^A-Za-z0-9.:-]", "-", oid)
    return f"o:psu:{s}" if otype == "psalm" and home == "psalter" else f"o:{s}"


def test_every_homed_object_labelled_exactly_once(body):
    lab = labels(body)
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(f"SELECT id, type, home FROM object WHERE home IN ({','.join('?' * len(PRINTED))})",
                       PRINTED).fetchall()
    assert rows, "attribution has not run (object.home empty)"
    bad = [(oid, lab[anchor(oid, t, h)]) for oid, t, h in rows if lab[anchor(oid, t, h)] != 1]
    assert not bad, f"{len(bad)} objects not labelled exactly once, e.g. {bad[:10]}"


def test_no_duplicate_labels_and_every_reference_resolves(body):
    r = check(body)
    assert not r["duplicates"], r["duplicates"][:20]
    assert not r["unresolved"], r["unresolved"][:20]


def test_inline_objects_have_no_home_label():
    con = sqlite3.connect(DB_PATH)
    n = con.execute("SELECT count(*) FROM object WHERE type IN ('rubric','link','ordinary_ref') AND home != 'inline'")
    assert n.fetchone()[0] == 0


def test_de_communi_references_point_to_a_common():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT DISTINCT target FROM reference WHERE kind='de_communi'").fetchall()
    assert rows and all(t.startswith("COMMON.") for (t,) in rows)


def test_latex_log_clean():
    log = BUILD / "latex" / "book.log"
    if not log.exists():
        pytest.skip("PDF not built")
    t = log.read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"Reference `[^']*' on page \d+ undefined", t)
    assert "Missing character" not in t
