# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line.

    garleak-site build --out _site            build the site
    garleak-site check _site                  run the checks over a built site
    garleak-site serve --out _site            build, then serve at http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _default_config() -> Path:
    local = Path.cwd() / "config.yaml"
    return local if local.is_file() else HERE.parent / "config.yaml"


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the build like GitHub Pages does, including the custom 404 page."""

    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code == 404 and page.is_file():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)


def _build(config: Path, out: Path, date: str | None) -> int:
    from .build import BuildError, build

    try:
        stats = build(config, out, dt.date.fromisoformat(date) if date else None)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"built {stats['pages']} pages and {stats['pdfs']} stamped PDF(s) into {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="garleak-site", description="Build and check the Garleak static site.")
    ap.add_argument("--config", type=Path, default=None, help="site config (default: ./config.yaml, else site/config.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the site")
    b.add_argument("--out", type=Path, default=Path("_site"))
    b.add_argument("--date", help="build date, YYYY-MM-DD (default: today, UTC)")
    c = sub.add_parser("check", help="check a built site")
    c.add_argument("site", type=Path, nargs="?", default=Path("_site"))
    c.add_argument("--no-boundary", action="store_true", help="skip the invented-record check")
    s = sub.add_parser("serve", help="build, then serve locally")
    s.add_argument("--out", type=Path, default=Path("_site"))
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--no-build", action="store_true")
    s.add_argument("--date")
    args = ap.parse_args(argv)
    config = args.config or _default_config()

    if args.cmd == "build":
        return _build(config, args.out, args.date)
    if args.cmd == "check":
        from .build import load_config
        from .checks import check_site

        cfg = load_config(config)
        ex = None if args.no_boundary else cfg.get("example_archive")
        report = check_site(args.site, ex)
        for e in report.errors:
            print("error:", e)
        print(f"checked {report.pages} pages, {report.files} files, {report.bytes / 1e6:.2f} MB, "
              f"{report.js_bytes} bytes of JavaScript: {len(report.errors)} error(s)")
        return 0 if report.ok else 1
    if args.cmd == "serve":
        if not args.no_build and _build(config, args.out, args.date):
            return 1
        handler = functools.partial(_Handler, directory=str(args.out.resolve()))
        with http.server.ThreadingHTTPServer((args.host, args.port), handler) as httpd:
            print(f"serving {args.out} at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
