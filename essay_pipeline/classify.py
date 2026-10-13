"""Rule-based detection of acceptance statements, programmes, institutions
and programme level. These rules only *find* text that is on the page; when
they cannot decide, callers must send the record to needs_review."""
import re

ACCEPT_RE = re.compile(
    r"\b(?:admitted|accepted|admission offer|offered (?:me )?a place|"
    r"offer of a place|received (?:an|my|the|a) (?:conditional |unconditional )?offer|"
    r"got (?:an offer|in(?:to)?\b)|application was successful|"
    r"was successful in my application|successful applicant)",
    re.I,
)
# Anything hedged, negated or hypothetical is never treated as evidence.
NEGATION_RE = re.compile(
    r"\b(?:not|never|no|rejected|reject|unsuccessful|waitlist(?:ed)?|declined|"
    r"hope|hoping|hopefully|would|wish|if)\b|n't\b",
    re.I,
)
FIRST_PERSON_RE = re.compile(r"\b(?:I|my|me|I'm|I’ve|I've)\b")

_FIELD = r"[A-Z][\w&'’\-]*(?:\s+(?:[A-Z][\w&'’\-]*|and|of|in|for|the|&|on))*"
_ABBR = r"(?:M\.?\s?Sc|M\.?\s?Phil|M\.?\s?St|M\.?\s?Res|MPP|MPA(?:[-/]ID)?|MAPP|LL\.?M|MJur|MLitt)\.?"
PROGRAMME_RE = re.compile(
    rf"\b(?:{_ABBR}(?:\s+(?:in|of)\s+{_FIELD}|\s*\(\s*{_FIELD}\s*\))?"
    rf"|MA\s+(?:in|of)\s+{_FIELD}"
    rf"|Master(?:'s|’s|s)?\s+(?:of|in)\s+{_FIELD})"
)
_TRAILING_JUNK = {"and", "of", "in", "for", "the", "&", "on", "I"}

MASTERS_RE = re.compile(
    r"\b(?:M\.?\s?Sc|M\.?\s?Phil|M\.?\s?St|M\.?\s?Res|MPP|MPA|MAPP|LL\.?M|MJur|MLitt|"
    r"MA\s+(?:in|of)|Master(?:'s|’s|s)?\b|postgraduate taught)",
)
DOCTORAL_RE = re.compile(r"\b(?:D\.?\s?Phil|Ph\.?\s?D|doctoral|doctorate)\b", re.I)
UNDERGRAD_RE = re.compile(
    r"\b(?:UCAS|undergraduate|B\.?A\.?(?=\s|$|[,;)])|B\.?\s?Sc|bachelor(?:'s|s)?)\b", re.I
)
# Postgraduate degrees whose names look undergraduate; never auto-reject these.
LEVEL_AMBIGUOUS_RE = re.compile(
    r"\b(?:BCL|Bachelor of Civil Law|BPhil|B\.Phil|Bachelor of Philosophy)\b", re.I
)

MPP_MPA_RE = re.compile(
    r"\b(?:MPP|MPA(?:[-/]ID)?|Master(?:'s|’s|s)?\s+(?:of|in)\s+"
    r"(?:Public\s+(?:Policy|Administration|Affairs)|Development\s+Practice))\b",
    re.I,
)

OXFORD_RE = re.compile(r"\b(?:University of Oxford|Oxford University|Oxford|Blavatnik)\b")
CAMBRIDGE_RE = re.compile(r"\b(?:University of Cambridge|Cambridge University|Cambridge)\b")
CAMBRIDGE_MA_RE = re.compile(r"\b(?:Harvard|MIT|Massachusetts|Kennedy School|Cambridge,\s*MA)\b")
OTHER_INSTITUTION_RE = re.compile(
    r"\b(?:(?:University|College|Institute|School) of(?: the)? [A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)*"
    r"|[A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)*\s+(?:University|College|School of [A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)*))"
)

ESSAY_TYPE_PATTERNS = [
    ("statement of purpose", re.compile(r"\bstatement of purpose\b|\bSOP\b", re.I)),
    ("personal statement", re.compile(r"\bpersonal statement\b", re.I)),
    ("writing sample", re.compile(r"\bwriting sample\b", re.I)),
    ("supplemental essay", re.compile(r"\bsupplement(?:al|ary) essay\b", re.I)),
]

ADMISSION_YEAR_RE = re.compile(
    r"\b(?:for|in|class of|entry|intake|cohort|cycle|matriculat\w*)\s+(?:the\s+)?"
    r"((?:19|20)\d{2}(?:\s?[/–-]\s?\d{2,4})?)"
    r"|\b((?:19|20)\d{2}(?:\s?[/–-]\s?\d{2,4})?)\s+(?:entry|intake|cohort|admissions?\s+cycle)\b",
    re.I,
)

TEMPLATE_FLAG_RE = re.compile(
    r"\b(?:example|sample|illustrative|for illustration|hypothetical|fictional|"
    r"invented|template|we wrote|written by our|written by (?:an? )?(?:AI|ChatGPT)|"
    r"AI[- ]generated|generated (?:by|with|using) (?:AI|ChatGPT|GPT))\b",
    re.I,
)


def has_acceptance_language(sentence: str) -> bool:
    return bool(ACCEPT_RE.search(sentence)) and not NEGATION_RE.search(sentence)


def is_first_person(sentence: str) -> bool:
    return bool(FIRST_PERSON_RE.search(sentence))


def find_programmes(text: str) -> list[str]:
    found = []
    for m in PROGRAMME_RE.finditer(text):
        tokens = m.group(0).split()
        while tokens and tokens[-1] in _TRAILING_JUNK:
            tokens.pop()
        prog = " ".join(tokens).rstrip(".,;:")
        if prog and prog not in found:
            found.append(prog)
    return found


def find_institution(text: str) -> str | None:
    """Return the single institution named in `text`, else None."""
    names = set()
    if OXFORD_RE.search(text):
        names.add("University of Oxford")
    if CAMBRIDGE_RE.search(text) and not CAMBRIDGE_MA_RE.search(text):
        names.add("University of Cambridge")
    if not names:
        for m in OTHER_INSTITUTION_RE.finditer(text):
            names.add(m.group(0).strip())
    return names.pop() if len(names) == 1 else None


def classify_level(text: str) -> str:
    """'masters', 'doctoral', 'undergraduate' or 'ambiguous'."""
    if LEVEL_AMBIGUOUS_RE.search(text):
        return "ambiguous"
    m, d, u = bool(MASTERS_RE.search(text)), bool(DOCTORAL_RE.search(text)), bool(UNDERGRAD_RE.search(text))
    if m and not d and not u:
        return "masters"
    if d and not m and not u:
        return "doctoral"
    if u and not m and not d:
        return "undergraduate"
    return "ambiguous"


def programme_category(institution: str | None, programme: str | None) -> str | None:
    if institution == "University of Oxford":
        return "Oxford master's"
    if institution == "University of Cambridge":
        return "Cambridge master's"
    if programme and MPP_MPA_RE.search(programme):
        return "MPP-MPA"
    return None


def detect_essay_type(*texts: str) -> str | None:
    hits = {name for name, rx in ESSAY_TYPE_PATTERNS for t in texts if t and rx.search(t)}
    return hits.pop() if len(hits) == 1 else None


def find_admission_year(text: str) -> str | None:
    years = {(m.group(1) or m.group(2)).replace(" ", "") for m in ADMISSION_YEAR_RE.finditer(text)}
    return years.pop() if len(years) == 1 else None


def template_flags(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in TEMPLATE_FLAG_RE.finditer(text)})
