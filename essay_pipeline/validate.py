"""Phase 3 checks (a)-(e). Any failure => needs_review; out-of-scope levels
=> rejected. Nothing is ever auto-corrected."""
from dataclasses import dataclass

from bs4 import BeautifulSoup

from . import classify, config
from .extract import Candidate
from .parsers.base import ParsedPage
from .sources import Source
from .text import content_hash, jaccard, shingles, squash

ACCEPTED, NEEDS_REVIEW = "accepted", "needs_review"


@dataclass
class KnownEssay:
    id: str
    hash: str
    shingles: set[str]


@dataclass
class Decision:
    outcome: str  # accepted | needs_review | rejected_undergraduate | rejected_doctoral | rejected_out_of_category
    reasons: list[str]


def page_text_for_verbatim(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(["script", "style", "noscript"]):
        el.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    return squash(soup.get_text(""))


def decide(c: Candidate, page: ParsedPage, html: str, source: Source, record_id: str,
           known: list[KnownEssay]) -> Decision:
    # (e) programme level -- out-of-scope levels are rejected, not reviewed.
    if c.level == "doctoral":
        return Decision("rejected_doctoral", ["doctoral programme (DPhil/PhD)"])
    if c.level == "undergraduate":
        return Decision("rejected_undergraduate", ["undergraduate programme / UCAS"])
    if c.level == "masters" and c.institution and c.programme and c.programme_category is None:
        return Decision("rejected_out_of_category",
                        ["master's programme outside Oxford, Cambridge and MPP/MPA categories"])

    reasons = [f"extract: {r}" for r in c.reasons]
    if c.level != "masters":
        reasons.append("e: programme level not clearly master's")

    # (a) acceptance evidence names institution AND master's programme
    ev = c.evidence
    if not ev or not ev.sentence:
        reasons.append("a: acceptance_evidence is empty")
    else:
        if not ev.institution:
            reasons.append("a: acceptance_evidence does not name a single institution")
        if not ev.programmes or classify.classify_level(" ".join(ev.programmes)) != "masters":
            reasons.append("a: acceptance_evidence does not name a master's-level programme")
        if c.programme_category is None:
            reasons.append("a: programme category could not be determined")

    # (b) verbatim presence in the cached HTML (whitespace-insensitive)
    haystack = page_text_for_verbatim(html)
    if not c.essay_text:
        reasons.append("b: no essay text")
    elif squash(c.essay_text) not in haystack:
        reasons.append("b: essay text not found verbatim in cached HTML")
    if ev and squash(ev.sentence) not in haystack:
        reasons.append("b: acceptance_evidence not found verbatim in cached HTML")
    if c.prompt_text and squash(c.prompt_text) not in haystack:
        reasons.append("b: prompt_text not found verbatim in cached HTML")

    # (c) exact and near duplicates
    if c.essay_text:
        h, sh = content_hash(c.essay_text), shingles(c.essay_text)
        for k in known:
            if k.id == record_id:
                continue
            if k.hash == h:
                reasons.append(f"c: exact duplicate of {k.id}")
            elif (sim := jaccard(sh, k.shingles)) >= config.NEAR_DUPLICATE_THRESHOLD:
                reasons.append(f"c: near-duplicate of {k.id} (similarity {sim:.2f})")

    # (d) template / sample / AI-generated wording on the page
    flags = classify.template_flags(page.content_text)
    if flags:
        reasons.append(f"d: page contains template/sample wording: {', '.join(flags)}")

    # Terms gate: nothing enters the main repository from unreviewed terms.
    if source.terms_status == "unreviewed":
        reasons.append("terms: source terms of use not yet reviewed")

    return Decision(NEEDS_REVIEW if reasons else ACCEPTED, reasons)
