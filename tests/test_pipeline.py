import csv
import json
import sqlite3

import pytest

from essay_pipeline import export, pipeline
from essay_pipeline.fetch import PageCache
from essay_pipeline.sources import load_sources
from tests.fixtures import ESSAY_PARAS, medium_page, wordpress_page

OX_TITLE = "Statement of Purpose to the University of Oxford [accepted: MSc in Computer Science]"
MARKERS = {"start_marker": "FIXTURE ESSAY START", "end_marker": "FIXTURE ESSAY END"}


def run_offline(tmp_path, pages: dict[str, str], sources: list[dict]):
    cache = PageCache(tmp_path / "data" / "cache")
    for url, html in pages.items():
        cache.put(url, html, {"url": url, "fetched_at": "2026-10-13T00:00:00+00:00"})
    cfg = tmp_path / "sources.json"
    cfg.write_text(json.dumps({"sources": sources}))
    run_id = pipeline.run(load_sources(cfg), tmp_path / "data", offline=True)
    paths = export.export_all(tmp_path / "data", run_id)
    conn = sqlite3.connect(tmp_path / "data" / "essays.sqlite")
    conn.row_factory = sqlite3.Row
    return conn, paths


def src(sid, urls, parser="haikalstheory_wordpress", terms="ok_private_study", essays=None, status="approved"):
    return {"source_id": sid, "status": status, "parser": parser, "publisher": f"{sid} publisher",
            "source_type": "personal blog", "trust_level": "first-person", "terms_status": terms,
            "license_or_terms_note": "test", "pages": [{"url": u, "essays": essays or []} for u in urls]}


def essay(conn, url):
    return conn.execute("SELECT e.*, p.review_reasons, p.author_commentary, p.acceptance_evidence_location "
                        "FROM essays e JOIN essay_provenance p USING(id) WHERE source_url=?", (url,)).fetchone()


def test_fully_verified_page_is_accepted(tmp_path):
    url = "https://blog.test/ox"
    conn, paths = run_offline(tmp_path, {url: wordpress_page(OX_TITLE, "Here is what I submitted.")},
                              [src("s1", [url], essays=[MARKERS])])
    r = essay(conn, url)
    assert r["review_status"] == "accepted", r["review_reasons"]
    assert r["institution"] == "University of Oxford"
    assert r["programme"] == "MSc in Computer Science"
    assert r["programme_category"] == "Oxford master's"
    assert r["essay_type"] == "statement of purpose"
    assert r["acceptance_evidence"] == OX_TITLE
    assert r["acceptance_evidence_location"] == "h1.entry-title"
    assert r["admission_year"] is None  # not stated => not guessed
    assert r["essay_text"] == "\n\n".join(ESSAY_PARAS)
    assert "Here is what I submitted." in r["author_commentary"]
    assert "Share this" not in r["essay_text"] + r["author_commentary"]

    index = paths["index"].read_text()
    assert "## Oxford master's" in index and "#### MSc in Computer Science" in index
    with paths["shareable_csv"].open() as f:
        row = next(csv.DictReader(f))
    assert "essay_text" not in row and row["essay_text_if_reuse_permitted"] == ""
    assert row["excerpt"].startswith("FIXTURE ESSAY START")


def test_unconfirmed_boundaries_and_terms_go_to_review(tmp_path):
    url = "https://blog.test/ox2"
    conn, _ = run_offline(tmp_path, {url: wordpress_page(OX_TITLE, "Intro.")},
                          [src("s1", [url], terms="unreviewed")])
    r = essay(conn, url)
    reasons = json.loads(r["review_reasons"])
    assert r["review_status"] == "needs_review"
    assert any("essay boundaries not confirmed" in x for x in reasons)
    assert any(x.startswith("terms:") for x in reasons)


def test_no_acceptance_statement_goes_to_review(tmp_path):
    url = "https://blog.test/none"
    conn, _ = run_offline(tmp_path, {url: wordpress_page("My Oxford MSc statement of purpose", "Fingers crossed.")},
                          [src("s1", [url], essays=[MARKERS])])
    r = essay(conn, url)
    assert r["review_status"] == "needs_review"
    assert r["acceptance_evidence"] is None and r["programme"] is None
    assert any("a: acceptance_evidence is empty" == x for x in json.loads(r["review_reasons"]))


