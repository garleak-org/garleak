# citecheck

citecheck reads the reference list of a paper and checks, for every entry, that the cited
work exists and that the identifiers and bibliographic details in the reference agree with
a registry record. It works on BibTeX, compiled `.bbl` files, LaTeX source directories and
tarballs, plain-text reference lists, and arXiv papers fetched by ID.

It is part of [Garleak](https://garleak.org), where it automates the mechanical half of
verification tier T1 ("citations checked"). It is also a standalone tool and needs nothing
from the platform.

> **What citecheck does not check.** citecheck checks existence and metadata. It does
> **not** check whether a cited work supports the claim it is cited for. A reference can be
> real, correctly identified, and still be cited for something it never says. That judgment
> stays with a human reader. The tool prints this statement at the end of every run and
> records it in every JSON report.

## Install

Python 3.11 or newer.

```sh
cd services/citecheck
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
```

The only runtime dependency is `httpx`. citecheck is not on PyPI (see "Status" below).

## Usage

```sh
citecheck refs.bib                          # a BibTeX file
citecheck paper.bbl                         # a compiled bibliography (natbib or biblatex)
citecheck paper/                            # a LaTeX source directory
citecheck source.tar.gz                     # an arXiv-style source tarball
citecheck references.txt                    # one reference per line, or per blank-line block
citecheck --arxiv 2509.09678                # fetch the e-print from arXiv and check its bibliography
citecheck refs.bib --json report.json       # also write the JSON report
citecheck refs.bib --offline                # use the on-disk cache only, no network
citecheck refs.bib --only-flagged           # hide verified entries in the table
```

For a LaTeX source, citecheck uses the `.bbl` when there is one (it is what the paper
actually printed), then the `.bib` files named by `\bibliography{}` or `\addbibresource{}`
(keeping only cited keys), then an inline `thebibliography`.

Exit status is 0 when nothing is flagged, 1 when at least one reference is `unresolved` or
`metadata_mismatch` (or the check could not be completed), and 2 when the input could not be
read. `--exit-zero` forces 0.

Other options: `--resolvers arxiv,crossref,doi.org,openalex,ads,pos` to choose resolvers,
`--no-ads`, `--no-arxiv-search`, `--cache-dir DIR`, `--no-cache`, `--max-refs N`, `-v` to log
every request (URLs only), `-q` for no table.

### Example

```
$ citecheck --arxiv 2509.09678 --only-flagged
   # verdict            conf  reference                  note
   1 not checkable      0.60  Dodelson 2003              No matching record found, but this looks like a k...
  18 wrong id, real ref 0.93  Scolnic et al. 2023        use doi:10.3847/2041-8213/ace978
  19 wrong id, real ref 0.93  Riess 2022                 use doi:10.3847/2041-8213/ac5c5b
  20 wrong id, real ref 0.93  Breuval et al. 2024        use doi:10.3847/1538-4357/ad630e
  21 wrong id, real ref 0.93  Freedman 2021              use doi:10.3847/1538-4357/ac0e95
  25 wrong id, real ref 0.93  Riess 2024                 use doi:10.3847/1538-4357/ad8c21

60 of 66 references verified; 5 real with a wrong identifier; 1 not checkable.
```

Five references in this paper carry DOIs that are wrong. Four do not exist at all
(`ac082c`, `ace280`, `ac361f`, `acbffc`), and one (`ace35e`) belongs to an unrelated paper on
21 cm beam variations. All five works are real, and the arXiv IDs printed next to them are
right. citecheck reports them as wrong identifiers on real references, gives the DOI to use
(each suggestion is looked up and matched before it is offered), and calls none of them
fabricated.

## Verdicts

Every reference gets exactly one verdict from this fixed list. The list is part of the
report schema and will not change within schema version 1.

| verdict | meaning | what to do |
|---|---|---|
| `verified` | A printed identifier resolves and the metadata agree. For a reference with no identifier, a registry record was found by search and agrees. | Nothing. |
| `id_mismatch_real_ref` | An identifier is wrong, does not resolve, or points to a different work, but the real work was found. `corrected_ids` gives the identifier to use. | Fix the identifier. The reference itself is fine. |
| `metadata_mismatch` | The identifier resolves, but the record's title, authors, year, or volume/page disagree materially, and no better match exists. | Look at it. Either the identifier or the reference text is wrong. |
| `unresolved` | Nothing matching was found anywhere consulted. | Check it by hand. It may be fabricated. It may also be a real work that the registries do not index. |
| `not_checkable` | There is nothing public to check (private communication, in preparation, unpublished), or it is a kind of work the registries cover poorly (books, theses, software, proceedings, websites) and no match turned up. | Check by hand if it matters. |

Each verdict carries a `confidence` between 0 and 1 (with a `high`/`medium`/`low` label), a
plain-language `reason`, the matched record, the component similarity scores (title,
authors, year, volume/page), and the full evidence trail: which resolver was asked what,
and what it said.

There is no "fabricated" verdict. Registries have gaps, parsers make mistakes, and a wrong
accusation costs the accused far more than a missed fabrication costs anyone. citecheck
reports what it found and how sure it is, and leaves the conclusion to a person. When a
resolver fails or a cache entry is missing, the reference is marked `incomplete` and is not
flagged.

## How it decides

1. **Identifiers first.** Each DOI, arXiv ID, and ADS bibcode in the reference is looked
   up and the returned record is compared with the reference.
2. **A DOI missing from Crossref is not a missing DOI.** DataCite (arXiv, Zenodo, data
   archives), mEDRA, JaLC and other agencies register DOIs that Crossref never sees.
   citecheck asks the global DOI handle system (doi.org) and reads the record through
   content negotiation before it concludes anything.
3. **Known failure classes are repaired.** DOIs with pasted URL tails, doubled letters in a
   journal slug (`mmnras` for `mnras`), and Proceedings of Science DOIs that are not
   registered with doi.org even though the contribution is online at pos.sissa.it.
4. **Metadata search as a fallback.** When an identifier fails, points at a different work,
   or is absent, the reference is searched by author, year, title, journal, volume, and
   page in NASA ADS (if a token is present), Crossref, OpenAlex, and arXiv. A match found
   this way turns a failed identifier into `id_mismatch_real_ref`, never `unresolved`.
5. **Tolerant comparison.** Matching allows journal year versus arXiv posting year, accents
   and transliteration, collaboration author lists, compound surnames, journals such as JCAP
   and JHEP that print the issue where the volume usually goes, and bibliography styles that
   print no title (most astronomy styles). Every component score is reported.
6. **ADS bibcodes are hints, not evidence against a reference.** The mnras style links every
   entry to ADS, and those bibcodes go stale (a preprint bibcode becomes an alternate once
   the journal version appears, and `.tmp.` in-press bibcodes are replaced). A bibcode is
   checked only when no DOI or arXiv ID is printed, and one that ADS no longer knows simply
   sends the reference to the metadata search.

## Resolvers, rate limits, and the cache

| resolver | used for | spacing |
|---|---|---|
| arXiv API | arXiv IDs (batched, 40 per request) and title search | 1 request per 3 s, shared with e-print downloads |
| DataCite | fallback for arXiv IDs (every arXiv paper has a 10.48550 DOI) | 0.5 s |
| Crossref | DOIs (batched) and bibliographic search | 0.25 s |
| doi.org | DOI handles, registration agency, content negotiation | 0.3 s |
| OpenAlex | DOIs, search by volume/page and by title | 0.2 s |
| NASA ADS | DOIs, arXiv IDs, bibcodes, search by journal/volume/page | 0.4 s, only with a token |
| pos.sissa.it | Proceedings of Science contributions | 1 s |

When the arXiv API or OpenAlex search starts refusing requests (HTTP 429), citecheck stops
asking it for the rest of the run and relies on the other sources, rather than retrying.

Responses are cached on disk (default `~/.cache/citecheck`, or `$XDG_CACHE_HOME/citecheck`,
or `$CITECHECK_CACHE_DIR`). Positive answers are kept indefinitely. "Not found" answers
expire after seven days, since new records do get registered. `--offline` uses the cache only.

Environment variables:

- `CITECHECK_MAILTO` sets the contact address sent to Crossref and OpenAlex for their polite
  pools. There is no default address, and none is sent when it is unset.
- `ADS_TOKEN`, or the file `~/.ads/dev_key`, enables NASA ADS. The token is sent only in the
  `Authorization` header. It is never printed, logged, cached, or written into a report.
- `OPENALEX_API_KEY` is optional and handled the same way.

## JSON report (schema v1)

`--json out.json` writes a report that validates against
[`schema/report.v1.json`](schema/report.v1.json) (JSON Schema 2020-12). Version 1 is
stable. Later 1.x releases may add optional fields but will not remove or rename fields or
change the verdict list. The top level holds:

- `schema_version`, `tool`, `generated_at`, `input`, `settings`, `network` (request counts)
- `summary` with per-verdict `counts`, `flagged_indices` (references that need a human),
  `corrected_indices`, `incomplete_indices`, a one-line `headline`, and `prescreen`
- `references`, one object per reference with `raw`, `parsed`, `verdict`, `confidence`,
  `reason`, `corrected_ids`, `matched_record`, `scores`, `incomplete`, and `evidence`
- `disclaimer`, the statement about claim support

`summary.prescreen.status` is `pass`, `review`, or `incomplete`, and
`summary.prescreen.claim_support_checked` is always `false`.

## Python API

```python
from citecheck.checker import Checker
from citecheck.http import Cache, Http, default_cache_dir
from citecheck.parsers import load_path
from citecheck.resolvers import build_resolvers

http = Http(Cache(default_cache_dir()))
refs = load_path("refs.bib").refs
for r in Checker(build_resolvers(http)).check_all(refs):
    print(r.reference.index, r.verdict.value, r.reason)
```

## How it fits Garleak tier T1

T1 means "every reference exists and says what is claimed". The first half is mechanical
and citecheck does it. The second half is reading, and a verifier does it. On the platform,
citecheck runs in the automated pre-screen: `prescreen.status == "pass"` lets a paper
through without a human looking at its citations for existence, `review` sends the flagged
references to a person, and the per-reference evidence is shown to the verifier. A T1 badge
still requires a human to confirm that the references say what the paper claims they say.

## Status

Version 0.1.0. Not yet released. The name `citecheck` is already taken on PyPI by an
unrelated project, so a release will need a different distribution name (the import name
can stay `citecheck`).

Known limits. The free-text parser is tuned on astronomy and physics styles (mnras,
aasjournal, JHEP, revtex, APA-like lists) and can miss titles in unusual styles. Book and
thesis coverage in the registries is thin, so those usually end up `not_checkable`.
Coverage outside physics and astronomy has not been measured yet.

## Tests and benchmark

```sh
.venv/bin/python -m pytest              # offline, replays recorded HTTP fixtures
.venv/bin/python -m pytest --network    # adds live tests
.venv/bin/python tests/record_fixtures.py --fresh   # re-record fixtures after changing queries
.venv/bin/python bench/run_bench.py     # live benchmark, see bench/RESULTS.md
```

The offline suite includes the arXiv:2509.09678 wrong-suffix regression and a set of
synthetic fabricated references (plausible titles, realistic names, invented DOIs and arXiv
IDs), none of which may ever come out `verified`.

## Credit

citecheck grew out of the citation-integrity audit in
[llm-in-astro-ph](https://github.com/seratsaad/llm-in-astro-ph) (Serat Saad), which resolved
22,547 cited arXiv identifiers from 2,532 astro-ph papers and found no fabricated
references. Its lessons are built in here. Every DOI missing from Crossref in its sample
turned out to be real and registered elsewhere. Wrong identifiers on real references are a
different thing from fabrication. Journal-string typos and unregistered PoS DOIs are real
references too.

## License

AGPL-3.0-or-later, matching the Garleak repository.
