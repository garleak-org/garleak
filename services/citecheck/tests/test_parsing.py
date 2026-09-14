# SPDX-License-Identifier: AGPL-3.0-or-later
"""Parser tests. No network."""

import io
import tarfile

from citecheck.parsers import load_bbl, load_bibtex, load_path, load_plaintext, parse_bibtex
from citecheck.parsers.sources import load_text
from citecheck.textutil import latex_to_text


def test_latex_accents_and_markup():
    assert latex_to_text(r"M.~{Garc{\'\i}a Mar{\'\i}n}") == "M. García Marín"
    assert latex_to_text(r"J.B.~Mu{\~n}oz") == "J.B. Muñoz"
    assert latex_to_text(r"\emph{{The Mid-infrared Instrument}}") == "The Mid-infrared Instrument"
    assert latex_to_text(r"{\bfseries 919} (2021) 16") == "919 (2021) 16"
    assert latex_to_text(r"Schr\"{o}dinger \& Sons") == "Schrödinger & Sons"


def test_bibtex_macros_concat_nesting():
    text = r"""
    @string{apjx = "Astrophysical Journal"}
    @comment{ignored {nested} }
    @article{Key1,
      author = {Garc{\'\i}a, M. and {Planck Collaboration} and van der Berg, Ann},
      title = {{The {CMB} at small scales}},
      journal = apjx # " Letters",
      year = 2020, month = jan,
      pages = "L7--L9",
    }
    """
    es = parse_bibtex(text)
    assert len(es) == 1
    f = es[0]["fields"]
    assert f["journal"] == "Astrophysical Journal Letters"
    assert f["month"] == "jan"
    refs = load_bibtex(text)
    r = refs[0]
    assert r.title == "The CMB at small scales"
    assert r.authors[0] == "García"
    assert r.authors[-1] == "van der Berg"
    assert r.page == "L7"
    assert r.year == 2020


def test_bibtex_ads_export_style():
    text = r"""@ARTICLE{2021ApJ...919...16F,
       author = {{Freedman}, Wendy L.},
        title = "{Measurements of the Hubble Constant: Tensions in Perspective}",
      journal = {\apj},
         year = 2021,
       volume = {919},
       eid = {16},
        pages = {16},
          doi = {10.3847/1538-4357/ac0e95},
archivePrefix = {arXiv},
       eprint = {2106.15656},
       adsurl = {https://ui.adsabs.harvard.edu/abs/2021ApJ...919...16F},
}"""
    r = load_bibtex(text)[0]
    assert r.authors == ["Freedman"]
    assert r.journal == "ApJ"
    assert r.doi == "10.3847/1538-4357/ac0e95"
    assert r.arxiv == "2106.15656"
    assert r.bibcode == "2021ApJ...919...16F"
    assert r.volume == "919" and r.page == "16"


def test_bbl_jhep_style_regression_entries(fixtures_dir):
    refs = load_bbl((fixtures_dir / "arxiv_2509.09678_subset.bbl").read_text())
    by_key = {r.key: r for r in refs}
    f = by_key["Freedman:2021ahq"]
    assert f.authors == ["Freedman"]
    assert f.year == 2021 and f.volume == "919" and f.page == "16"
    assert f.doi == "10.3847/1538-4357/ac082c"  # the wrong suffix printed in the paper
    assert f.arxiv == "2106.15656"
    s = by_key["Scolnic:2023pga"]
    assert s.doi == "10.3847/2041-8213/ace280" and s.page == "L31"
    p = by_key["Planck:2018vyg"]
    assert p.collaboration and "Planck" in p.collaboration
    assert p.year == 2020


def test_bbl_mnras_style_with_bibcode_key():
    text = r"""\begin{thebibliography}{}
\bibitem[\protect\citeauthoryear{Freedman}{Freedman}{2021}]{2021ApJ...919...16F}
Freedman W.~L., 2021, \apj, 919, 16
\bibitem[\protect\citeauthoryear{{Planck Collaboration} et~al.,}{{Planck Collaboration} et~al.,}{2020}]{2020A&A...641A...6P}
{Planck Collaboration} et~al., 2020, \aap, 641, A6
\end{thebibliography}"""
    refs = load_bbl(text)
    a, b = refs
    assert a.authors == ["Freedman"] and a.year == 2021
    assert a.journal == "ApJ" and a.volume == "919" and a.page == "16"
    assert a.bibcode_hint == "2021ApJ...919...16F"
    assert b.collaboration and b.volume == "641" and b.page == "A6"


