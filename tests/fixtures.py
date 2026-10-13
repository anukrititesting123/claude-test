"""SYNTHETIC TEST FIXTURES -- NOT REAL ESSAYS.

Every page below was written for the test suite to exercise the parsers and
checks. None of it is, or is presented as, an applicant's real essay, and it
must never be loaded into the repository database outside tests.
"""

ESSAY_PARAS = [
    "FIXTURE ESSAY START. Placeholder paragraph one used only by the automated tests of this pipeline.",
    "Placeholder paragraph two continues with neutral filler words so that the shingle comparison has enough material to work on reliably.",
    "Placeholder paragraph three ends here. FIXTURE ESSAY END.",
]


def wordpress_page(title: str, intro: str, essay_paras=ESSAY_PARAS, outro: str = "Thanks for reading.") -> str:
    body = "".join(f"<p>{p}</p>" for p in essay_paras)
    return f"""<!doctype html><html><head><title>{title} | test blog</title></head>
<body><nav><p>Home About</p></nav>
<article class="post"><h1 class="entry-title">{title}</h1>
<div class="entry-content">
<p>{intro}</p>
{body}
<p>{outro}</p>
<div class="sharedaddy"><p>Share this: Twitter Facebook</p></div>
</div></article>
<footer><p>Blog at WordPress.com.</p></footer></body></html>"""


def medium_page(title: str, paras: list[str]) -> str:
    ps = "".join(f'<p class="pw-post-body-paragraph" data-selectable-paragraph="">{p}</p>' for p in paras)
    return f"""<!doctype html><html><head><title>{title}</title></head><body>
<article><div><section>
<h1 data-testid="storyTitle" data-selectable-paragraph="">{title}</h1>
<p data-testid="authorName">Fixture Author</p>
{ps}
</section></div></article></body></html>"""
