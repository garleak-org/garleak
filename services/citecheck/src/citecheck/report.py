# SPDX-License-Identifier: AGPL-3.0-or-later
"""Report assembly (JSON, schema v1) and the human-readable terminal table."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
from typing import Any

from . import DISCLAIMER, SCHEMA_ID, SCHEMA_VERSION, __version__
from .models import VERDICT_ORDER, RefResult, Verdict

VERDICT_TEXT = {
    Verdict.VERIFIED: "verified",
    Verdict.ID_MISMATCH_REAL_REF: "wrong id, real ref",
    Verdict.METADATA_MISMATCH: "metadata mismatch",
    Verdict.UNRESOLVED: "unresolved",
    Verdict.NOT_CHECKABLE: "not checkable",
}
_COLORS = {
    Verdict.VERIFIED: "32",
    Verdict.ID_MISMATCH_REAL_REF: "33",
    Verdict.METADATA_MISMATCH: "35",
    Verdict.UNRESOLVED: "31;1",
    Verdict.NOT_CHECKABLE: "2",
}


def summarize(results: list[RefResult]) -> dict[str, Any]:
    counts = {v.value: 0 for v in VERDICT_ORDER}
    for r in results:
        counts[r.verdict.value] += 1
    n = len(results)
    flagged = [r.reference.index for r in results
               if r.verdict in (Verdict.UNRESOLVED, Verdict.METADATA_MISMATCH) and not r.incomplete]
    incomplete = [r.reference.index for r in results if r.incomplete]
    corrected = [r.reference.index for r in results if r.verdict == Verdict.ID_MISMATCH_REAL_REF]
    with_id = sum(1 for r in results if r.reference.has_identifier())
    if incomplete and any(results[i - 1].verdict == Verdict.UNRESOLVED for i in incomplete):
        status = "incomplete"
    elif flagged:
        status = "review"
    else:
        status = "pass"
    parts = [f"{counts['verified']} of {n} references verified"]
    if counts["id_mismatch_real_ref"]:
        parts.append(f"{counts['id_mismatch_real_ref']} real with a wrong identifier")
    if counts["metadata_mismatch"]:
        parts.append(f"{counts['metadata_mismatch']} with metadata that disagree")
    if counts["unresolved"]:
        parts.append(f"{counts['unresolved']} unresolved")
    if counts["not_checkable"]:
        parts.append(f"{counts['not_checkable']} not checkable")
    return {
        "n_references": n,
        "n_with_identifier": with_id,
        "counts": counts,
        "flagged_indices": flagged,
        "corrected_indices": corrected,
        "incomplete_indices": incomplete,
        "headline": "; ".join(parts) + ".",
        "prescreen": {
            "status": status,
            "scope": "existence and metadata only (the mechanical half of Garleak tier T1)",
            "claim_support_checked": False,
        },
    }


def build_report(results: list[RefResult], input_info: dict, settings: dict, stats: dict,
                 started: dt.datetime, finished: dt.datetime) -> dict[str, Any]:
    return {
        "$schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "citecheck", "version": __version__},
        "generated_at": finished.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "elapsed_seconds": round((finished - started).total_seconds(), 2),
        "input": input_info,
        "settings": settings,
        "summary": summarize(results),
        "references": [r.to_dict() for r in results],
        "network": stats,
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ terminal


def _use_color(stream) -> bool:
    return hasattr(stream, "isatty") and stream.isatty() and not os.environ.get("NO_COLOR")


def _c(text: str, code: str, on: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if on else text


def _who(r: RefResult) -> str:
    ref = r.reference
    who = ref.collaboration or (ref.authors[0] if ref.authors else (ref.key or "?"))
    if len(ref.authors) > 1 and not ref.collaboration:
        who += " et al." if len(ref.authors) > 2 else f" & {ref.authors[1]}"
    return f"{who} {ref.year or ''}".strip()


def _note(r: RefResult) -> str:
    if r.verdict == Verdict.VERIFIED:
        via = r.matched_record.source if r.matched_record else ""
        ids = [f"{k}:{v}" for k, v in r.reference.to_dict()["identifiers"].items() if k in ("doi", "arxiv")]
        return (" ".join(ids) or f"matched by search ({via})")
    if r.corrected_ids:
        return "use " + ", ".join(f"{k}:{v}" for k, v in r.corrected_ids.items())
    return r.reason


def render_table(report_results: list[RefResult], summary: dict, input_info: dict, stream=None,
                 only_flagged: bool = False) -> str:
    stream = stream or sys.stdout
    color = _use_color(stream)
    width = max(80, min(shutil.get_terminal_size((110, 20)).columns, 160))
    lines = []
    lines.append(f"citecheck {__version__}  input: {input_info.get('source')}  ({input_info.get('kind')})")
    lines.append("")
    w_idx, w_v, w_c, w_who = 4, 18, 5, 26
    w_note = max(20, width - (w_idx + w_v + w_c + w_who + 5))
    lines.append(f"{'#':>{w_idx}} {'verdict':<{w_v}} {'conf':<{w_c}} {'reference':<{w_who}} note")
    lines.append("-" * min(width, w_idx + w_v + w_c + w_who + 5 + w_note))
    for r in report_results:
        if only_flagged and r.verdict == Verdict.VERIFIED:
            continue
        v = VERDICT_TEXT[r.verdict]
        vcol = _c(f"{v:<{w_v}}", _COLORS[r.verdict], color)
        who = _who(r)[:w_who]
        note = _note(r)
        if r.incomplete:
            note = "[incomplete] " + note
        if len(note) > w_note:
            note = note[: w_note - 3] + "..."
        lines.append(f"{r.reference.index:>{w_idx}} {vcol} {r.confidence:<{w_c}.2f} {who:<{w_who}} {note}")
    lines.append("")
    lines.append(summary["headline"])
    flagged = [r for r in report_results if r.reference.index in summary["flagged_indices"]]
    if flagged:
        lines.append("")
        lines.append("Needs a human look:")
        for r in flagged:
            lines.append(f"  [{r.reference.index}] {r.reference.raw[:width - 8]}")
            lines.append(f"       {r.reason[:2 * width]}")
    fixes = [r for r in report_results if r.verdict == Verdict.ID_MISMATCH_REAL_REF]
    if fixes:
        lines.append("")
        lines.append("Identifier corrections (the works are real):")
        for r in fixes:
            corr = ", ".join(f"{k} {v}" for k, v in r.corrected_ids.items()) or "see JSON report"
            lines.append(f"  [{r.reference.index}] {_who(r)}: {corr}")
    lines.append("")
    lines.append(_c("Note: " + DISCLAIMER, "2", color))
    return "\n".join(lines)
