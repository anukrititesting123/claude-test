"""Approved-source registry (sources.json). Only sources with
status == "approved" are ever fetched. Adding a source needs the user's
approval first."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config

VALID_TERMS = {"unreviewed", "ok_private_study", "reuse_permitted", "prohibited"}
VALID_TRUST = {"official", "first-person", "third-party"}


@dataclass
class EssayBoundary:
    """Set by a human after reading the cached page. Each string must appear
    verbatim on the page, otherwise the record goes to needs_review."""
    start_marker: str | None = None
    end_marker: str | None = None
    acceptance_evidence: str | None = None
    prompt_marker: str | None = None


@dataclass
class Page:
    url: str
    essays: list[EssayBoundary] = field(default_factory=list)


@dataclass
class Source:
    source_id: str
    status: str
    parser: str
    publisher: str
    source_type: str
    trust_level: str
    terms_status: str
    license_or_terms_note: str
    pages: list[Page]
    needs_js: bool = False
    phase1_ref: str | None = None

    @property
    def approved(self) -> bool:
        return self.status == "approved"


def load_sources(path: Path | None = None) -> list[Source]:
    raw = json.loads(Path(path or config.SOURCES_FILE).read_text(encoding="utf-8"))
    out = []
    for s in raw["sources"]:
        if s["terms_status"] not in VALID_TERMS:
            raise ValueError(f"{s['source_id']}: terms_status must be one of {sorted(VALID_TERMS)}")
        if s["trust_level"] not in VALID_TRUST:
            raise ValueError(f"{s['source_id']}: trust_level must be one of {sorted(VALID_TRUST)}")
        pages = [Page(p["url"], [EssayBoundary(**e) for e in p.get("essays", [])]) for p in s["pages"]]
        out.append(Source(
            source_id=s["source_id"], status=s["status"], parser=s["parser"],
            publisher=s["publisher"], source_type=s["source_type"], trust_level=s["trust_level"],
            terms_status=s["terms_status"], license_or_terms_note=s["license_or_terms_note"],
            pages=pages, needs_js=s.get("needs_js", False), phase1_ref=s.get("phase1_ref"),
        ))
    return out
