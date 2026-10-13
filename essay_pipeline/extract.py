"""Turn a parsed page into essay candidates. Every field is either copied
verbatim from the page or left None; anything undecided becomes a review
reason."""
from dataclasses import dataclass, field

from . import classify
from .parsers.base import Block, ParsedPage
from .sources import EssayBoundary, Page
from .text import clean, sentences


@dataclass
class Evidence:
    sentence: str
    location: str
    institution: str | None
    programmes: list[str]
    first_person_or_title: bool

    @property
    def strong(self) -> bool:
        return bool(self.institution and self.programmes and self.first_person_or_title)


@dataclass
class Candidate:
    index: int
    essay_text: str
    author_commentary: str | None
    prompt_text: str | None
    evidence: Evidence | None
    institution: str | None
    programme: str | None
    programme_category: str | None
    essay_type: str | None
    admission_year: str | None
    level: str
    reasons: list[str] = field(default_factory=list)


def _units(page: ParsedPage) -> list[tuple[str, str, bool]]:
    """(text, location, is_title_or_heading) for the title and every sentence."""
    units = []
    if page.title:
        units.append((page.title.text, page.title.location, True))
    for b in page.blocks:
        if b.kind == "heading":
            units.append((b.text, b.location, True))
            continue
        for i, s in enumerate(sentences(b.text), 1):
            units.append((s, f"{b.location}, sentence {i}", False))
    return units


def _evidence_from(text: str, location: str, title_like: bool) -> Evidence:
    return Evidence(text, location, classify.find_institution(text), classify.find_programmes(text),
                    title_like or classify.is_first_person(text))


def find_acceptance_evidence(page: ParsedPage) -> list[Evidence]:
    return [_evidence_from(t, loc, tl) for t, loc, tl in _units(page) if classify.has_acceptance_language(t)]


def _configured_evidence(page: ParsedPage, wanted: str) -> Evidence | None:
    wanted_c = clean(wanted)
    blocks = ([page.title] if page.title else []) + page.blocks
    for b in blocks:
        if wanted_c in b.text:
            return _evidence_from(wanted_c, b.location, b.kind in ("title", "heading"))
    return None


def _pick_evidence(page: ParsedPage, boundary: EssayBoundary, n_essays: int,
                   reasons: list[str]) -> Evidence | None:
    if boundary.acceptance_evidence:
        ev = _configured_evidence(page, boundary.acceptance_evidence)
        if ev is None:
            reasons.append("configured acceptance_evidence not found verbatim on page")
        return ev
    found = find_acceptance_evidence(page)
    if not found:
        reasons.append("no acceptance statement found on page")
        return None
    strong = [e for e in found if e.strong]
    if n_essays > 1:
        reasons.append("several essays on page: acceptance must be tied to each essay manually "
                       "(set acceptance_evidence in sources.json)")
    if not strong:
        reasons.append("acceptance statement does not name the institution, a programme and the "
                       "author in one sentence")
        return found[0]
    if len({tuple(e.programmes) for e in strong}) > 1:
        reasons.append("acceptance statements name different programmes")
    return strong[0]


def _slice(blocks: list[Block], boundary: EssayBoundary, reasons: list[str]) -> tuple[int, int] | None:
    if not (boundary.start_marker and boundary.end_marker):
        reasons.append("essay boundaries not confirmed: whole article stored; set start_marker/"
                       "end_marker in sources.json after inspecting the cached page")
        return 0, len(blocks) - 1
    start = next((i for i, b in enumerate(blocks) if clean(boundary.start_marker) in b.text), None)
    if start is None:
        reasons.append("start_marker not found on page")
        return None
    end = next((i for i in range(start, len(blocks)) if clean(boundary.end_marker) in blocks[i].text), None)
    if end is None:
        reasons.append("end_marker not found after start_marker")
        return None
    return start, end


def build_candidates(page: ParsedPage, page_cfg: Page) -> list[Candidate]:
    boundaries = page_cfg.essays or [EssayBoundary()]
    used: set[int] = set()
    out = []
    for idx, boundary in enumerate(boundaries):
        reasons: list[str] = []
        span = _slice(page.blocks, boundary, reasons) if page.blocks else None
        if span is None:
            if not page.blocks:
                reasons.append("no article text extracted")
            essay_text = ""
        else:
            used.update(range(span[0], span[1] + 1))
            essay_text = "\n\n".join(b.text for b in page.blocks[span[0]:span[1] + 1])

        prompt_text = None
        if boundary.prompt_marker:
            hit = next((b.text for b in page.blocks if clean(boundary.prompt_marker) in b.text), None)
            if hit is None:
                reasons.append("prompt_marker not found on page")
            prompt_text = hit

        ev = _pick_evidence(page, boundary, len(boundaries), reasons)
        institution = ev.institution if ev else None
        programme = ev.programmes[0] if ev and len(ev.programmes) == 1 else None
        if ev and len(ev.programmes) > 1:
            reasons.append("acceptance statement names more than one programme")

        level_text = ev.sentence if ev else page.content_text
        level = classify.classify_level(level_text)

        out.append(Candidate(
            index=idx,
            essay_text=essay_text,
            author_commentary=None,
            prompt_text=prompt_text,
            evidence=ev,
            institution=institution,
            programme=programme,
            programme_category=classify.programme_category(institution, programme),
            essay_type=classify.detect_essay_type(page.title.text if page.title else "",
                                                  ev.sentence if ev else ""),
            admission_year=classify.find_admission_year(ev.sentence) if ev else None,
            level=level,
            reasons=reasons,
        ))

    if page_cfg.essays:
        commentary = [b.text for i, b in enumerate(page.blocks) if i not in used]
        for c in out:
            c.author_commentary = "\n\n".join(commentary) or None
    return out
