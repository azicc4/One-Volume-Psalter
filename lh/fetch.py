"""Download the web reference sources listed in sources/manifest.json into sources/web/ and verify their hashes."""
from __future__ import annotations

import hashlib
import json
import urllib.request

from lh.config import ROOT, SOURCES_WEB

MANIFEST = ROOT / "sources" / "manifest.json"
URLS = {
    "felix_just/Psalter.html": "https://catholic-resources.org/LoH/Psalter.html",
    "felix_just/Psalter-Hours.html": "https://catholic-resources.org/LoH/Psalter-Hours.html",
    "felix_just/Psalter-Index.html": "https://catholic-resources.org/LoH/Psalter-Index.html",
    "felix_just/Psalter-Omissions.html": "https://catholic-resources.org/LoH/Psalter-Omissions.html",
    "felix_just/Hours-Ordinary.html": "https://catholic-resources.org/LoH/Hours-Ordinary.html",
    "nova_vulgata/psalmorum.html": "https://www.vatican.va/archive/bible/nova_vulgata/documents/nova-vulgata_vt_psalmorum_lt.html",
}


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest() -> None:
    entries = {k: {"url": u, "sha256": sha256(SOURCES_WEB / k) if (SOURCES_WEB / k).exists() else None}
               for k, u in URLS.items()}
    MANIFEST.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def fetch(force: bool = False) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    for rel, url in URLS.items():
        dest = SOURCES_WEB / rel
        if dest.exists() and not force:
            print(f"[fetch] {rel}: present")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (one-volume-psalter)"})
        dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        want = (manifest.get(rel) or {}).get("sha256")
        note = "" if not want or want == sha256(dest) else "  (CHANGED since manifest — re-run lh psalter and review)"
        print(f"[fetch] {rel}: downloaded{note}")
