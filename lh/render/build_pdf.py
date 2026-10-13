"""Run latexmk/LuaLaTeX on a book/*.tex file. Uses a project-local font cache (TEXMFCACHE) because the TeX Live
default cache directory is not writable here."""
from __future__ import annotations

import os
import shutil
import subprocess

from lh.config import BOOK, BUILD


def build_pdf(name: str) -> str:
    outdir = BUILD / "latex"
    outdir.mkdir(parents=True, exist_ok=True)
    cache = BUILD / "texmf-cache"
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEXMFCACHE=str(cache))
    cmd = ["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={outdir}", f"{name}.tex"]
    r = subprocess.run(cmd, cwd=BOOK, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = outdir / f"{name}.log"
    if r.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else r.stdout[-3000:]
        raise SystemExit(f"LaTeX failed (see {log}):\n{tail}")
    dest = BOOK / "out" / f"{name}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(outdir / f"{name}.pdf", dest)
    return str(dest)
