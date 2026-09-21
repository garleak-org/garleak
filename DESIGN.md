# Design Direction

**Current direction (2026-09-14, later the same day).** The maintainer asked for the site
to look exactly like arXiv: plain HTML, very little text. The live site now follows arXiv's
own measurements (system sans at 16px, black on white, links #0000EE, a 52px top band, a
grey breadcrumb strip, `dl` listings with bold 18px titles, the `/abs/` metadata table and
submission history, an "Access Paper" column). Garleak's identity is only the gold top
band with the garlic mark and the stage dots. The serif and Plex fonts, cream panels and
hairline-row design below are superseded where they conflict with this. Never copy arXiv's
logo, name, or its maroon or near-black band.

**Revised 2026-09-14.** Changes from the first version, approved that day.

- The page background is white, like arXiv's (`--paper #FFFFFF`). The cream `#F6F3EA`
  becomes `--panel`, a secondary ground for bands and notices, and the palette prose is
  rewritten to match.
- `--gold-wash #F0E8D2` is new, for hover and highlight bands that carry text.
  `--gold-pale` is kept for fills with no text on them.
- Stage ramp v2 replaces the first ramp, which failed its own greyscale and contrast
  checks.
- The listing-row mockups now follow the avoid list (sentence-case type labels, no
  middle dots) and show assistance on two axes, as in `W2 A1 declared`.
- Item 4 of the `/abs/` page covers the two assistance axes, and the version timeline
  opens pre-rendered diffs.
- One light theme, as a decision. The site is static HTML with near-zero JavaScript and
  self-hosted fonts.
- The quality floor describes static pages. Listing pages carry `noindex` along with T0
  and gated content, and invented example records stay under `/example/`.

**Brief:** arXiv's information architecture, a visual identity that is unmistakably not
arXiv's. Text-first, dense, fast, legible at small sizes, readable by researchers who will
scan a hundred titles in a sitting.

The density and restraint are a deliberate requirement of this brief, not a default. Do
not "modernize" it into cards, hero sections, or generous whitespace. Density is the
feature — this audience reads listings, not landing pages.

## What to copy from arXiv

Conventions this audience already knows. Copying them lowers friction and is legally fine.

- `/abs/<id>` page structure: title, authors, abstract, metadata block, download links.
- `/list/<category>/<period>` dense listing format.
- The `v1` / `v2` version convention and version history block.
- Category tree browsing and the daily-new mailing format.
- Keyboard-navigable, near-zero-JS listing pages.

## What never to copy

- The wordmark, logo, or any typographic treatment of the name.
- The maroon (`#b31b1b`) identity color, or anything within reach of it.
- Header and footer layout as a visual composition.
- Any copy implying affiliation, endorsement, or equivalence.

## Palette

Gold occupies the identity role that maroon occupies at arXiv — the header rule, the
mark, the active state. Do not use arXiv's maroon anywhere. Colors are drawn from the
garlic-bulb mark.

```
--paper      #FFFFFF   page background, white like arXiv's
--panel      #F6F3EA   secondary ground for bands and notices, warm cream from the mark
--ink        #1F1B14   body text, warm near-black
--ink-soft   #5C5443   metadata, secondary
--rule       #DCD3BE   hairlines and dividers
--gold       #B8913F   identity (mark, header rule, active state), never text
--gold-wash  #F0E8D2   hover and highlight bands that carry text
--gold-pale  #D9BE7E   fills with no text on them, such as the pct_original bar
--bronze     #6E5218   links and interactive text
--flag       #9A3B16   gated categories, warnings, contested declarations
```

Gold is an identity color, not a text color. At the saturation in the mark it fails AA
contrast on every ground (2.9:1 on white, 2.6:1 on cream), so it never carries body
text, links, or anything that must be read. Links and interactive text use `--bronze`,
which passes on every ground that carries text (7.3:1 on white, 6.6:1 on cream, 6.0:1 on
gold-wash). Gold appears as rules, fills, the mark itself, and the active-state
underline.

`--gold-pale` never has text on it. Bronze drops to 4.0:1 there and ink-soft to 4.1:1,
both under AA. Hover and highlight bands that hold text use `--gold-wash` instead
(bronze 6.0:1, ink-soft 6.1:1), and `--gold-pale` is kept for fills such as the
`pct_original` bar.

The ground is white, like arXiv's, so a page reads as a document before it reads as a
brand. The warmth comes from the accents, meaning the gold of the mark and the header
rule, the cream of `--panel` behind notices and bands, and the warm near-black of the
text. Keep chroma low everywhere except the mark and the stage ramp. Cream plus gold with
no discipline reads as a wedding invitation.

**One theme, on purpose.** Garleak ships a single light theme and paints every color
explicitly. It does not follow the reader's dark-mode setting. A dark palette would need
its own stage ramp and its own contrast checks, and is left for later.

## The stage ramp

The one memorable element on the site. Spend the boldness here and keep everything around
it quiet. A single hue ramping in saturation and darkness as verification deepens, so a
listing page reads as a field of confidence at a glance.

Kept deliberately cool, against the warm identity. Stage is data, not brand — if the ramp
were gold it would read as decoration and collide with the mark.

