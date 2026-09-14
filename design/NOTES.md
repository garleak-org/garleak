# Design notes

Decisions and proposed changes to DESIGN.md that came out of building the prototype
(`design/prototype/index.html`). DESIGN.md itself is unchanged; these are proposals
until accepted.

## 1. Stage ramp v2 (proposed)

The DESIGN.md ramp fails its own greyscale test. T1 `#7FA8A0` has relative luminance
0.351, lighter than T0 `#9C968A` at 0.307, so in greyscale the first two stages swap.
T0 and T1 dots are also 2.65:1 and 2.36:1 on `--paper`, below the 3:1 WCAG floor for
graphical objects.

Ramp v2 keeps the idea (inert warm grey, then one teal hue gaining chroma and depth) and
fixes both problems. Luminance targets are evenly spaced in log(Y + 0.05) between the
3:1 limit and a dark teal; lightness solved in OKLCH.

| Stage | DESIGN.md | Y | on paper | v2 | Y | on paper |
|---|---|---|---|---|---|---|
| T0 / N0 | #9C968A | 0.307 | 2.65 | #908B82 | 0.260 | 3.05 |
| T1 / N1 | #7FA8A0 | 0.351 | 2.36 | #5C8278 | 0.196 | 3.85 |
| T2 / N2 | #4F8C7E | 0.219 | 3.51 | #2F7565 | 0.143 | 4.91 |
| T3 / N3 | #2A7A66 | 0.154 | 4.65 | #006751 | 0.103 | 6.19 |
| T4 | #0F6E5C | 0.120 | 5.56 | #00583F | 0.073 | 7.67 |

Stage labels are always set in `--ink`. The color is redundant with the numeral and label,
as DESIGN.md requires.

## 2. Gold-pale cannot carry links

On `--gold-pale`, bronze drops to 4.03:1 and ink-soft to 4.14:1, both under AA. Added
`--gold-wash #F0E8D2` for hover and highlight bands (bronze 5.96:1, ink-soft 6.13:1).
`--gold-pale` is kept for fills with no text on them, such as the `pct_original` bar.

## 3. Listing-row mockup vs. the "avoid" list

The DESIGN.md row mockups use all-caps type labels (`PAPER`) and middle-dot meta strings,
both of which the same document lists as tells to avoid. The prototype uses sentence-case
"Paper" and "Scratch" in small sans, and separates metadata by spacing alone.

## 4. Row layout

Stage and object type sit in a fixed 14rem gutter to the left of the title, so stage
glyphs line up down the page and a listing reads as a column of confidence. On narrow
screens the gutter folds into a single line above the title.

## 5. Single theme

DESIGN.md defines one warm light palette, so the prototype commits to it and paints every
color explicitly. A dark palette would need its own ramp check and is left as an open item.

## 6. Assistance taxonomy is not ordinal (spec issue, not only design)

L0-L4 mixes two axes: who wrote the prose (L0 prompt-only, L2 model-drafted, L3
model-polished) and who did the analysis (L4). A "median of reader votes" and a
"confidence interval" on the prediction both assume an ordered scale, and this one isn't
ordered. The prototype's example shows the problem: the classifier predicts L4 from text
alone, and the submitter's contest is really about the analysis axis. Consider two
declared fields (prose: L0-L3, analysis: human / shared / model), each ordinal.

## 7. The static site (2026-09-14)

Notes from porting the prototype to the generator in `site/garleak_site/`.

- The build prepends `design/tokens.css` to `site/garleak_site/static/site.css` and serves
  the result as the one stylesheet, `/static/garleak.css`. Components use tokens only.
- `--s0` is back at `#908B82`, the approved ramp v2 value. An earlier edit had darkened it
  to `#86817A` to hold 3:1 on `--gold-wash`, which DESIGN.md already accepts at 2.8:1
  because the numeral and label always carry the stage.
- `--rule-strong #8C8373` is kept for the borders of form controls, which need 3:1 on
  their ground. It is not in DESIGN.md's palette table.
- Notices, invitations and the example banner sit on `--panel` with a gold left rule.
  Row and timeline hover bands use `--gold-wash`, as the prototype does.
- The version timeline marks are links to each version. A small script adds a Compare
  button under each mark and opens the pre-rendered diff after two picks. Without the
  script, every pair of versions is listed as links under the timeline.
- Assistance shows one row of three signals per axis, writing then analysis. The scale
  strip has four cells for writing and three for analysis.
- In the verification table, rows cleared by a major version are muted whether they
  passed or failed, so failed checks keep the same prominence as passed ones.
- The 404 page is the only centered page.
- Fonts are self-hosted woff2 (Source Serif 4 variable, IBM Plex Sans 400/500/600, IBM
  Plex Mono 400/500) with their OFL texts in `site/garleak_site/static/fonts/`.
