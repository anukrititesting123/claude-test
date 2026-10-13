"""Parser for Phase 1 source A1 (haikalstheory.wordpress.com).

Selectors follow standard WordPress.com theme markup. They have NOT yet been
checked against the live page (network access was blocked during Phase 1):
run `python -m essay_pipeline inspect --source haikalstheory_wordpress` on the
cached HTML and adjust before trusting the output.
"""
from .base import ParsedPage, parse_article

NAME = "haikalstheory_wordpress"

TITLE_SELECTORS = ["h1.entry-title", "h2.entry-title", "h1.post-title", ".post h2", "article h1"]
CONTENT_SELECTORS = ["div.entry-content", "div.post-content", "div.entry", "article"]
REMOVE_SELECTORS = [
    ".sharedaddy", ".jp-relatedposts", "#jp-post-flair", ".wpcnt", ".wordads-ad-wrapper",
    ".post-likes-widget-placeholder", ".sd-sharing-enabled", ".wp-block-buttons",
]


def parse(html: str, url: str) -> ParsedPage:
    return parse_article(html, url, TITLE_SELECTORS, CONTENT_SELECTORS, REMOVE_SELECTORS)
