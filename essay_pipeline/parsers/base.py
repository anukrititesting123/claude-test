"""Shared parser types. A parser only locates the title and the article's
text blocks; it never rewrites text."""
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from ..text import clean

BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
ALWAYS_REMOVE = ["script", "style", "noscript", "iframe", "form", "nav", "footer", "aside", "button"]


@dataclass
class Block:
    text: str
    location: str  # human-readable position on the page, e.g. "div.entry-content > p[3]"
    kind: str      # "title" | "heading" | "body"


@dataclass
class ParsedPage:
    url: str
    title: Block | None
    blocks: list[Block] = field(default_factory=list)

    @property
    def content_text(self) -> str:
        parts = ([self.title.text] if self.title else []) + [b.text for b in self.blocks]
        return "\n\n".join(parts)


def _text(el: Tag) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    return clean(el.get_text(""))


def _is_top_level_block(el: Tag, container: Tag) -> bool:
    if el.name == "blockquote" and el.find(list(BLOCK_TAGS - {"blockquote"})):
        return False  # its inner paragraphs are collected individually
    parent = el.parent
    while parent is not None and parent is not container:
        if parent.name in BLOCK_TAGS and not (parent.name == "blockquote" and parent.find("p")):
            return False
        parent = parent.parent
    return True


def select_first(soup: BeautifulSoup, selectors: list[str]) -> tuple[Tag | None, str | None]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el is not None:
            return el, sel
    return None, None


def collect_blocks(elements: list[Tag], label: str, skip: Tag | None = None) -> list[Block]:
    blocks = []
    for el in elements:
        if skip is not None and (el is skip or skip in el.parents):
            continue
        text = _text(el)
        if not text:
            continue
        kind = "heading" if el.name in HEADING_TAGS else "body"
        blocks.append(Block(text, f"{label} > {el.name}[{len(blocks) + 1}]", kind))
    return blocks


def parse_article(html: str, url: str, title_selectors: list[str], content_selectors: list[str],
                  remove_selectors: list[str]) -> ParsedPage:
    soup = BeautifulSoup(html, "html.parser")
    title_el, title_sel = select_first(soup, title_selectors)
    title = Block(_text(title_el), title_sel, "title") if title_el is not None else None
    if title is None and soup.title and soup.title.string:
        title = Block(clean(soup.title.string), "head > title", "title")

    container, content_sel = select_first(soup, content_selectors)
    if container is None:
        return ParsedPage(url, title, [])
    for sel in remove_selectors:
        for el in container.select(sel):
            el.decompose()
    for el in container.find_all(ALWAYS_REMOVE):
        el.decompose()
    elements = [el for el in container.find_all(list(BLOCK_TAGS)) if _is_top_level_block(el, container)]
    return ParsedPage(url, title, collect_blocks(elements, content_sel, skip=title_el))
