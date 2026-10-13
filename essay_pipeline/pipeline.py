"""Orchestrates fetch -> parse -> extract -> validate -> store for approved
sources only."""
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .extract import build_candidates
from .fetch import PageCache, PoliteFetcher
from .parsers import PARSERS
from .sources import Source
from .text import content_hash, shingles, word_count
from .validate import KnownEssay, decide


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_id(url: str, index: int) -> str:
    return "ess_" + hashlib.sha256(f"{url}#{index}".encode()).hexdigest()[:12]


def _known_essays(conn) -> list[KnownEssay]:
    return [KnownEssay(r["id"], content_hash(r["essay_text"]), shingles(r["essay_text"]))
            for r in conn.execute("SELECT id, essay_text FROM essays")]


def run(sources: list[Source], data_dir: Path, offline: bool = False, refresh: bool = False,
        only: str | None = None, fetcher: PoliteFetcher | None = None) -> str:
    run_id = _now().replace(":", "") + "_" + uuid.uuid4().hex[:6]
    conn = db.connect(data_dir / "essays.sqlite")
    fetcher = fetcher or PoliteFetcher(PageCache(data_dir / "cache"), offline=offline)
    log = lambda sid, url, event, detail="": db.log_event(conn, run_id, _now(), sid, url, event, detail)
    log(None, None, "run_started", f"offline={offline} refresh={refresh} only={only}")

    for src in sources:
        if only and src.source_id != only:
            continue
        if not src.approved:
            log(src.source_id, None, "source_not_approved", f"status={src.status}")
            continue
        log(src.source_id, None, "source_attempted")
        if src.terms_status == "prohibited":
            for p in src.pages:
                log(src.source_id, p.url, "terms_prohibited", src.license_or_terms_note)
            continue
        parse = PARSERS.get(src.parser)
        if parse is None:
            log(src.source_id, None, "parse_error", f"no parser module named {src.parser!r}")
            continue

        for page_cfg in src.pages:
            res = (fetcher.get_rendered if src.needs_js else fetcher.get)(page_cfg.url, refresh=refresh)
            if res.skipped:
                log(src.source_id, page_cfg.url, res.skipped, res.detail)
                continue
            log(src.source_id, page_cfg.url, "cache_hit" if res.from_cache else "fetched")
            try:
                page = parse(res.html, page_cfg.url)
                candidates = build_candidates(page, page_cfg)
            except Exception as e:  # a broken parser must not stop the run
                log(src.source_id, page_cfg.url, "parse_error", f"{type(e).__name__}: {e}")
                continue

            for c in candidates:
                rid = record_id(page_cfg.url, c.index)
                decision = decide(c, page, res.html, src, rid, _known_essays(conn))
                log(src.source_id, page_cfg.url, "essay_found", rid)
                if decision.outcome.startswith("rejected"):
                    db.record_rejection(conn, {
                        "id": rid, "source_id": src.source_id, "source_url": page_cfg.url,
                        "outcome": decision.outcome, "reason": "; ".join(decision.reasons),
                        "institution": c.institution, "programme": c.programme,
                        "acceptance_evidence": c.evidence.sentence if c.evidence else None,
                        "date_scraped": res.fetched_at,
                    })
                    log(src.source_id, page_cfg.url, decision.outcome, rid)
                    continue
                db.upsert_essay(conn, {
                    "id": rid,
                    "institution": c.institution,
                    "programme": c.programme,
                    "programme_category": c.programme_category,
                    "essay_type": c.essay_type,
                    "prompt_text": c.prompt_text,
                    "admission_year": c.admission_year,
                    "essay_text": c.essay_text,
                    "word_count": word_count(c.essay_text) if c.essay_text else None,
                    "source_url": page_cfg.url,
                    "source_type": src.source_type,
                    "publisher": src.publisher,
                    "acceptance_evidence": c.evidence.sentence if c.evidence else None,
                    "date_scraped": res.fetched_at,
                    "trust_level": src.trust_level,
                    "license_or_terms_note": src.license_or_terms_note,
                    "review_status": decision.outcome,
                }, {
                    "source_id": src.source_id,
                    "acceptance_evidence_location": c.evidence.location if c.evidence else None,
                    "author_commentary": c.author_commentary,
                    "review_reasons": decision.reasons,
                    "content_sha256": content_hash(c.essay_text) if c.essay_text else None,
                    "reuse_permitted": src.terms_status == "reuse_permitted",
                })
                log(src.source_id, page_cfg.url, f"stored_{decision.outcome}", rid)
            conn.commit()

    log(None, None, "run_finished")
    conn.commit()
    conn.close()
    return run_id