```
T0 unverified    #908B82   warm grey, deliberately inert
T1 citations     #5C8278
T2 claims        #2F7565
T3 partial repro #006751
T4 reproduced    #00583F   darkest and fullest
```

This is ramp v2. The first ramp (#9C968A, #7FA8A0, #4F8C7E, #2A7A66, #0F6E5C) failed
its own test. Its T1 was lighter than its T0 in greyscale (relative luminance 0.35
against 0.31), so the first two stages swapped, and the T0 and T1 dots fell under the
3:1 floor for graphical objects. v2 keeps the idea (an inert warm grey, then one teal
gaining depth), darkens at every step (luminance 0.26, 0.20, 0.14, 0.10, 0.07), and puts
every dot at 3:1 or better on `--paper` and `--panel`. Stage labels are always set in
`--ink`, and the color only repeats what the numeral and label say. The working is in
`design/NOTES.md`.

Sketches use the same ramp at the N0–N3 positions, with a different glyph — a ring
rather than a filled dot — so the two ladders are never mistaken for each other at a
glance.

Never color-only. Every stage carries its numeral and label. Check it at protanopia and
deuteranopia, and confirm the ramp still reads in greyscale. Test the badge against
`--paper`, `--panel`, and `--gold-wash`. On a `--gold-wash` hover band T0 falls to
2.8:1, which is acceptable only because the numeral and label carry the stage.

## Type

Two families, clearly distinct.

- **Body and titles:** a text serif with a large x-height and real small caps — Source
  Serif 4, Charis SIL, or Spectral. Serif signals scholarly without costume, and it sets
  denser than a sans at the same measure.
- **Interface and data:** IBM Plex Sans for chrome, navigation, badges, and tabular
  metadata. Plex Mono only for identifiers, hashes, and code, where character
  disambiguation genuinely matters.

Set a scale from *Elements of Typographic Style*. Body at 16–17px with generous
line-height for a serif. Line length under 75 characters in abstracts and prose; listing
rows may run wider because they are scanned, not read.

Fonts are self-hosted with the site, so no page waits on a third-party font service or
tells one who is reading.

**Avoid:** all-caps labels, accenting a single word in a heading, an arrow appended to
link text, meta strings joined with middle dots, eyebrow labels above every section.
These are the tells.

## Layout

Left-aligned throughout. No centered text anywhere except the 404. Hairline rules
separate rows; no cards, no shadows, no border-radius above 2px. Structure comes from
alignment and rules, which is what makes dense text scannable.

### Listing rows

Papers and sketches share a row shape but never a listing page.

```
┌────────────────────────────────────────────────────────────┐
│ Paper    4471v3    ● T3  partially reproduced              │
│ Title of the paper set in the serif, two lines maximum     │
│ R. Nakamura    claude-opus-4    W2 A1 declared             │
│ 3 versions    61% original    verified by 2                │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Sketch  8812      ○ N1  no prior work found               │
│ One-line statement of the idea, one line only              │
│ u/kestrel    gpt-5    W3 declared    unclaimed             │
└────────────────────────────────────────────────────────────┘
```

Stage glyph and label lead, because stage is the reason someone reads or skips. The
object type sits left of it in the sans, small — it changes what the stage means, so it
must be read first.

A promoted sketch shows its origin inline, as `promoted from sketch 8812 by u/kestrel`.
A sketch with no analysis shows only its writing code (`W3 declared`), never A0.

### The `/abs/` page

The most important page. Order top to bottom:

1. Title, authors, submitter, responsible operator if an agent submission.
2. Tier block — current tier, verifier names, what each checked, dates.
3. Abstract.
4. The assistance block. Two axes, writing (W0 to W3) and analysis (A0 to A2), each with
   its three signals side by side and visibly separate, in the order declared, predicted
   (with its confidence interval), community median. Never averaged, never collapsed, and
   the two axes never combined into one level. If the submitter has contested a
   prediction, show the contest beside it.
5. Version timeline, a horizontal strip with one mark per version, tier state at each,
   `pct_original` as a filled proportion. Choosing two marks opens their diff, which is
   pre-rendered when the site is built.
6. Model card and provenance link.
7. Downloads, citation string, DOI.

The version timeline is the second place worth spending design effort. It is the thing
that shows, at a glance, that this is a living draft rather than a fixed document — which
is the whole conceptual difference from arXiv.

## Copy

Plain, active, specific. "Verify this version," not "Submit verification." An action
keeps its name through the flow: the button says Verify, the resulting state says
Verified.

Never write "real paper" or "published." Use Verified and Graduated. The tier badge says
what was actually checked; the language must not imply peer review.

Empty states are invitations: a category with no papers says what would belong there and
links to submit, rather than apologizing.

## Quality floor

Responsive to mobile, visible keyboard focus, `prefers-reduced-motion` respected, WCAG AA
contrast throughout. Every page is static HTML built ahead of time, so it works with
JavaScript disabled. `/abs/` pages at T1 and above can be indexed and cited. T0 and gated
content carry `noindex`, and so do listing pages, which mostly show T0 work and change
daily. Invented example records appear only under `/example/`, with a banner on every
page and `noindex`.

**Motion:** essentially none. One exception — the diff viewer may animate the transition
between compared versions, because that motion shows what changed, which is the point.
