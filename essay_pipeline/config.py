"""Runtime settings. Paths can be overridden with ESSAY_PIPELINE_DATA."""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SOURCES_FILE = PACKAGE_DIR / "sources.json"

# Polite crawling: one request every 3-5 seconds per domain.
MIN_DELAY_SECONDS = 3.0
MAX_DELAY_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5

_CONTACT = os.environ.get("ESSAY_PIPELINE_CONTACT", "").strip()
USER_AGENT = (
    "MastersEssayResearchBot/0.1 "
    "(non-commercial private-study research; obeys robots.txt; 1 req/3-5s"
    + (f"; contact: {_CONTACT}" if _CONTACT else "")
    + ")"
)

# Words of excerpt kept in the shareable export.
EXCERPT_WORDS = 40
# Jaccard similarity on 5-word shingles at or above which two essays are
# treated as near-duplicates.
NEAR_DUPLICATE_THRESHOLD = 0.8


def data_dir() -> Path:
    return Path(os.environ.get("ESSAY_PIPELINE_DATA", "data")).resolve()
