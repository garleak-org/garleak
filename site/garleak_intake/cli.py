# SPDX-License-Identifier: AGPL-3.0-or-later
"""garleak-intake: the command line the intake workflows call, and that people run locally.

    garleak-intake process --event event.json --archive ../archive --dry-run
    garleak-intake process --issue issue.json --context ctx/ --archive archive --out out/ --github-output $GITHUB_OUTPUT
    garleak-intake orcid-lookup --issue issue.json --archive archive --out ctx/orcid.json
    garleak-intake route --issue issue.json
    garleak-intake check-pr --archive archive --base origin/main
    garleak-intake stale-prs --open-prs open-prs.json --base HEAD
    garleak-intake ledger --archive ../archive [--account HANDLE] [--json]
    garleak-intake labels
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

from . import labels as L
from .context import Context, parse_ts
from .paths import ARCHIVE


def _issue(args) -> tuple[dict, dict | None]:
    event = json.loads(Path(args.event).read_text(encoding="utf-8")) if getattr(args, "event", None) else None
    if getattr(args, "issue", None):
        issue = json.loads(Path(args.issue).read_text(encoding="utf-8"))
    else:
        issue = (event or {}).get("issue")
    if not isinstance(issue, dict) or "number" not in issue:
        raise SystemExit("no issue: give --issue issue.json or --event with an `issue` object")
    return issue, event


def _config(archive: Path) -> dict:
    return yaml.safe_load((Path(archive) / "config.yaml").read_text(encoding="utf-8"))


def cmd_process(args) -> int:
    from .http import UrllibHttp
    from .orcid import OrcidClient
    from .process import Options, process_issue

    issue, event = _issue(args)
    ctx = Context.load(Path(args.context) if args.context else None)
    http = None if args.offline else UrllibHttp()
    orcid = None
    if http is not None and ctx.orcid is None and (Path(args.archive) / "config.yaml").is_file():
        orcid = OrcidClient.from_config(http, _config(args.archive), Path(args.cache_dir) if args.cache_dir else None)
    opts = Options(dry_run=args.dry_run, now=parse_ts(args.now) if args.now else None, offline=args.offline,
                   citecheck=args.citecheck, forms_dir=Path(args.forms) if args.forms else None,
                   rubrics_dir=Path(args.rubrics) if args.rubrics else None, http=http, orcid_client=orcid)
    res = process_issue(issue, Path(args.archive), ctx, opts, event)
    add, remove = res.labels()
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").write_text(res.to_json(), encoding="utf-8")
        (out / "comment.md").write_text(res.comment_markdown(), encoding="utf-8")
        (out / "labels-add.txt").write_text("".join(f"{x}\n" for x in add), encoding="utf-8")
        (out / "labels-remove.txt").write_text("".join(f"{x}\n" for x in remove), encoding="utf-8")
        if res.action == "pr":
            (out / "pr-title.txt").write_text(res.pr_title + "\n", encoding="utf-8")
            (out / "pr-body.md").write_text(res.pr_body(), encoding="utf-8")
            (out / "commit-message.txt").write_text(res.commit_message(), encoding="utf-8")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            for k, v in res.outputs().items():
                fh.write(f"{k}={v}\n")
    if args.dry_run or not args.out:
        print(f"status: {res.status}   action: {res.action}   automerge: {res.automerge}   branch: {res.branch}")
        print(f"labels: +{', '.join(add) or '-'}   -{', '.join(remove) or '-'}")
        if res.errors:
            print("errors:\n  " + "\n  ".join(res.errors))
        print("\n--- issue comment ---\n" + res.comment_markdown())
        if res.action == "pr":
            print("--- pull request: " + res.pr_title)
            for f in res.files:
                print(f"--- {f}")
                if f in res.previews:
                    print(res.previews[f].rstrip())
    # In the workflow a handled error still needs its comment, so only a dry run signals it.
    return 3 if (args.dry_run and res.status == "error") else 0


def cmd_route(args) -> int:
    issue, _ = _issue(args)
    names = [x["name"] if isinstance(x, dict) else x for x in issue.get("labels") or []]
    kinds = sorted({L.KIND_OF_LABEL[x] for x in names if x in L.KIND_OF_LABEL})
    kind = kinds[0] if len(kinds) == 1 else ""
    print(kind)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"kind={kind}\n")
    return 0


def cmd_orcid(args) -> int:
    """The only step that sees the ORCID secrets. It reads the iD from the form, checks its
    check digit, reads the public record, and writes the answer for `process`."""
    from .forms import form_for_labels, load_forms, parse_body
    from .http import UrllibHttp
    from .orcid import OrcidClient, normalize_orcid, orcid_checksum_ok
    from .requests import Fields, build_identity

    issue, _ = _issue(args)
    names = [x["name"] if isinstance(x, dict) else x for x in issue.get("labels") or []]
    form = form_for_labels(load_forms(Path(args.forms) if args.forms else None), names)
    if form is None or form.kind != "identity":
        print("not an identity issue")
        return 0
    values, missing = parse_body(form, issue.get("body") or "")
    req = build_identity(Fields(form, values, missing))
    orcid = normalize_orcid(req.orcid) if req.path == "orcid" else None
    if not orcid or not orcid_checksum_ok(orcid):
        print("no valid ORCID iD in the form")
        return 0
    client = OrcidClient.from_config(UrllibHttp(), _config(args.archive), Path(args.cache_dir) if args.cache_dir else None)
    rec = client.lookup(orcid)
    Path(args.out).write_text(json.dumps(rec.to_dict(), indent=2), encoding="utf-8")
    print(f"{orcid}: {rec.status}")
    return 0


def cmd_check_pr(args) -> int:
    from .gitcheck import collisions, repo_root

    repo = repo_root(Path(args.archive))
    problems = collisions(repo, args.base, args.head)
    for p in problems:
        print("collision:", p)
    print(f"check-pr: {len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_stale(args) -> int:
    from .gitcheck import repo_root, stale_issues

    rows = json.loads(Path(args.open_prs).read_text(encoding="utf-8") or "[]")
    branches = [r.get("headRefName", "") for r in rows]
    found = stale_issues(repo_root(Path(args.repo)), branches, args.base, args.remote)
    text = "".join(f"{n}\n" for n in found)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


def cmd_ledger(args) -> int:
    from garleak_archive import ledger
    from garleak_archive.loader import load_archive

    a = load_archive(Path(args.archive))
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    bal = ledger.balances(ledger.events(a))
    rows = []
    for (acc, fld), amount in sorted(bal.items()):
        if args.account and acc != args.account:
            continue
        rows.append({"account": acc, "field": fld, "balance": str(amount),
                     "standing": ledger.standing(a, acc, fld, today)})
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print("The ledger is computed from public records, so every balance here is public (SPEC §3.7.5).")
        print(f"{'account':<24}{'field':<10}{'balance':>10}{'standing':>10}")
        for r in rows:
            print(f"{r['account']:<24}{r['field']:<10}{r['balance']:>10}{r['standing']:>10}")
    return 0


def cmd_labels(args) -> int:
    print(L.tsv(Path(args.file) if args.file else None), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="garleak-intake", description="Phase 1 intake for Garleak.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("process", help="process one issue into records and a report")
    p.add_argument("--event", help="a GitHub event payload (its `issue`, and `comment` if any)")
    p.add_argument("--issue", help="a REST issue object, which takes precedence over the event's")
    p.add_argument("--archive", default=str(ARCHIVE))
    p.add_argument("--context", help="directory the workflow filled with comments, permissions and open PRs")
    p.add_argument("--out", help="directory for result.json, comment.md, the PR texts and labels")
    p.add_argument("--github-output", help="append step outputs here (GITHUB_OUTPUT)")
    p.add_argument("--dry-run", action="store_true", help="write to a temporary copy of the archive and print")
    p.add_argument("--now", help="the time to act at, ISO 8601 (for tests)")
    p.add_argument("--offline", action="store_true", help="no network: no ORCID, no attachments")
    p.add_argument("--citecheck", help="path to the citecheck executable")
    p.add_argument("--forms", help="issue-form directory (default .github/ISSUE_TEMPLATE)")
    p.add_argument("--rubrics", help="rubrics directory (default from archive.yaml)")
    p.add_argument("--cache-dir", help="ORCID cache directory")
    p.set_defaults(func=cmd_process)

    r = sub.add_parser("route", help="print the form kind of an issue")
    r.add_argument("--event")
    r.add_argument("--issue")
    r.add_argument("--github-output")
    r.set_defaults(func=cmd_route)

    o = sub.add_parser("orcid-lookup", help="read the public ORCID record named in an identity issue")
    o.add_argument("--event")
    o.add_argument("--issue")
    o.add_argument("--archive", default=str(ARCHIVE))
    o.add_argument("--forms")
    o.add_argument("--cache-dir")
    o.add_argument("--out", required=True)
    o.set_defaults(func=cmd_orcid)

    c = sub.add_parser("check-pr", help="fail if the branch adds records the base already has")
    c.add_argument("--archive", default=str(ARCHIVE))
    c.add_argument("--base", required=True)
    c.add_argument("--head", default="HEAD")
    c.set_defaults(func=cmd_check_pr)

    s = sub.add_parser("stale-prs", help="issues whose open intake branch collides with the base")
    s.add_argument("--open-prs", required=True)
    s.add_argument("--repo", default=".")
    s.add_argument("--base", default="HEAD")
    s.add_argument("--remote", default="origin")
    s.add_argument("--out")
    s.set_defaults(func=cmd_stale)

    lg = sub.add_parser("ledger", help="balances and standing, computed from the records")
    lg.add_argument("--archive", default=str(ARCHIVE))
    lg.add_argument("--account")
    lg.add_argument("--today")
    lg.add_argument("--json", action="store_true")
    lg.set_defaults(func=cmd_ledger)

    lb = sub.add_parser("labels", help="print .github/labels.yml as name, color, description lines")
    lb.add_argument("--file")
    lb.set_defaults(func=cmd_labels)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
