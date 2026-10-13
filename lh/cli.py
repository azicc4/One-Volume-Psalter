"""Command line entry point: python -m lh <command> ..."""
import argparse

from lh.config import PDFS


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lh", description="One-Volume Psalter build pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("extract", help="L1: dump spans/links/outline of source PDFs")
    p.add_argument("keys", nargs="*", default=["PA"], help=f"PDF keys ({', '.join(PDFS)}) or 'all'")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("build", help="L2-L5: parse sources and build build/lh.sqlite")
    p.add_argument("keys", nargs="*", default=["PA"])

    p = sub.add_parser("verify", help="L6: run verification checks and write reports/verification.md")
    p.add_argument("keys", nargs="*", default=["PA"])

    sub.add_parser("psalter", help="import Felix Just tables and write reports/psalter_discrepancies.md")

    p = sub.add_parser("find", help="full-text search of objects (accent-insensitive)")
    p.add_argument("query", nargs="+")
    p.add_argument("--type")

    p = sub.add_parser("show", help="show one object and every place it is printed")
    p.add_argument("id")

    p = sub.add_parser("hour", help="reassemble one hour from the database, e.g. lh hour OT.01.MON LAUDS")
    p.add_argument("day")
    p.add_argument("hour")

    p = sub.add_parser("fetch", help="download the web reference sources (Felix Just, Nova Vulgata) into sources/web/")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("all", help="run the whole pipeline: build, verify, psalter, export, catalog, book --poc")
    p.add_argument("keys", nargs="*", default=["PA", "LQP", "ADV", "COM", "SPA", "SP", "SQ", "SADV"])

    sub.add_parser("export", help="write diffable JSONL snapshots of the database to data/export/")

    sub.add_parser("catalog", help="L7: write the searchable reference catalog to reference/index.html")

    p = sub.add_parser("book", help="L8: generate LaTeX from the database and build the PDF")
    p.add_argument("--poc", action="store_true", help="proof of concept (psalter week I, Sunday and Monday)")
    p.add_argument("--no-pdf", action="store_true", help="only write the generated .tex")

    args = ap.parse_args(argv)

    if args.cmd == "all":
        indexed = [k.split(":")[0] for k in args.keys if k.split(":")[0] != "ADV"]   # ADV has no index check
        for step in (["build", *args.keys], ["verify", *indexed], ["psalter"], ["export"], ["catalog"], ["book", "--poc"]):
            print(f"== lh {' '.join(step)}")
            main(step)
        return

    if args.cmd == "extract":
        from lh.extract.spans import extract
        keys = list(PDFS) if args.keys == ["all"] else args.keys
        for k in keys:
            extract(k, force=args.force)
    elif args.cmd == "build":
        from lh.extract.spans import extract
        from lh.model.build import build
        for k in args.keys:
            extract(k.split(":")[0])
        build(args.keys)
    elif args.cmd == "verify":
        from lh.verify.checks import run_all
        from lh.verify.report import write_report
        out = run_all(args.keys)
        print(f"[verify] report -> {write_report(out)}")
        print(f"  roundtrip failures: {out['roundtrip']['failures']}/{out['roundtrip']['occurrences']}; "
              f"structure incomplete: {out['structure']['incomplete']}; psalm lines divergent: {out['psalms']['divergent']}; "
              f"near-duplicates: {out['variants']['pairs']}")
        cov = {k[9:]: v["gaps"] for k, v in out.items() if k.startswith("coverage:")}
        print(f"  coverage gaps per source: {cov}  (reports/coverage_<KEY>.md)")
        if "sanctis_overlaps" in out:
            print(f"  Sanctis overlaps: {out['sanctis_overlaps']}  (reports/sanctis_overlaps.md)")
        for k, v in out.items():
            if k.startswith("copies:"):
                print(f"  copies {k[7:]}: {v['same']}/{v['multi']} repeated day/hours collapse; {v['differ']} differ "
                      f"({v['explained']} explained, {v['review']} unexplained); unexplained calendar findings {v['calendar']}  "
                      f"(reports/{k[7:].lower()}_copies.md)")
    elif args.cmd == "psalter":
        from lh.psalter.compare import compare
        from lh.psalter.felix import import_felix
        print(f"[psalter] {len(import_felix())} seed rows from Felix Just")
        print(f"[psalter] {dict(compare())} -> reports/psalter_discrepancies.md")
        from lh.psalter.novavulgata import fill
        print(f"[psalter] Nova Vulgata gap fill: {fill()} -> reports/psalter_coverage.md")
    elif args.cmd in ("find", "show", "hour"):
        from lh import query
        getattr(query, args.cmd)(args)
    elif args.cmd == "book":
        from lh.render.build_pdf import build_pdf
        from lh.render.poc import write_poc
        print(f"[book] wrote {write_poc()}")
        if not args.no_pdf:
            print(f"[book] pdf -> {build_pdf('poc')}")
    elif args.cmd == "catalog":
        from lh.catalog.build import build_catalog
        print(f"[catalog] {build_catalog()}")
    elif args.cmd == "export":
        from lh.model.export import export
        print(f"[export] {export()} -> data/export/")
    elif args.cmd == "fetch":
        from lh.fetch import fetch, write_manifest
        fetch(args.force)
        write_manifest()
