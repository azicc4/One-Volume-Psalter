"""Project paths and the registry of source documents.

Gitignored inputs (the source PDFs, their L1 dumps, cached web sources) can live outside the checkout — e.g. a git
worktree used by a parallel workstream reads them from the main checkout:
  LH_PDF_DIR   directory holding the eight LH-*.pdf files            (default: repo root)
  LH_L1_DIR    directory of build/l1/<KEY>.sqlite dumps              (default: build/l1)
  LH_WEB_DIR   directory of cached web sources (Felix Just, NV)      (default: sources/web)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
L1_DIR = Path(os.environ.get("LH_L1_DIR") or BUILD / "l1")
PDF_DIR = Path(os.environ.get("LH_PDF_DIR") or ROOT)
DB_PATH = BUILD / "lh.sqlite"
DATA = ROOT / "data"
SEED = DATA / "seed"
OVERRIDES = DATA / "overrides"
EXPORT = DATA / "export"
REPORTS = ROOT / "reports"
SOURCES_WEB = Path(os.environ.get("LH_WEB_DIR") or ROOT / "sources" / "web")
BOOK = ROOT / "book"

# Short keys for the eight source PDFs (kept in the repo root, gitignored).
PDFS = {
    "PA": "LH-Per_annum.pdf",
    "ADV": "LH-Adventus_et_Nativitatis.pdf",
    "LQP": "LH-Quadragesimae_et_Paschae.pdf",
    "COM": "LH-Communia.pdf",
    "SPA": "LH-Sanctis-Per_annum.pdf",
    "SADV": "LH-Sanctis-Adventus_et_Nativitatis.pdf",
    "SP": "LH-Sanctis-Paschae.pdf",
    "SQ": "LH-Sanctis-Quadragesimae.pdf",
}


def pdf_path(key: str) -> Path:
    return PDF_DIR / PDFS[key]


# Versions of the book built side by side from the same database (python -m lh book --variant NAME). Each has its
# own PDF, card, page budget and simulation; the viewer switches between them (Main | Experiment).
VARIANTS = {
    "main": {"file": "book", "card": "card", "label": "Main"},
    # B-17: the hymns and psalms of the four-week cycle printed in full at each hour, as in the four-volume
    # breviary; the Psalter in biblical order and the Hymns section are kept
    "weekly": {"file": "book-weekly", "card": "card-weekly", "label": "Experiment", "weekly_psalter": True,
               "note": "Experimental edition: the psalms and hymns of the four-week cycle printed at each hour"},
}
