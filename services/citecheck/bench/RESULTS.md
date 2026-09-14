# citecheck benchmark results

This is a small live run, meant to catch gross problems and to give a first number for each
of the two error rates that matter. It is not a validation study, and the real-paper numbers
are in-sample (see "How these numbers were reached" below).

## What was run

`bench/run_bench.py` does two things.

1. It fetches the arXiv source of eight real astro-ph papers, reads the bibliography the
   paper actually printed (the `.bbl` when present), and checks every reference. The papers
   span the JHEP, AAS, A&A, MNRAS, and OJA bibliography styles, so some lists are full of
   DOIs and arXiv IDs and others print only author, year, journal, volume, and page.
2. It checks 48 invented references. Forty come from a fixed seed (a plausible title built
   from astronomy phrases, one to four realistic surnames, a real journal with a plausible
   volume and page, and either a fake DOI in that journal's DOI pattern, a well-formed arXiv
   ID, an out-of-range arXiv ID, or no identifier). Eight are the hand-written fakes in
   `tests/fixtures/fabricated.bib`.

Two numbers come out of it.

- **False-fabricated rate.** The share of references in the real papers that come out
  `unresolved`, the verdict that means "could be fabricated". The llm-in-astro-ph audit found
  no fabricated references among 22,547 cited arXiv IDs, so every `unresolved` verdict on a
  real paper counts as a tool miss unless inspection shows otherwise.
- **Recall on fakes.** The share of invented references that are flagged, meaning
  `unresolved` or `metadata_mismatch`. The number that must stay at zero is the count of
  invented references that come out `verified` or `id_mismatch_real_ref`.

Resolvers were arXiv (with DataCite as fallback), Crossref, doi.org, OpenAlex, NASA ADS (a
token was available on the machine), and pos.sissa.it. Run on 2026-09-14 with citecheck 0.1.0.

## Results

### Real papers

| arXiv | source used | refs | verified | id_mismatch_real_ref | metadata_mismatch | unresolved | not_checkable |
|---|---|---:|---:|---:|---:|---:|---:|
| 2509.09678 | .bbl (JHEP style) | 66 | 60 | 5 | 0 | 0 | 1 |
| 2106.15656 | .bbl (AAS) | 117 | 116 | 0 | 0 | 0 | 1 |
| 2112.04510 | .bbl (AAS) | 170 | 164 | 0 | 0 | 0 | 6 |
| 1807.06209 | inline thebibliography (A&A) | 379 | 375 | 0 | 0 | 0 | 4 |
| 2310.01112 | .bbl (MNRAS) | 127 | 125 | 0 | 0 | 0 | 2 |
| 2512.19652 | .bib | 83 | 83 | 0 | 0 | 0 | 0 |
| 2603.11015 | .bbl (MNRAS) | 51 | 49 | 0 | 0 | 0 | 2 |
| 2512.01270 | .bib | 51 | 51 | 0 | 0 | 0 | 0 |
| **total** | | **1044** | **1023** | **5** | **0** | **0** | **16** |

False-fabricated rate: **0 of 1044 (0.0%)**. Metadata-mismatch rate: 0 of 1044. The five
`id_mismatch_real_ref` verdicts are all genuine and are described below.

The 16 `not_checkable` references are three books, two VizieR catalogs, two archive web
pages, two "in prep." citations, a conference talk, an ASP proceedings chapter, a software
record, lecture notes, an STScI technical report, and two 2026 citations with neither a
volume nor an identifier. None of them is a tool miss in the sense that matters here: none
was accused of being fabricated. A reader who wants them confirmed has to look by hand.

### Synthetic fabricated references

| identifier mode | n | verified | id_mismatch_real_ref | metadata_mismatch | unresolved | not_checkable |
|---|---:|---:|---:|---:|---:|---:|
| fake DOI in a real journal's pattern | 11 | 0 | 0 | 5 | 6 | 0 |
| well-formed arXiv ID | 7 | 0 | 0 | 7 | 0 | 0 |
| out-of-range arXiv ID | 7 | 0 | 0 | 0 | 7 | 0 |
| no identifier | 15 | 0 | 0 | 0 | 15 | 0 |
| hand-written fixtures | 8 | 0 | 0 | 0 | 8 | 0 |
| **total** | **48** | **0** | **0** | **12** | **36** | **0** |

All 48 are flagged (recall 100%), and none is verified. The split between the two flagged
verdicts is informative. An invented identifier that happens to exist (every well-formed
arXiv ID in the set, and five of the eleven DOIs) points at an unrelated real paper, so the
reference gets `metadata_mismatch`. An identifier that does not exist, or no identifier at
all, gets `unresolved`.

### Cost

