"""Static copy of the book preview viewer for GitHub Pages (.github/workflows/pages.yml).

Writes what serve.py answers live as plain files, so any static host can serve the viewer:
  build/site/index.html, viewer.js, viewer.css, vendor/   the viewer
  build/site/pdfs.json                                     the PDFs in book/out/
  build/site/outline/<name>.json                           their bookmarks (needs PyMuPDF)
  build/site/pdf/<name>.pdf                                the PDFs
  build/site/pdf/<file>-ribbons.json                       the page arrangement tables

    python tools/viewer/build_site.py [--out build/site]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve import OUT, ROOT, VIEWER, outline, pdf_list  # noqa: E402

VIEWER_FILES = ["index.html", "viewer.js", "viewer.css", "vendor"]


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in VIEWER_FILES:
        src = VIEWER / name
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, out / name)
    pdfs = pdf_list()
    if not pdfs:
        sys.exit("[site] no PDFs in book/out/ — build the book first (python -m lh book)")
    (out / "pdfs.json").write_text(json.dumps(pdfs), encoding="utf-8")
    (out / "outline").mkdir()
    (out / "pdf").mkdir()
    for p in pdfs:
        toc = outline(p["name"])
        if toc is None:
            sys.exit("[site] PyMuPDF is needed to read the bookmarks: pip install pymupdf")
        (out / "outline" / f"{p['name']}.json").write_text(json.dumps(toc), encoding="utf-8")
        shutil.copy2(OUT / f"{p['name']}.pdf", out / "pdf" / f"{p['name']}.pdf")
    for table in OUT.glob("*-ribbons.json"):              # the page arrangement tables (python -m lh ribbons)
        shutil.copy2(table, out / "pdf" / table.name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    args = ap.parse_args(argv)
    out = build(args.out)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"[site] {out}  ({size / 1e6:.1f} MB; PDFs: {', '.join(p['name'] for p in pdf_list())})")


if __name__ == "__main__":
    main()
