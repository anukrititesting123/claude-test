# Phase 1 — Source Discovery Report

Run date: 2026-10-13
Status: **STOPPED for approval. No scrapers have been written.**

## Method and its limits

- Ran the seven query patterns from the brief, plus 14 follow-up queries
  (first-person blogs, WordPress/Blogspot/Medium/Substack, GitHub SOP repos,
  forums, consultancy "essay database" pages).
- **I could not open any candidate page.** The container's network policy
  refuses outbound connections to every candidate host (ox.ac.uk, cam.ac.uk,
  medium.com, wordpress.com, tutorhunt.com, reddit.com, hks.harvard.edu, …).
  Everything below comes from search-engine titles and snippets only.
- So for **every** row, `robots.txt` status, terms of use, whether the essay
  text is on the page, and the exact acceptance sentence are **UNVERIFIED**.
  Nothing here may be scraped until those are checked on the live page.

## Headline finding

Published, per-essay-verifiable, accepted master's essays for these three
categories are **very scarce**. Searches found **no official university or
department page** (Oxford, Cambridge, Blavatnik, HKS, Princeton SPIA, Berkeley
Goldman, Duke Sanford, Cornell, USC Price) that publishes accepted applicants'
essays. Those pages only give guidance. Most "accepted essay" results are
commercial or illustrative, and the rest are drafts posted for feedback.

Realistic yield from currently discovered sources: **0–2 essays**, none of
them for the MPP/MPA category.

## Candidate source table

Key: Accept. = where acceptance is claimed (per essay / site-wide / none);
Est. = estimated in-scope essays; Rec. = recommendation.

### A. Candidates worth verifying (first-person)

| # | URL | Owner / publisher | Type | Category | Acceptance claim (from search snippet only) | Accept. | robots.txt | Terms | Est. | Rec. |
|---|-----|------------------|------|----------|--------------------------------------------|---------|-----------|-------|------|------|
| A1 | https://haikalstheory.wordpress.com/2012/03/03/statement-of-purpose-to-the-university-of-oxford-accepted-msc-in-computer-science/ | Personal WordPress.com blog ("haikalstheory"); author name not yet seen | Personal blog | Oxford master's | Title: "Statement of Purpose to the University of Oxford [accepted: MSc in Computer Science]"; snippet: "Although my application was successful, I did not get a full scholarship" | Per essay (self-reported) | Unverified (blocked) | Unverified (WordPress.com default; author copyright) | 1 | **Approve for verification.** Strongest lead. Programme name is as stated in 2012; do not change it to the current course name. |
| A2 | https://dannymutia.medium.com/my-journey-and-lessons-with-writing-personal-statements-cf21b211c941 | Danny Mutia (Medium) | Personal blog | Oxford master's (MSc Energy Systems stated as completed) | Snippet: author completed "MSc Energy Systems at the University of Oxford" and says they "won spots in several competitive Oxford courses" | Unclear per essay | Unverified (blocked) | Unverified (Medium ToS; author copyright) | 0–2 | **Verify first.** It is not yet known whether full statement text is on the page or which essay went with which programme. Default: needs_review. |

### B. Low-trust or unconfirmed (excluded by default)

| # | URL | Owner / publisher | Type | Why excluded | Est. |
|---|-----|------------------|------|-------------|------|
| B1 | https://www.tutorhunt.com/resource/22499/ | Tutorhunt (tutoring marketplace, user upload) | Commercial / user-generated | Snippet: "My personal statement for MSc Mathematical Physics at Oxford University" (2019). **No acceptance statement seen.** At best needs_review. | 0–1 |
| B2 | https://launchpad.stacyblackman.com/explore/essays/49246375-5605-418b-8a47-e150ec58ae36 | Stacy Blackman Consulting | Commercial essay platform | HKS MPP curriculum-essay prompt. Admission outcome not visible, and the platform may require login. | Unknown |
| B3 | https://elitesop.com/samples/mpp-at-university-of-oxford-chevening-scholar-applicant/ | Elite College SOPs | Commercial SOP writer | Labelled "applicant", not admitted. Likely written or edited by the company. | 0 |
| B4 | https://www.vappingo.com/word-blog/statement-of-purpose-examples-for-top-programs-harvard-mit-oxford-more/ | Vappingo (editing service) | Commercial | "Oxford MSc Public Policy" excerpt with no acceptance confirmation. Excerpt only. | 0 |
| B5 | https://brightlinkprep.com/sample-statement-of-purpose-for-mpp/ | Brightlink Prep | Commercial | Site-wide claim ("accepted to several top programs"), not per essay. The programme appears to be public health, not MPP. | 0 |

### C. Rejected (out of scope, or explicitly not real)

| URL | Reason |
|-----|--------|
| https://vincekotchian.com/personal-statements/mpp-statement-of-purpose/ | Page says: "We wrote these six ourselves as teaching models. The applicants are invented." Fails check (d). |
| admit-lab.com (MPP/MPA/master's example posts), yocket.com, collegepond.com, ambitio.club, g5admissions.com | Hypothetical or illustrative samples, some with placeholders such as "Dr. [Name]". |
| https://blog.accepted.com/the-statement-of-purpose-that-got-me-a-large-scholarship-to-cambridge/ | Gates Cambridge scholarship essay. Search reports it was for a **PhD**, so it is doctoral and out of scope. |
| uniadmissions.co.uk "successful personal statement" pages | Undergraduate (UCAS), so out of scope. |
| GitHub SOP repos (siddu1998/Graduate-Admissions, vsitzmann/phd-master-application-docs, ljfranklin/SOP, ludwigschubert/master-application-stanford) | US CS/engineering MS/PhD, which falls outside all three categories. |
| essayforum.com (Oxford MSc Global Health Science SOP; MPP motivation letters) | Drafts posted for critique. No acceptance stated. |
| GradCafe forums, The Student Room, llm-guide.com threads | Drafts and discussion. No per-essay acceptance found. GradCafe results pages report outcomes but contain no essays. |
| Official pages (ox.ac.uk, bsg.ox.ac.uk, cam.ac.uk departments, hks.harvard.edu, spia.princeton.edu, gspp.berkeley.edu, sanford.duke.edu, Cornell MPA Stories) | Guidance only. No accepted essays published. These are useful only for `prompt_text`/word-limit context, which is not part of the essay corpus. |

## Decisions needed from you

1. **Network access.** Phase 2 and the Phase 1 verification step both require
   fetching the live pages. Allow at least `haikalstheory.wordpress.com` and
   `dannymutia.medium.com` (and their robots.txt) in the environment's
   network settings, or move to a less restricted environment.
2. **Approve or reject A1 and A2** for verification, then scraping if they
   pass.
3. **B1 (Tutorhunt):** should I fetch it to check for an acceptance statement
   (it would go to needs_review if none), or exclude it outright?
4. **Scope reality check.** With only around 1–2 essays found, the pipeline
   would be mostly infrastructure around a nearly empty corpus. Options:
   - (a) Proceed anyway. The pipeline is reusable, and you supply further URLs
     you know of (each one still goes through verification).
   - (b) Run a second discovery round once network access is open, with
     direct site search on Medium, Substack, WordPress, Reddit
     (r/gradadmissions, r/MPP), and LinkedIn articles.
   - (c) Stop here.
