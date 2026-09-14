# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier, journal, and matching tests. No network."""

import re
from pathlib import Path

from citecheck.ids import (arxiv_well_formed, doi_repairs, extract_arxiv, extract_dois, normalize_arxiv,
                           normalize_doi, parse_bibcode, pos_from_doi)
from citecheck.journals import journal_key, journals_agree
from citecheck.match import compare, surnames_match
from citecheck.models import Record, Reference


def test_normalize_doi_variants():
    for s in ("https://doi.org/10.3847/1538-4357/AC0E95", "doi:10.3847/1538-4357/ac0e95.",
              "http://dx.doi.org/10.3847/1538-4357/ac0e95", "10.3847%2F1538-4357%2Fac0e95"):
        assert normalize_doi(s) == "10.3847/1538-4357/ac0e95"
    assert normalize_doi("no doi here") is None


def test_extract_dois_from_latex():
    s = r"\href{https://doi.org/10.1088/2041-8205/802/2/L19}{\emph{ApJL} 802} doi:10.1093/mnras/stz3094."
    assert extract_dois(s) == ["10.1088/2041-8205/802/2/l19", "10.1093/mnras/stz3094"]


def test_doi_repairs_doubled_letter_and_tail():
    cands = dict(doi_repairs("10.1093/mmnras/stt984"))
    assert "10.1093/mnras/stt984" in cands
    cands = dict(doi_repairs("10.1126/science.1123013/suppl"))
    assert "10.1126/science.1123013" in cands


def test_arxiv_ids():
    assert normalize_arxiv("arXiv:2106.15656v2") == "2106.15656"
    assert normalize_arxiv("https://arxiv.org/abs/astro-ph/0601001") == "astro-ph/0601001"
    assert arxiv_well_formed("2106.15656")
    assert not arxiv_well_formed("2407.1234")  # 4-digit number after 2015
    assert not arxiv_well_formed("2413.12345")  # month 13
    assert arxiv_well_formed("0704.0001")
    assert extract_arxiv(r"[\href{https://arxiv.org/abs/1502.02024}{{\ttfamily 1502.02024}}]") == ["1502.02024"]
    assert extract_arxiv("arXiv e-prints, p. arXiv:2101.00001") == ["2101.00001"]


def test_bibcode_parsing():
    b = parse_bibcode("2023PASP..135d8003W")
    assert b["bibstem"] == "PASP" and b["volume"] == "135" and b["page"] == "48003"
    b = parse_bibcode("2024ApJ...969L...2F")
    assert b["volume"] == "969" and b["page"] == "L2"
    assert parse_bibcode("Freedman:2021ahq") is None


def test_pos_doi():
    assert pos_from_doi("10.22323/1.444.0905") == ("444", "905")
    assert pos_from_doi("10.3847/1538-4357/ac0e95") is None


def test_journal_keys():
    assert journal_key("Mon. Not. Roy. Astron. Soc.")[0] == "mnras"
    assert journal_key("Monthly Notices of the Royal Astronomical Society")[0] == "mnras"
    assert journal_key("mmnras") == ("mnras", True)  # journal-string typo, flagged not failed
    assert journal_key("Astrophys. J. Lett.")[0] == "apjl"
    assert journal_key(r"\apj")[0] == "apj"
    assert journal_key("Astronomy & Astrophysics")[0] == "aa"
    assert journals_agree("ApJ", "The Astrophysical Journal") is True
    assert journals_agree("MNRAS", "Physical Review D") is False


def test_surnames():
    assert surnames_match("Muñoz", "Munoz")
    assert surnames_match("Alves de Oliveira", "Oliveira")
    assert surnames_match("Garcia Marin", "García Marín")
    assert not surnames_match("Smith", "Freedman")
    assert surnames_match("Hoffman", "Homan")  # 'ff' ligature lost in PDF-derived index metadata
    assert not surnames_match("Hoffman", "Holman")


