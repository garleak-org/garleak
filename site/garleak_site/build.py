# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the static site.

The real archive is built at the site root and the example archive under /example/,
where every page carries a banner and `noindex, nofollow`. Invented records are never
written outside /example/, and the sitemap and feeds come from the real archive only.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from garleak_archive import assistance as asst
from garleak_archive.diff import inline_diff_html, render_html, word_diff
from garleak_archive.loader import load_archive
from garleak_archive.stages import N_NAMES, TIER_NAMES
from garleak_archive.validate import validate

from . import view as V
from .blog import load_posts
from .markup import render_body, render_spec
from .pdfstamp import stamp_pdf

PKG = Path(__file__).parent
LISTING_ROBOTS = "noindex, follow"

# path, template, title, nav key
CONTENT_PAGES = [
    ("/about/", "about.html", "About Garleak", "about"),
    ("/stages/", "stages.html", "Stages and assistance", "stages"),
    ("/verify/", "verify.html", "Verify for Garleak", "verify"),
    ("/submit/", "submit.html", "Submitting to Garleak", "submit"),
    ("/citecheck/", "citecheck.html", "citecheck", "citecheck"),
    ("/terms/", "terms.html", "Terms, draft", "terms"),
    ("/licenses/", "licenses.html", "Licenses", "licenses"),
    ("/moderation/", "moderation.html", "Screening and moderation", "moderation"),
]


class BuildError(RuntimeError):
    pass


def load_config(path: Path) -> dict:
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text())
    for key in ("archive", "example_archive", "tokens", "spec", "blog"):
        if cfg.get(key):
            cfg[key] = (path.parent / cfg[key]).resolve()
    cfg["site_url"] = cfg["site_url"].rstrip("/")
    return cfg


@dataclass
class Page:
    path: str
    indexable: bool
    example: bool