def test_doctoral_is_rejected_not_stored(tmp_path):
    url = "https://blog.test/dphil"
    page = wordpress_page("My DPhil application", "I was admitted to the DPhil in Engineering at Oxford.")
    conn, paths = run_offline(tmp_path, {url: page}, [src("s1", [url], essays=[MARKERS])])
    assert essay(conn, url) is None
    rej = conn.execute("SELECT * FROM rejections").fetchone()
    assert rej["outcome"] == "rejected_doctoral"
    assert "Rejected as doctoral: 1" in paths["report"].read_text()


def test_sample_wording_and_duplicates_flagged(tmp_path):
    a, b = "https://blog.test/a", "https://blog.test/b"
    pages = {a: wordpress_page(OX_TITLE, "Original post."),
             b: wordpress_page(OX_TITLE, "A sample I am reposting.")}
    conn, _ = run_offline(tmp_path, pages, [src("s1", [a, b], essays=[MARKERS])])
    rb = json.loads(essay(conn, b)["review_reasons"])
    assert any(x.startswith("d:") and "sample" in x for x in rb)
    assert any(x.startswith("c: exact duplicate") for x in rb)


def test_configured_evidence_must_exist_verbatim(tmp_path):
    url = "https://blog.test/ev"
    conn, _ = run_offline(tmp_path, {url: wordpress_page(OX_TITLE, "Intro.")},
                          [src("s1", [url], essays=[{**MARKERS, "acceptance_evidence": "I got into Oxford's MSc."}])])
    reasons = json.loads(essay(conn, url)["review_reasons"])
    assert any("configured acceptance_evidence not found" in x for x in reasons)


def test_medium_mpp_page(tmp_path):
    url = "https://medium.test/post"
    paras = ["I was admitted to the Master of Public Policy at the University of Exampleton for 2024 entry."] + ESSAY_PARAS
    conn, _ = run_offline(tmp_path, {url: medium_page("My application story", paras)},
                          [src("m1", [url], parser="dannymutia_medium", essays=[MARKERS])])
    r = essay(conn, url)
    assert r["review_status"] == "accepted", r["review_reasons"]
    assert r["programme_category"] == "MPP-MPA"
    assert r["institution"] == "University of Exampleton"
    assert r["admission_year"] == "2024"
    assert "Fixture Author" not in (r["author_commentary"] or "")


def test_unapproved_source_is_never_fetched(tmp_path):
    url = "https://blog.test/x"
    conn, paths = run_offline(tmp_path, {url: wordpress_page(OX_TITLE, "x")},
                              [src("s1", [url], essays=[MARKERS], status="proposed")])
    assert conn.execute("SELECT COUNT(*) FROM essays").fetchone()[0] == 0
    assert "source_not_approved" in paths["report"].read_text()


def test_verbatim_check_catches_altered_text(tmp_path):
    from essay_pipeline.extract import build_candidates
    from essay_pipeline.parsers import PARSERS
    from essay_pipeline.sources import EssayBoundary, Page
    from essay_pipeline.validate import decide

    url = "https://blog.test/v"
    html = wordpress_page(OX_TITLE, "Intro.")
    page = PARSERS["haikalstheory_wordpress"](html, url)
    c = build_candidates(page, Page(url, [EssayBoundary(**MARKERS)]))[0]
    c.essay_text += " An invented extra sentence."
    source = load_sources_stub()
    d = decide(c, page, html, source, "id", [])
    assert any(x.startswith("b: essay text not found verbatim") for x in d.reasons)


def load_sources_stub():
    from essay_pipeline.sources import Source
    return Source("s", "approved", "haikalstheory_wordpress", "p", "personal blog", "first-person",
                  "ok_private_study", "t", [])


@pytest.mark.parametrize("path", ["essay_pipeline/sources.json"])
def test_shipped_sources_file_is_valid(path):
    sources = load_sources(path)
    assert {s.phase1_ref for s in sources} == {"A1", "A2"}
    assert all(s.terms_status == "unreviewed" for s in sources)