From an empty cache the run made about 600 requests in 440 s of wall time: ADS 341,
OpenAlex 115, Crossref 95, doi.org 20, DataCite 20, arXiv e-print downloads 8, and one call
to the arXiv API. That call was refused (HTTP 429), and the arXiv lookups ran through
DataCite for the rest of the run. A repeat run is served from the cache in about a second.
ADS carries most of the load because astronomy styles print few identifiers, and each
identifier-free reference needs a metadata search.

## Finding worth keeping: five wrong DOIs in arXiv:2509.09678

The original audit sampled DOIs and caught two wrong suffixes in this paper. Checking every
reference finds five, all on real ApJ and ApJL papers whose arXiv IDs are printed correctly
alongside.

| ref | printed DOI | what it is | correct DOI |
|---|---|---|---|
| Freedman 2021, ApJ 919, 16 | 10.3847/1538-4357/ac082c | not registered anywhere | 10.3847/1538-4357/ac0e95 |
| Scolnic et al. 2023, ApJL 954, L31 | 10.3847/2041-8213/ace280 | not registered anywhere | 10.3847/2041-8213/ace978 |
| Riess et al. 2022, ApJL 934, L7 | 10.3847/2041-8213/ac361f | not registered anywhere | 10.3847/2041-8213/ac5c5b |
| Breuval et al. 2024, ApJ 973, 30 | 10.3847/1538-4357/acbffc | not registered anywhere | 10.3847/1538-4357/ad630e |
| Riess et al. 2024, ApJ 977, 120 | 10.3847/1538-4357/ace35e | a different paper (Kim et al. 2023, 21 cm beam variations, ApJ 953, 136) | 10.3847/1538-4357/ad8c21 |

Each correction was checked against Crossref by hand as well as by the tool. The pattern
(right journal prefix, wrong six-character suffix) looks like identifiers that were guessed
or garbled while the rest of the reference was copied correctly. That is exactly the case
the `id_mismatch_real_ref` verdict exists for. Calling these references fabricated would
have been wrong.

## How these numbers were reached

The first full pass over these same eight papers was not clean, and each miss was fixed
before the numbers above were produced. So the real-paper rates are in-sample and should be
read as optimistic until citecheck is run on papers it was not tuned on. What the first
pass got wrong:

- **19 false `id_mismatch_real_ref` verdicts** (16 in the MNRAS paper 2310.01112, one each in
  2512.19652, 2603.11015, and 2512.01270). The mnras style links every entry to ADS, and
  citecheck treated the bibcode in that link as a printed identifier. Preprint bibcodes
  become alternates once ADS merges the journal version, and `.tmp.` in-press bibcodes are
  replaced, so perfectly good references were reported as carrying a wrong identifier. Now
  bibcodes are looked up through `identifier:` (which matches alternates), `.tmp.` bibcodes
  are ignored, and a bibcode is checked only when no DOI or arXiv ID is printed.
- **1 false `unresolved`**, Cardona, Kunz & Pettorino 2017, JCAP 3, 056. JCAP uses the year
  as its volume and references print the issue in its place, so the volume never matched.
  Matching now accepts the record's issue (or year) as the printed volume.
- **Journals and proceedings that were not parsed.** Journal names containing "and"
  (Communications in Applied Mathematics and Computational Science) were mistaken for author
  lists, and "in ASP Conference Series, Vol. N, ..., page" was not read at all. A first
  attempt at the author-list filter then broke abbreviated names such as "J. Mach. Learn.
  Res.", which surfaced as one more false `unresolved` (Hoffman & Gelman 2014). That
  reference also exposed two index-data problems: OpenAlex spells the first author "Homan"
  (the "ff" ligature was lost in PDF extraction), and index years sometimes follow the
  arXiv posting rather than the journal. Surname matching now tolerates dropped ligatures,
  and first author (or a cited co-author) plus year, volume, and page together count as a
  match.
- **Politeness.** ADS originally ran up to three queries per reference. It now stops at the
  first query that returns records and leaves any further looking to the other resolvers.

Every one of these was a reference the tool could not confirm, which is what the fairness
rule is for. None of them ever came out as a confident accusation. But a reader of a report
with 19 spurious "wrong identifier" flags would have lost trust in the tool, so they
mattered.

## Limits of this benchmark

- Eight papers, all astronomy, all by authors who build bibliographies from ADS. Other
  fields will have fewer identifiers, more books, and styles the parser has not seen.
- The synthetic fakes are made by a simple generator. LLM-fabricated references can be more
  adversarial, for instance a real first author with an invented title at a real volume and
  page, and those are not in this set.
- Recall on identifier-free fakes depends on the search indexes answering. When OpenAlex
  throttles title search, citecheck stops using it for the rest of the run and relies on ADS
  and Crossref, which is enough for astronomy but may not be elsewhere.

To reproduce: `python bench/run_bench.py` (add `--no-ads` to run without an ADS token). The
per-paper JSON reports land in `bench/out/`, and `bench/RESULTS.generated.md` holds the
machine-written tables.