class Builder:
    def __init__(self, config: dict, out: Path, build_date: dt.date | None = None,
                 allow_example_at_root: bool = False):
        self.cfg = config
        self.out = Path(out)
        self.build_date = build_date or dt.datetime.now(dt.timezone.utc).date()
        self.allow_example_at_root = allow_example_at_root
        self.pages: list[Page] = []
        self.pdfs = 0
        self.noindex_pdfs: list[str] = []
        self.env = Environment(
            loader=FileSystemLoader(PKG / "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )
        self.env.filters.update(
            longdate=V.longdate, dayname=V.dayname, shortdate=V.shortdate,
            monthname=V.monthname, plural=V.plural, join_names=V.join_names,
        )
        self.env.globals.update(
            cfg=config, TIER_NAMES=TIER_NAMES, N_NAMES=N_NAMES, WRITING=asst.WRITING,
            ANALYSIS=asst.ANALYSIS, gloss=V.gloss, build_date=self.build_date,
            MIN_VOTES=asst.MIN_VOTES_FOR_MEDIAN, has_example=False,
            LICENSES=V.LICENSES, license_name=V.license_name, license_url=V.license_url,
        )

    # ------------------------------------------------------------ output

    def _file(self, path: str) -> Path:
        p = self.out / path.lstrip("/")
        return p / "index.html" if path.endswith("/") else p

    def write(self, path: str, text: str) -> None:
        p = self._file(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def render(self, path: str, template: str, *, title: str, site: V.Site | None = None,
               robots: str | None = None, canonical: str | None = None, nav: str = "",
               indexable: bool = True, searchable: bool = False, **ctx) -> None:
        example = bool(site and site.example)
        if example:
            robots, indexable = "noindex, nofollow", False
        elif robots:
            indexable = False
        html = self.env.get_template(template).render(
            title=title, site=site, example=example, robots=robots, nav=nav, path=path,
            canonical=self.cfg["site_url"] + (canonical or path),
            searchable=searchable and not example, **ctx,
        )
        self.write(path, html)
        self.pages.append(Page(path, indexable and (canonical or path) == path, example))

    def redirect(self, path: str, target: str, site: V.Site, what: str) -> None:
        self.render(path, "redirect.html", title=what, site=site, robots=LISTING_ROBOTS,
                    canonical=target, target=target, what=what)

    # ------------------------------------------------------------ the build

    def site_for(self, root: Path, prefix: str, example: bool) -> V.Site:
        archive = load_archive(root)
        errors = [i for i in validate(archive) if i.level == "error"]
        if errors:
            raise BuildError(f"{root} does not validate:\n" + "\n".join(str(e) for e in errors))
        if archive.example and not example and not self.allow_example_at_root:
            raise BuildError(f"{root} is an example archive and is built only under /example/")
        if example and not archive.example:
            raise BuildError(f"{root} is not marked example: true, so it cannot go under /example/")
        today = archive.as_of or self.build_date
        return V.Site(archive, prefix, example, today, self.cfg)

    def build(self) -> dict:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.static()
        real = self.site_for(self.cfg["archive"], "", False)
        sites = [real]
        ex = None
        if self.cfg.get("example_archive") and Path(self.cfg["example_archive"]).is_dir():
            ex = self.site_for(self.cfg["example_archive"], "/example", True)
            sites.append(ex)
        self.env.globals["has_example"] = ex is not None
        self.content(real, ex)
        for s in sites:
            self.archive_pages(s)
        self.feeds(real)
        self.notfound(sites)
        self.meta_files()
        return {"pages": len(self.pages), "pdfs": self.pdfs}

    def static(self) -> None:
        shutil.copytree(PKG / "static", self.out / "static", ignore=shutil.ignore_patterns("site.css", ".DS_Store", "fonts"))
        tokens = Path(self.cfg["tokens"]).read_text(encoding="utf-8")
        site_css = (PKG / "static" / "site.css").read_text(encoding="utf-8")
        (self.out / "static" / "garleak.css").write_text(tokens + "\n" + site_css, encoding="utf-8")

    # ------------------------------------------------------------ content pages

    def content(self, real: V.Site, ex: V.Site | None) -> None:
        self.render("/", "home.html", title="Garleak", site=real, nav="home", searchable=True, example_site=ex)
        for path, template, title, nav in CONTENT_PAGES:
            self.render(path, template, title=title, site=real, nav=nav, searchable=True, example_site=ex)
        spec_title, spec_html, toc = render_spec(Path(self.cfg["spec"]).read_text(encoding="utf-8"))
        self.render("/spec/", "spec.html", title="Specification", site=real, nav="spec", searchable=True,
                    spec_title=spec_title, spec_html=spec_html, toc=toc)
        self.render("/search/", "search.html", title="Search", site=real, robots=LISTING_ROBOTS, nav="search")
        self.blog(real)

    def blog(self, s: V.Site) -> None:
        """Posts and statements from blog/: an index, one page each, and an Atom feed."""
        posts = load_posts(self.cfg.get("blog"))
        self.render("/blog/", "blog_index.html", title="Blog", site=s, nav="blog", searchable=True, posts=posts)
        for post in posts:
            self.render(post.url, "blog_post.html", title=post.title, site=s, nav="blog", searchable=True,
                        post=post, body=render_body(post.body, post.url))
        newest = max((p.date for p in posts), default=s.today)
        updated = dt.datetime.combine(newest, dt.time(0, 0), dt.timezone.utc).isoformat()
        xml = self.env.get_template("blog_atom.xml").render(base=self.cfg["site_url"], posts=posts[:50],
                                                            updated=updated)
        self.write("/blog/feed.xml", xml)

    # ------------------------------------------------------------ archive pages

    def archive_pages(self, s: V.Site) -> None:
        if s.example:
            self.render(s.url("/"), "home.html", title="Example archive", site=s, nav="home", example_site=s)
            self.render(s.url("/verify/"), "verify.html", title="Verification queue", site=s, nav="verify",
                        example_site=s)
        self.render(s.url("/list/"), "list_index.html", title="Papers by category", site=s,
                    robots=LISTING_ROBOTS, nav="papers", kind="paper")
        self.render(s.url("/sketch/list/"), "list_index.html", title="Sketches by category", site=s,
                    robots=LISTING_ROBOTS, nav="sketches", kind="sketch")
        self.render(s.url("/graduated/"), "graduated.html", title="Graduated papers", site=s,
                    robots=LISTING_ROBOTS, nav="graduated")
        for cat in s.a.categories.values():
            months = s.months(cat.code)
            for kind, base, nav in (("paper", "/list/", "papers"), ("sketch", "/sketch/list/", "sketches")):
                noun = "papers" if kind == "paper" else "sketches"
                recent = s.paper_recent(cat.code) if kind == "paper" else s.sketch_recent(cat.code)
                self.render(s.url(f"{base}{cat.code}/recent/"), "listing.html",
                            title=f"{cat.name} {noun}, recent", site=s, robots=LISTING_ROBOTS, nav=nav,
                            kind=kind, cat=cat, listing=recent, period="recent", months=months)
                self.redirect(s.url(f"{base}{cat.code}/new/"), s.url(f"{base}{cat.code}/recent/"), s,
                              f"{cat.name} {noun}, recent")
                for ym in months:
                    lst = s.paper_month(cat.code, ym) if kind == "paper" else s.sketch_month(cat.code, ym)
                    self.render(s.url(f"{base}{cat.code}/{ym}/"), "listing.html",
                                title=f"{cat.name} {noun}, {V.monthname(ym)}", site=s, robots=LISTING_ROBOTS,
                                nav=nav, kind=kind, cat=cat, listing=lst, period=ym, months=months)
        for pv in s.papers:
            self.paper_pages(s, pv)
        for sv in s.sketches:
            self.sketch_pages(s, sv)

    def abs_page(self, s: V.Site, pv: V.PaperView, vv: V.VersionView, path: str, canonical: str, form: str) -> None:
        ident = "paper:" + path.rstrip("/").rsplit("/", 1)[-1]
        if pv.removed:
            self.render(path, "tombstone.html", title=f"{ident} removed", site=s, robots=LISTING_ROBOTS,
                        canonical=canonical, pv=pv, ident=ident, obj=pv.p)
        elif not vv.visible:
            self.render(path, "gated.html", title=f"{ident}, gated", site=s, robots=LISTING_ROBOTS,
                        canonical=canonical, pv=pv, vv=vv, ident=ident)
        else:
            self.render(path, "abs.html", title=vv.v.title, site=s, canonical=canonical, nav="papers",
                        robots=None if vv.indexable else LISTING_ROBOTS, searchable=True,
                        pv=pv, vv=vv, form=form, ident=ident)

    def paper_pages(self, s: V.Site, pv: V.PaperView) -> None:
        n = pv.number
        for vv in pv.versions:
            self.abs_page(s, pv, vv, vv.url, vv.url, "exact")
            self.redirect(s.url(f"/abs/paper:{vv.key}/"), vv.url, s, vv.ident)
            if vv.visible and not pv.removed:
                self.version_files(s, pv, vv)
        for major, vv in pv.series.items():
            path = s.url(f"/abs/{n}v{major}/")
            self.abs_page(s, pv, vv, path, vv.url, "series")
            self.redirect(s.url(f"/abs/paper:{n}v{major}/"), path, s, f"paper:{n}v{major}")
        self.abs_page(s, pv, pv.current, pv.concept_url, pv.concept_url, "concept")
        self.redirect(s.url(f"/abs/paper:{n}/"), pv.concept_url, s, f"paper:{n}")
        if pv.removed:
            return
        for a, later in pv.pairs:
            for b in later:
                self.diff_page(s, pv, a, b)

    def version_files(self, s: V.Site, pv: V.PaperView, vv: V.VersionView) -> None:
        src = self._file(vv.src_dir).parent
        src.mkdir(parents=True, exist_ok=True)
        for f in sorted(vv.v.directory.iterdir()):
            # PDFs are served only stamped, from pdf_url, never as the raw upload.
            if f.is_file() and f.name != ".DS_Store" and f.suffix.lower() != ".pdf":
                shutil.copy2(f, src / f.name)
        (src / "index.html").unlink(missing_ok=True)
        if vv.v.pdf:
            stamp_pdf(vv.v.pdf, self._file(vv.pdf_url), vv.stamp_lines)
            self.pdfs += 1
            if not vv.indexable:
                # GitHub Pages cannot send X-Robots-Tag, so keep crawlers off these files.
                self.noindex_pdfs.append(vv.pdf_url)
        body = render_body(vv.v.body, vv.src_dir)
        self.render(vv.text_url, "text.html", title=f"{vv.v.title}, full text", site=s, nav="papers",
                    robots=None if vv.indexable else LISTING_ROBOTS, searchable=True, pv=pv, vv=vv, body=body)

    def diff_page(self, s: V.Site, pv: V.PaperView, a: V.VersionView, b: V.VersionView) -> None:
        body = word_diff(a.v.body, b.v.body)
        abstract = word_diff(a.v.abstract, b.v.abstract)
        self.render(a.diff_url(b), "diff.html", title=f"paper:{pv.number}, v{a.number} compared with v{b.number}",
                    site=s, robots=LISTING_ROBOTS, nav="papers", pv=pv, a=a, b=b,
                    title_diff=inline_diff_html(a.v.title, b.v.title), abstract_diff=render_html(abstract),
                    body_diff=render_html(body), added=body.added + abstract.added,
                    removed=body.removed + abstract.removed)

    def sketch_pages(self, s: V.Site, sv: V.SketchView) -> None:
        n = sv.number
        if sv.s.status == "removed":
            self.render(sv.url, "tombstone.html", title=f"sketch:{n} removed", site=s, robots=LISTING_ROBOTS,
                        pv=None, ident=f"sketch:{n}", obj=sv.s)
        elif not sv.visible:
            self.render(sv.url, "gated.html", title=f"sketch:{n}, gated", site=s, robots=LISTING_ROBOTS,
                        pv=None, vv=None, sv=sv, ident=f"sketch:{n}")
        else:
            self.render(sv.url, "sketch.html", title=sv.s.statement, site=s, nav="sketches", searchable=True,
                        robots=None if sv.indexable else LISTING_ROBOTS, sv=sv)
        for key in (f"{n}v1", f"{n}v1.0"):
            self.redirect(s.url(f"/sketch/{key}/"), sv.url, s, f"sketch:{key}")
        for key in (f"{n}", f"{n}v1", f"{n}v1.0"):
            self.redirect(s.url(f"/abs/sketch:{key}/"), sv.url, s, f"sketch:{key}")

    # ------------------------------------------------------------ feeds, 404, sitemap

    def feeds(self, s: V.Site) -> None:
        """Atom feeds per category, real archive only."""
        updated = dt.datetime.combine(s.today, dt.time(0, 0), dt.timezone.utc).isoformat()
        for cat in s.a.categories.values():
            papers = sorted((v for pv in s.cat_papers(cat.code) for v in pv.versions if v.visible),
                            key=lambda v: (v.v.date, v.pv.number), reverse=True)[:50]
            sketches = sorted(s.cat_sketches(cat.code), key=lambda x: (x.s.date, x.number), reverse=True)[:50]
            for kind, base, entries in (("paper", "/list/", papers), ("sketch", "/sketch/list/", sketches)):
                xml = self.env.get_template("atom.xml").render(site=s, cat=cat, kind=kind, entries=entries,
                                                                updated=updated, base=base)
                self.write(f"{base}{cat.code}/feed.xml", xml)

    def notfound(self, sites: list[V.Site]) -> None:
        issued = json.dumps({s.prefix: s.issued() for s in sites}, separators=(",", ":"), sort_keys=True)
        real = sites[0]
        html = self.env.get_template("404.html").render(
            title="Nothing here", site=real, example=False, robots="noindex", nav="", path="/404.html",
            canonical=None, searchable=False, issued=issued.replace("</", "<\\/"),
        )
        self.write("/404.html", html)
        self.pages.append(Page("/404.html", False, False))

    def meta_files(self) -> None:
        base = self.cfg["site_url"]
        disallow = "".join(f"Disallow: {u}\n" for u in sorted(set(self.noindex_pdfs)))
        self.write("/robots.txt", f"User-agent: *\n{disallow}Allow: /\n\nSitemap: {base}/sitemap.xml\n")
        urls = sorted({p.path for p in self.pages if p.indexable and not p.example})
        xml = self.env.get_template("sitemap.xml").render(base=base, urls=urls)
        self.write("/sitemap.xml", xml)
        self.write("/CNAME", base.split("://", 1)[1] + "\n")


def build(config_path: Path, out: Path, build_date: dt.date | None = None) -> dict:
    return Builder(load_config(config_path), out, build_date).build()
