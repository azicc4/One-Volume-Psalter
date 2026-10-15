"""Local server for the book preview viewer (tools/viewer). Started by "preview main.bat" and "preview experiment.bat"; stdlib only.

Serves, on 127.0.0.1 only:
  /                 → tools/viewer/index.html (and the viewer's own files)
  /pdfs.json        → the PDFs in book/out/ (name, size, modified)
  /outline/<name>.json → that PDF's bookmarks with page indexes (needs PyMuPDF; the viewer falls back without it)
  /pdf/<name>.pdf   → book/out/<name>.pdf (with HTTP Range support, so the viewer reads only the pages it shows)
Nothing else in the repository is reachable.

    python tools/viewer/serve.py [book|poc] [--port N] [--no-browser]
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import unquote, urlsplit

VIEWER = Path(__file__).resolve().parent
ROOT = VIEWER.parent.parent
OUT = ROOT / "book" / "out"

RANGE = re.compile(r"bytes=(\d*)-(\d*)$")
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript",
         ".mjs": "text/javascript", ".json": "application/json", ".pdf": "application/pdf",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"}


def pdf_list() -> list[dict]:
    return [{"name": p.stem, "size": p.stat().st_size, "mtime": int(p.stat().st_mtime)}
            for p in sorted(OUT.glob("*.pdf"), key=lambda p: (p.stem != "book", p.stem))]


_outlines: dict = {}


def outline(name: str) -> list | None:
    """The PDF's bookmarks as [level, title, page index], read by PyMuPDF (cached per file version). Resolving them in
    the browser walks the whole named-destination tree (~5 MB of the full book); here it costs nothing. None when
    PyMuPDF is missing (plain `py -3`): the viewer then resolves them itself."""
    if name not in {p["name"] for p in pdf_list()}:
        return None
    path = OUT / f"{name}.pdf"
    key = (name, path.stat().st_mtime_ns)
    if key not in _outlines:
        try:
            import pymupdf
        except ImportError:
            return None
        with pymupdf.open(path) as doc:
            _outlines[key] = [[level - 1, title, page - 1 if page > 0 else None]
                              for level, title, page in doc.get_toc(simple=True)]
    return _outlines[key]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve(head=False)

    def do_HEAD(self):
        self.serve(head=True)

    def serve(self, head: bool):
        path = unquote(urlsplit(self.path).path)
        if path == "/pdfs.json":
            return self.send(json.dumps(pdf_list()).encode(), ".json", head)
        if path.startswith("/outline/") and path.endswith(".json"):
            toc = outline(path[len("/outline/"):-len(".json")])
            return self.send(json.dumps(toc).encode(), ".json", head) if toc is not None else self.send_error(404)
        if path.startswith("/pdf/"):
            target = (OUT / path[5:]).resolve()
            base = OUT.resolve()
        else:
            target = (VIEWER / (path.lstrip("/") or "index.html")).resolve()
            base = VIEWER
        if target.is_dir():
            target = target / "index.html"
        if base not in target.parents or not target.is_file() or target.suffix not in TYPES:
            return self.send_error(404)
        with open(target, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            start, end = 0, size - 1
            m = RANGE.match(self.headers.get("Range", ""))
            if m and (m[1] or m[2]):                       # pdf.js reads the PDF in byte ranges, page by page
                if m[1]:
                    start, end = int(m[1]), min(int(m[2]) if m[2] else size - 1, size - 1)
                else:                                      # "bytes=-N": the last N bytes
                    start = max(0, size - int(m[2]))
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                self.headers_for(end - start + 1, target.suffix, status=206,
                                 extra={"Content-Range": f"bytes {start}-{end}/{size}"})
            else:
                self.headers_for(size, target.suffix)
            if not head:
                f.seek(start)
                left = end - start + 1
                try:                                       # in chunks: one 9 MB write stalls on Windows
                    while left > 0 and (chunk := f.read(min(64 * 1024, left))):
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (ConnectionError, OSError):         # the browser moved on (reload, or pdf.js switching to ranges)
                    pass

    def send(self, body: bytes, suffix: str, head: bool):
        self.headers_for(len(body), suffix)
        if not head:
            self.wfile.write(body)

    def headers_for(self, length: int, suffix: str, status: int = 200, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", TYPES[suffix])
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")          # a rebuilt book.pdf shows on the next reload
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def log_message(self, fmt, *args):                          # quiet: only errors
        if args and str(args[1])[:1] in "45":
            sys.stderr.write("[viewer] " + fmt % args + "\n")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Book preview viewer (ribbons, page turning)")
    ap.add_argument("pdf", nargs="?", default="book", help="book (default) or poc: a PDF in book/out/")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    if not (OUT / f"{args.pdf}.pdf").exists():
        have = ", ".join(p["name"] for p in pdf_list()) or "none"
        sys.exit(f"[viewer] book/out/{args.pdf}.pdf not found (available: {have}).\n"
                 f"         Build it first:  .venv\\Scripts\\python -m lh book"
                 + (" --poc" if args.pdf == "poc" else f" --variant {args.pdf.split('-', 1)[1]}" if "-" in args.pdf
                    else ""))
    for port in (args.port, 0):                                  # fall back to any free port
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?file={args.pdf}"
    print(f"[viewer] {url}   (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, (url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[viewer] stopped")


if __name__ == "__main__":
    main()
