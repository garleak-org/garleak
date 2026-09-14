# garleak-site

The archive library and static-site generator for [Garleak](https://garleak.org).

- `garleak_archive` loads the records in `archive/` (format in
  [`archive/FORMAT.md`](../archive/FORMAT.md)), validates them against SPEC.md, and
  computes stages, `pct_original` and diffs. It knows nothing about HTML.
- `garleak_site` turns an archive into plain HTML with Jinja templates, one CSS file built
  from [`design/tokens.css`](../design/tokens.css), and self-hosted fonts.

Code under AGPL-3.0-or-later. Python 3.12.

## Setup

```sh
cd site
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
```

Use the venv in this directory, not a shared one.

## Commands

```sh
.venv/bin/pytest                                             # all tests
.venv/bin/garleak-archive validate ../archive ../archive-example
.venv/bin/garleak-archive guard --base origin/main ../archive ../archive-example
.venv/bin/garleak-archive hash ../archive-example/papers/4471/v1.0

.venv/bin/garleak-site build --out _site                     # build the site
.venv/bin/garleak-site build --out _site --date 2026-09-14   # with a fixed build date
.venv/bin/garleak-site check _site                           # links, markup, wording, noindex, /example/ boundary
.venv/bin/garleak-site serve                                 # build, then serve at http://127.0.0.1:8000
.venv/bin/garleak-site serve --no-build --port 8080
```

Search is optional. After a build, `npx --yes pagefind@1 --site _site` writes the index,
and `/search/` loads it when it is there. Without it, the site still builds and works.

CI runs the same steps in [`.github/workflows/site.yml`](../.github/workflows/site.yml):
validate, guard, pytest, build, Pagefind, check, then deploy to GitHub Pages from `main`.

## What the build writes

Settings are in [`config.yaml`](config.yaml) (`site_url`, `repo`, `contact`, `state`, and
the paths to the two archives, the tokens and SPEC.md).

| Path | What |
|---|---|
| `/` | What Garleak is and is not, the category tree with counts or invitations |
| `/list/<cat>/new/`, `/list/<cat>/<yyyy-mm>/` | Paper listings, new papers and new versions |
| `/scratch/list/<cat>/new/`, `/scratch/list/<cat>/<yyyy-mm>/` | Scratch listings |
| `/abs/<n>/`, `/abs/<n>v<M>/`, `/abs/<n>v<M>.<m>/` | A paper: current, series and exact versions |
| `/abs/paper:<id>/` | Redirects for the identifier form SPEC.md prints in citations |
| `/diff/<n>/<a>..<b>/` | A word diff for every pair of visible versions |
| `/text/<n>v<M>.<m>/`, `/src/<n>v<M>.<m>/`, `/pdf/<n>v<M>.<m>.pdf` | Full text, source files, stamped PDF |
| `/scratch/<n>/` | A scratch, with `/scratch/<n>v1.0/` redirecting to it |
| `/stages/`, `/about/`, `/spec/`, `/verify/`, `/submit/`, `/citecheck/`, `/terms/`, `/moderation/`, `/search/`, `/graduated/` | Content pages |
| `/list/<cat>/feed.xml`, `/scratch/list/<cat>/feed.xml` | Atom feeds, real archive only |
| `/sitemap.xml`, `/robots.txt`, `/404.html`, `/CNAME` | |
| `/example/...` | The example archive, with a banner and `noindex, nofollow` on every page |

Rules the build and `check` enforce:

- Invented records appear only under `/example/`, never in the sitemap or the feeds, and
  the build refuses to place an example archive at the root.
- T0 versions, gated content below T1, listings and diffs carry `noindex`.
- Gated papers below T1 get a page that says so, with no title or text, and no source,
  full text or diff is written for them.
- Every issued identifier has a page. The 404 page says when one was never issued.
- A version with `paper.pdf` gets a stamped copy with a notice on every page.
- Pages work with JavaScript disabled. Three small scripts add the two-click compare on
  the version timeline, the identifier message on the 404 page, and the search UI.

## Layout

```
garleak_archive/   ids, models, loader, schema, rubrics, stages, assistance, pct, diff,
                   hashing, immutability, validate, schemas/*.schema.json
garleak_site/      build, view, markup, pdfstamp, checks, templates/, static/
tests/             pytest
scripts/           contrast.py (palette contrast table), make_mark.py (mark and favicons)
```
