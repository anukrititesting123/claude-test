"""Text helpers. Nothing here alters wording -- only whitespace/Unicode form."""
import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"“‘(\[]?[A-Z])")


def clean(s: str) -> str:
    """NFC-normalise and collapse runs of whitespace to one space."""
    return _WS.sub(" ", unicodedata.normalize("NFC", s)).strip()


def squash(s: str) -> str:
    """Remove all whitespace; used for whitespace-insensitive verbatim checks."""
    return _WS.sub("", unicodedata.normalize("NFC", s))


def sentences(s: str) -> list[str]:
    return [p for p in (x.strip() for x in _SENTENCE_SPLIT.split(clean(s))) if p]


def word_count(s: str) -> int:
    return len(clean(s).split())


def content_hash(s: str) -> str:
    return hashlib.sha256(clean(s).lower().encode("utf-8")).hexdigest()


def shingles(s: str, k: int = 5) -> set[str]:
    words = re.findall(r"\w+", clean(s).lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def excerpt(s: str, n_words: int) -> str:
    words = clean(s).split()
    return " ".join(words[:n_words]) + (" …" if len(words) > n_words else "")
