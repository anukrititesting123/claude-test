"""CLI.

  python -m essay_pipeline run [--source ID] [--refresh]   fetch (polite) + parse + validate
  python -m essay_pipeline reparse [--source ID]            same, cache only (no network)
  python -m essay_pipeline export                           CSVs, index.md, run_report.md
  python -m essay_pipeline inspect --source ID              print cached page blocks to set markers
"""
import argparse
import sys

from . import config
from .export import export_all
from .fetch import PageCache
from .parsers import PARSERS
from .pipeline import run
from .sources import load_sources


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="essay_pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "reparse"):
        p = sub.add_parser(name)
        p.add_argument("--source")
        if name == "run":
            p.add_argument("--refresh", action="store_true", help="ignore cache and re-fetch")
    sub.add_parser("export")
    p = sub.add_parser("inspect")
    p.add_argument("--source", required=True)
    args = ap.parse_args(argv)

    data = config.data_dir()
    sources = load_sources()

    if args.cmd in ("run", "reparse"):
        run_id = run(sources, data, offline=args.cmd == "reparse",
                     refresh=getattr(args, "refresh", False), only=args.source)
        paths = export_all(data, run_id)
        print(f"run {run_id} done")
        for k, v in paths.items():
            print(f"  {k}: {v}")
        return 0

    if args.cmd == "export":
        for k, v in export_all(data).items():
            print(f"{k}: {v}")
        return 0

    src = next((s for s in sources if s.source_id == args.source), None)
    if src is None:
        print(f"unknown source {args.source}", file=sys.stderr)
        return 2
    cache = PageCache(data / "cache")
    for page_cfg in src.pages:
        hit = cache.get(page_cfg.url)
        print(f"== {page_cfg.url}")
        if not hit:
            print("   (not cached: run `python -m essay_pipeline run` first)")
            continue
        page = PARSERS[src.parser](hit[0], page_cfg.url)
        if page.title:
            print(f"[title] {page.title.location}: {page.title.text}")
        for i, b in enumerate(page.blocks):
            print(f"[{i}] ({b.kind}) {b.location}: {b.text[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