FREEDMAN = Record(source="crossref", ids={"doi": "10.3847/1538-4357/ac0e95"},
                  title="Measurements of the Hubble Constant: Tensions in Perspective*",
                  authors=["Freedman, Wendy L."], family_names=["Freedman"], year=2021,
                  container="The Astrophysical Journal", volume="919", page="16")


def test_compare_agrees_without_title():
    ref = Reference(index=1, raw="Freedman W. L., 2021, ApJ, 919, 16", source_format="bbl",
                    authors=["Freedman"], year=2021, journal="ApJ", volume="919", page="16")
    s = compare(ref, FREEDMAN)
    assert s.agrees and s.strength == "strong" and not s.contradicts


def test_compare_contradiction():
    ref = Reference(index=1, raw="Smith J., 2015, ApJ, 800, 1", source_format="bbl",
                    title="A completely different study of galaxy clusters", title_reliable=True,
                    authors=["Smith"], year=2015, journal="ApJ", volume="800", page="1")
    s = compare(ref, FREEDMAN)
    assert not s.agrees and s.contradicts


def test_compare_collaboration():
    rec = Record(source="crossref", title="Planck 2018 results. VI. Cosmological parameters",
                 authors=["Aghanim, N."], family_names=["Aghanim"], year=2020, volume="641", page="A6")
    ref = Reference(index=1, raw="Planck collaboration, Planck 2018 results. VI.", source_format="bbl",
                    collaboration="Planck collaboration", title="Planck 2018 results. VI. Cosmological parameters",
                    title_reliable=True, year=2020, volume="641", page="A6")
    s = compare(ref, rec)
    assert s.agrees and s.strength == "strong"


def test_jcap_issue_printed_as_volume():
    """JCAP uses the year as the volume; references print the issue (3) instead."""
    rec = Record(source="crossref", title="Determining H0 with Bayesian hyper-parameters",
                 authors=["Cardona, Wilmar"], family_names=["Cardona"], year=2017, volume="2017", issue="03",
                 page="056")
    ref = Reference(index=1, raw="Cardona, W., Kunz, M., & Pettorino, V. 2017, JCAP, 3, 056", source_format="bbl",
                    authors=["Cardona", "Kunz", "Pettorino"], year=2017, journal="JCAP", volume="3", page="056")
    s = compare(ref, rec)
    assert s.venue == 1.0 and s.agrees and s.strength == "strong"


def test_author_volume_page_survive_an_index_year_quirk():
    """OpenAlex dates the JMLR NUTS paper 2011 (its arXiv year); the reference says 2014."""
    rec = Record(source="openalex", title="The No-U-turn sampler: adaptively setting path lengths in "
                 "Hamiltonian Monte Carlo", authors=["Matthew D. Hoffman", "Andrew Gelman"],
                 family_names=["Hoffman", "Gelman"], year=2011, volume="15", page="1593")
    ref = Reference(index=1, raw="Hoffman M. D., Gelman A., et al., 2014, J. Mach. Learn. Res., 15, 1593",
                    source_format="bbl", authors=["Hoffman", "Gelman"], year=2014,
                    journal="J. Mach. Learn. Res", volume="15", page="1593")
    s = compare(ref, rec)
    assert s.agrees and s.strength == "moderate" and not s.contradicts


def test_author_year_agree_when_style_prints_no_title():
    rec = Record(source="datacite", title="Most of the photons that reionized the Universe came from dwarf galaxies",
                 authors=["Atek, Hakim"], family_names=["Atek"], year=2023)
    ref = Reference(index=1, raw="Atek H., et al., 2023, arXiv e-prints, p. arXiv:2308.08540", source_format="bbl",
                    authors=["Atek"], year=2023, arxiv="2308.08540")
    s = compare(ref, rec)
    assert s.agrees and not s.contradicts and s.strength == "weak"


def test_no_default_email_in_source():
    """The Crossref/OpenAlex contact address must come only from CITECHECK_MAILTO."""
    src = Path(__file__).resolve().parents[1] / "src" / "citecheck"
    pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
    for p in src.rglob("*.py"):
        assert not pat.search(p.read_text()), f"email-like string in {p}"
