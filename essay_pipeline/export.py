"""CSV exports, grouped markdown index and the run report."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import config, db
from .text import excerpt

PRIVATE_EXTRA = ["source_id", "acceptance_evidence_location", "author_commentary", "review_reasons"]


def export_all(data_dir: Path, run_id: str | None = None) -> dict[str, Path]:
    conn = db.connect(data_dir / "essays.sqlite")
    out_dir = data_dir / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = db.essays_with_provenance(conn)
    run_id = run_id or (conn.execute("SELECT run_id FROM run_events ORDER BY at DESC, rowid DESC LIMIT 1")
                        .fetchone() or [None])[0]
    paths = {
        "private_csv": _write_private_csv(rows, out_dir / "essays_private.csv"),
        "shareable_csv": _write_shareable_csv(rows, out_dir / "essays_shareable.csv"),
        "index": _write_index(rows, out_dir / "index.md"),
        "report": _write_report(conn, run_id, out_dir / "run_report.md"),
    }
    conn.close()
    return paths


def _write_private_csv(rows, path: Path) -> Path:
    """Full text, private study only. Never publish this file."""
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(db.ESSAY_COLUMNS + PRIVATE_EXTRA)
        for r in rows:
            w.writerow([r[c] for c in db.ESSAY_COLUMNS + PRIVATE_EXTRA])
    return path


def _write_shareable_csv(rows, path: Path) -> Path:
    """Metadata + short excerpt + link. Full text only where the source's
    terms were reviewed and permit reuse."""
    cols = [c for c in db.ESSAY_COLUMNS if c != "essay_text"] + ["excerpt", "essay_text_if_reuse_permitted"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            vals = [r[c] for c in db.ESSAY_COLUMNS if c != "essay_text"]
            vals.append(excerpt(r["essay_text"], config.EXCERPT_WORDS))
            vals.append(r["essay_text"] if r["reuse_permitted"] else "")
            w.writerow(vals)
    return path


def _write_index(rows, path: Path) -> Path:
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r in rows:
        if r["review_status"] != "accepted":
            continue
        tree[r["programme_category"]][r["institution"]][r["programme"]][
            r["admission_year"] or "Year not stated"].append(r)
    review = [r for r in rows if r["review_status"] == "needs_review"]

    lines = ["# Accepted master's essays: index", "",
             "Metadata, links to the original pages and short excerpts only. The essays are the "
             "authors' copyright; read them at the source.", ""]
    if not tree:
        lines += ["_No essays have passed every check yet._", ""]
    for cat in sorted(tree):
        lines.append(f"## {cat}")
        for inst in sorted(tree[cat]):
            lines.append(f"### {inst}")
            for prog in sorted(tree[cat][inst]):
                lines.append(f"#### {prog}")
                for year in sorted(tree[cat][inst][prog]):
                    lines.append(f"- **{year}**")
                    for r in tree[cat][inst][prog][year]:
                        lines.append(f"  - [{r['essay_type'] or 'essay'}]({r['source_url']}) by "
                                     f"{r['publisher']} ({r['trust_level']}, {r['word_count']} words), "
                                     f"id `{r['id']}`")
                        lines.append(f"    - Acceptance evidence: \"{r['acceptance_evidence']}\" "
                                     f"({r['acceptance_evidence_location']})")
                lines.append("")
    lines += [f"## Needs review ({len(review)})", ""]
    for r in review:
        lines.append(f"- [{r['source_url']}]({r['source_url']}): id `{r['id']}`")
        for reason in json.loads(r["review_reasons"]):
            lines.append(f"  - {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_report(conn, run_id: str | None, path: Path) -> Path:
    events = conn.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY rowid", (run_id,)).fetchall()
    count = Counter(e["event"] for e in events)
    status = Counter(r[0] for r in conn.execute("SELECT review_status FROM essays"))
    rejected = Counter(r[0] for r in conn.execute("SELECT outcome FROM rejections"))
    skip_events = ("robots_disallowed", "robots_unavailable", "terms_prohibited", "fetch_error",
                   "not_cached", "parse_error", "source_not_approved")

    lines = [
        f"# Run report: {run_id}", "",
        "## This run", "",
        f"- Sources attempted: {count['source_attempted']}",
        f"- Pages fetched from network: {count['fetched']}; served from cache: {count['cache_hit']}",
        f"- Essays found: {count['essay_found']}",
        f"- Stored as accepted: {count['stored_accepted']}",
        f"- Sent to review: {count['stored_needs_review']}",
        f"- Rejected as undergraduate: {count['rejected_undergraduate']}",
        f"- Rejected as doctoral: {count['rejected_doctoral']}",
        f"- Rejected as master's outside target categories: {count['rejected_out_of_category']}",
        "", "## Skipped pages and errors", "",
    ]
    skipped = [e for e in events if e["event"] in skip_events]
    lines += [f"- `{e['event']}` {e['source_id'] or ''} {e['url'] or ''}: {e['detail']}" for e in skipped] or ["- none"]
    lines += [
        "", "## Repository totals (all runs)", "",
        f"- Accepted: {status['accepted']}",
        f"- Needs review: {status['needs_review']}",
        f"- Rejected out of scope: {sum(rejected.values())} "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(rejected.items())) or 'none'})",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
