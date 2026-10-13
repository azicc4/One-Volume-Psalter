"""Project paths and the registry of source documents."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
L1_DIR = BUILD / "l1"
DB_PATH = BUILD / "lh.sqlite"
DATA = ROOT / "data"
SEED = DATA / "seed"
OVERRIDES = DATA / "overrides"
EXPORT = DATA / "export"
REPORTS = ROOT / "reports"
SOURCES_WEB = ROOT / "sources" / "web"
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
    return ROOT / PDFS[key]
