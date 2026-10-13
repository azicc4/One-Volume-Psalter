"""data/overrides mechanism, exercised on a temporary copy of the database."""
import json
import shutil
import sqlite3

import pytest

from lh.config import DB_PATH
from lh.model import overrides

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run `python -m lh build` first")


@pytest.fixture
def db(tmp_path, monkeypatch):
    copy = tmp_path / "lh.sqlite"
    shutil.copy(DB_PATH, copy)
    monkeypatch.setattr(overrides, "OVERRIDES", tmp_path)
    con = sqlite3.connect(copy)
    con.execute("DROP TABLE IF EXISTS override_log")
    yield con, tmp_path
    con.close()


def test_replace_merge_and_note(db):
    con, d = db
    ant = "ant.ad-te-orabo-domine.d967f7"
    a, b = con.execute("SELECT id FROM object WHERE type='ant' AND id != ? ORDER BY id LIMIT 2", (ant,)).fetchall()
    (d / "t.yaml").write_text(f"""
- {{id: T1, action: replace, object: {ant}, find: "mane", replace: "MANE", reason: r, evidence: e}}
- {{id: T2, action: merge, object: {a[0]}, into: {b[0]}, reason: r, evidence: e}}
- {{id: T3, action: note, reason: r, evidence: e}}
""", encoding="utf-8")
    assert overrides.apply(con) == 3
    text = json.loads(con.execute("SELECT payload FROM object WHERE id=?", (ant,)).fetchone()[0])["text"]
    assert "MANE" in text
    assert con.execute("SELECT count(*) FROM object WHERE id=?", (a[0],)).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM occurrence WHERE object_id=?", (a[0],)).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM override_log").fetchone()[0] == 3


def test_replace_must_match(db):
    con, d = db
    (d / "t.yaml").write_text("- {id: T1, action: replace, object: ant.ad-te-orabo-domine.d967f7, find: 'zzz', "
                              "replace: 'y', reason: r, evidence: e}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not found"):
        overrides.apply(con)


def test_entries_need_reason_and_evidence(db):
    con, d = db
    (d / "t.yaml").write_text("- {id: T1, action: note}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="lacks"):
        overrides.apply(con)
