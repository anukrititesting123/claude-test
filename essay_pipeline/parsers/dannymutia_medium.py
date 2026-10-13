"""Parser for Phase 1 source A2 (dannymutia.medium.com).

Medium marks body paragraphs with `data-selectable-paragraph`; when that
attribute is missing we fall back to the article's block elements. Not yet
checked against the live page -- inspect the cache before trusting output.
"""
from bs4 import BeautifulSoup

from .base import ParsedPage, collect_blocks, parse_article, select_first, _text, Block

NAME = "dannymutia_medium"

TITLE_SELECTORS = ["article h1[data-testid='storyTitle']", "article h1", "h1"]
CONTENT_SELECTORS = ["article section", "article"]
REMOVE_SELECTORS = ["[data-testid='authorName']", "[aria-label='responses']", "figure figcaption"]


def parse(html: str, url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    paragraphs = article.select("[data-selectable-paragraph]") if article else []
    if not paragraphs:
        return parse_article(html, url, TITLE_SELECTORS, CONTENT_SELECTORS, REMOVE_SELECTORS)
    title_el, title_sel = select_first(soup, TITLE_SELECTORS)
    title = Block(_text(title_el), title_sel, "title") if title_el is not None else None
    blocks = collect_blocks(paragraphs, "article [data-selectable-paragraph]", skip=title_el)
    if title and blocks and blocks[0].text == title.text:
        blocks = blocks[1:]
    return ParsedPage(url, title, blocks)