def test_journal_names_with_and_and_proceedings_series():
    from citecheck.parsers import parse_reference
    r = parse_reference(r"Goodman, J., \& Weare, J. 2010, Communications in Applied Mathematics and Computational "
                        r"Science, 5, 65", index=1, source_format="bbl")
    assert r.journal.startswith("Communications in Applied") and r.volume == "5" and r.page == "65"
    r = parse_reference(r"Arenou, F., \& Luri, X. 1999, in Astronomical Society of the Pacific Conference Series, "
                        r"Vol. 167, Harmonizing Cosmic Distance Scales, ed. D. Egret \& A. Heck, 13",
                        index=1, source_format="bbl")
    assert r.volume == "167" and r.page == "13" and r.authors == ["Arenou", "Luri"]
    r = parse_reference(r"Hoffman M.~D., Gelman A., et~al., 2014, J. Mach. Learn. Res., 15, 1593",
                        index=1, source_format="bbl")
    assert r.journal == "J. Mach. Learn. Res" and r.volume == "15" and r.page == "1593"


def test_bbl_aasjournal_style():
    text = r"""\begin{thebibliography}{}
\bibitem[{Scolnic} {et~al.}(2023)]{Scolnic2023}
{Scolnic}, D., {Riess}, A.~G., {Wu}, J., et~al. 2023, \apjl, 954, L31,
  \dodoi{10.3847/2041-8213/ace978}
\end{thebibliography}"""
    r = load_bbl(text)[0]
    assert r.authors[:3] == ["Scolnic", "Riess", "Wu"]
    assert r.doi == "10.3847/2041-8213/ace978"
    assert r.year == 2023 and r.volume == "954" and r.page == "L31"


def test_biblatex_bbl():
    text = r"""\entry{Freedman2021}{article}{}
  \name{author}{1}{}{%
    {{hash=abc}{%
       family={Freedman},
       familyi={F\bibinitperiod},
       given={Wendy\bibnamedelima L.},
       giveni={W\bibinitperiod\bibinitdelim L\bibinitperiod}}}%
  }
  \field{journaltitle}{The Astrophysical Journal}
  \field{title}{Measurements of the Hubble Constant: Tensions in Perspective}
  \field{volume}{919}
  \field{year}{2021}
  \field{pages}{16}
  \verb{doi}
  \verb 10.3847/1538-4357/ac0e95
  \endverb
\endentry
"""
    r = load_bbl(text)[0]
    assert r.authors == ["Freedman"]
    assert r.doi == "10.3847/1538-4357/ac0e95"
    assert r.title.startswith("Measurements")
    assert r.source_format == "biblatex-bbl"


def test_plaintext_numbered_list():
    text = """References
[1] Freedman, W. L. (2021). Measurements of the Hubble constant: tensions in perspective. The Astrophysical Journal, 919(1), 16. https://doi.org/10.3847/1538-4357/ac0e95
[2] Smith J., 2020, MNRAS, 491, 5021
3. Doe, A. private communication, 2019
"""
    refs = load_plaintext(text)
    assert len(refs) == 3
    a, b, c = refs
    assert a.doi == "10.3847/1538-4357/ac0e95"
    assert a.title and a.title.lower().startswith("measurements of the hubble")
    assert a.volume == "919" and a.page == "16"
    assert b.authors == ["Smith"] and b.volume == "491" and b.page == "5021"
    assert "private_communication" in c.flags


def test_sniffing():
    refs, kind = load_text("@article{a, title={X Y Z}, author={A, B}, year=2020}")
    assert kind == "bibtex" and len(refs) == 1
    refs, kind = load_text("Smith J., 2020, MNRAS, 491, 5021\nDoe A., 2019, ApJ, 870, 1\n")
    assert kind == "text" and len(refs) == 2


def _tar_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_tarball_prefers_bbl(tmp_path):
    tex = r"\documentclass{article}\begin{document}\cite{a}\bibliography{refs}\end{document}"
    bbl = r"\begin{thebibliography}{1}\bibitem{a} A.~Author, \emph{A title that is long}, Astrophys. J. 1 (2001) 2.\end{thebibliography}"
    p = tmp_path / "src.tar.gz"
    p.write_bytes(_tar_bytes({"main.tex": tex, "main.bbl": bbl, "refs.bib": "@article{a, title={Other}}"}))
    li = load_path(p)
    assert li.kind == "latex-bbl" and li.files_used == ["main.bbl"]
    assert li.refs[0].title == "A title that is long"


def test_source_dir_bib_filtered_by_citations(tmp_path):
    (tmp_path / "paper.tex").write_text(
        r"\documentclass{article}\begin{document}\citep[see][]{used1,used2} \citet{used3}"
        r"\bibliography{refs}\end{document}")
    (tmp_path / "refs.bib").write_text(
        "@article{used1, title={One two three}, author={A, B}, year=2001}\n"
        "@article{used2, title={Four five six}, author={C, D}, year=2002}\n"
        "@article{used3, title={Seven eight nine}, author={E, F}, year=2003}\n"
        "@article{unused, title={Not cited here}, author={G, H}, year=2004}\n")
    li = load_path(tmp_path)
    assert li.kind == "latex-bib"
    assert sorted(r.key for r in li.refs) == ["used1", "used2", "used3"]
