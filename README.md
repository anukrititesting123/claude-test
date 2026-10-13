# Accepted master's essays: curation pipeline

This pipeline collects publicly posted application essays whose source page
**explicitly states** that the author was admitted to one of these:

- an Oxford master's programme,
- a Cambridge master's programme,
- an MPP or MPA programme at any university.

It stores text only when that text exists verbatim at the source, together
with full provenance. Phase 1 findings and the approved sources are in
[`docs/phase1_source_discovery.md`](docs/phase1_source_discovery.md).

## Ground rules enforced in code

- **No invented text.** The essay text, acceptance evidence and prompt are
  copied from page blocks. Check (b) re-confirms that each one appears in the
  cached HTML; the comparison ignores whitespace only.
- **Acceptance is never inferred.** A record passes check (a) only when a
  single sentence or heading on the page contains acceptance language, names
  one institution and a master's programme, and is either the post title or a
  heading, or written in the first person. Hedged or negated sentences such as
  "not", "hope" or "if" never count.
- **Unstated fields stay null.** `admission_year` is only filled from an
  explicit "for 2019 entry"-style phrase inside the acceptance sentence; the
  post date does not count. `word_count` is a count of the stored text, not a
  figure taken from the source.
- **Uncertainty goes to `needs_review`, never to `accepted`.** Pages that are
  clearly doctoral or undergraduate are rejected and logged in `rejections`
  with no essay text stored.
- **Approved sources only.** Only sources with `status: "approved"` in
  `essay_pipeline/sources.json` are fetched. Adding a source needs the
  repository owner's approval.

## Crawling behaviour

- `requests` + BeautifulSoup. Playwright is used only for sources with
  `"needs_js": true`, and it is an optional install.
- robots.txt is checked for every host, including redirect targets.
  - Disallowed → page skipped and logged.
  - robots.txt unreachable or 5xx → page skipped and logged. An unreachable
    robots.txt is never treated as permission.
  - 404 → allowed, following the standard convention.
- One request every 3–5 s per domain, with a descriptive User-Agent. Set
  `ESSAY_PIPELINE_CONTACT` to add contact details.
- Raw HTML is cached in `data/cache/`. `reparse` never touches the network.

## Usage

```bash
pip install -r requirements-dev.txt
export ESSAY_PIPELINE_CONTACT="you@example.org"   # optional, goes in the User-Agent

python -m essay_pipeline run                 # polite fetch + parse + validate + export
python -m essay_pipeline inspect --source haikalstheory_wordpress   # view parsed blocks
python -m essay_pipeline reparse             # re-run from cache after editing sources.json
python -m essay_pipeline export              # regenerate exports only
python -m pytest                             # offline tests (synthetic fixtures)
```

### Steps for each new page (human in the loop)

1. Run `run` to fetch and cache the page. On a first pass every record lands
   in `needs_review`, because the boundaries and terms are not confirmed yet.
2. Read the live page and its terms. Set `terms_status` in `sources.json` to
   one of:
   - `ok_private_study`
   - `reuse_permitted` (only if the terms say so)
   - `prohibited` (all of the source's pages are then skipped and logged)
3. Run `inspect`, then add `essays: [{start_marker, end_marker}]` with
   verbatim snippets from the first and last essay paragraphs. Everything
   outside those markers is stored as author commentary. On pages with several
   essays, also set `acceptance_evidence` for each essay to the exact sentence
   on the page.
4. Run `reparse`. Records that pass checks (a)–(e) become `accepted`.

## Outputs (`data/`, git-ignored)

| File | Contents |
|------|----------|
| `essays.sqlite` | `essays` (the agreed schema) plus the supporting tables below |
| `export/essays_private.csv` | Full text and provenance. **Private study only.** |
| `export/essays_shareable.csv` | Metadata, a 40-word excerpt and the link. Full text only when `terms_status = reuse_permitted`. |
| `export/index.md` | Accepted essays grouped by category → institution → programme → year, plus the review queue with reasons |
| `export/run_report.md` | Sources attempted; essays found, accepted, sent to review and rejected (undergraduate/doctoral); skipped pages with reasons |

### Supporting tables (the `essays` schema is unchanged)

- `essay_provenance`: where the acceptance evidence sits on the page, author
  commentary, review reasons, content hash, reuse flag. The brief asks for
  these, but they are not columns in the record schema.
- `rejections`: out-of-scope pages (metadata only).
- `run_events`: per-run fetch, skip and error log.

## Validation checks

| Check | Fails when |
|-------|-----------|
| (a) | The acceptance sentence is missing or does not name one institution and a master's-level programme |
| (b) | The essay, evidence or prompt text is not found verbatim in the cached HTML |
| (c) | The essay is identical (SHA-256) or near-identical (Jaccard ≥ 0.8 on 5-word shingles) to another record |
| (d) | The article contains "example", "sample", "illustrative", "we wrote", "template", "AI-generated" and similar wording |
| (e) | The programme level is ambiguous. Doctoral or undergraduate → rejected. A master's outside the three categories → rejected. |
| terms | `terms_status` is still `unreviewed` |

## Copyright

The essays belong to their authors. The cache, database and private CSV are
for private study and are git-ignored. Share only `essays_shareable.csv` and
`index.md`.
