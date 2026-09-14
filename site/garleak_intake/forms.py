# SPDX-License-Identifier: AGPL-3.0-or-later
"""Issue-form templates and the markdown GitHub renders from them.

GitHub turns a submitted issue form into a body of sections, one per field, headed by the
field's label:

    ### Statement

    Wide-binary eccentricities should flatten above 0.1 pc ...

    ### Detail

    _No response_

Checkboxes arrive as `- [X] label` lines and dropdowns as the chosen option's text. The
templates in `.github/ISSUE_TEMPLATE/` are the single source of truth for the labels, so the
parser reads them rather than repeating them here. Sections are found in form order, which
keeps a `###` heading inside a pasted paper body from being taken for the next field
unless it repeats that field's exact label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .labels import KIND_OF_LABEL
from .paths import FORMS_DIR

NO_RESPONSE = "_No response_"
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*?)\s*$")
FENCE = re.compile(r"^```[\w+-]*\n(.*?)\n?```$", re.S)


@dataclass
class FormField:
    id: str
    label: str
    type: str  # input | textarea | dropdown | checkboxes
    required: bool = False
    options: list[str] = field(default_factory=list)
    required_options: list[str] = field(default_factory=list)
    multiple: bool = False
    render: str | None = None


@dataclass
class Form:
    name: str
    file: str
    kind: str
    labels: list[str]
    fields: list[FormField]

    def field(self, fid: str) -> FormField:
        for f in self.fields:
            if f.id == fid:
                return f
        raise KeyError(fid)


def _form(path: Path) -> Form | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "body" not in data:
        return None
    labels = list(data.get("labels") or [])
    kinds = [KIND_OF_LABEL[x] for x in labels if x in KIND_OF_LABEL]
    if len(kinds) != 1:
        raise ValueError(f"{path.name} must apply exactly one intake:* routing label")
    fields = []
    for item in data["body"]:
        if item.get("type") == "markdown":
            continue
        attrs = item.get("attributes") or {}
        valid = item.get("validations") or {}
        opts = attrs.get("options") or []
        if item["type"] == "checkboxes":
            labels_ = [o["label"] for o in opts]
            req = [o["label"] for o in opts if o.get("required")]
        else:
            labels_ = [str(o) for o in opts]
            req = []
        fields.append(FormField(
            id=item["id"],
            label=str(attrs["label"]).strip(),
            type=item["type"],
            required=bool(valid.get("required")),
            options=labels_,
            required_options=req,
            multiple=bool(attrs.get("multiple")),
            render=attrs.get("render"),
        ))
    return Form(name=data["name"], file=path.name, kind=kinds[0], labels=labels, fields=fields)


def load_forms(directory: Path | None = None) -> dict[str, Form]:
    out: dict[str, Form] = {}
    for p in sorted(Path(directory or FORMS_DIR).glob("*.yml")):
        if p.name == "config.yml":
            continue
        f = _form(p)
        if f is None:
            continue
        if f.kind in out:
            raise ValueError(f"two forms route to {f.kind}: {out[f.kind].file} and {p.name}")
        out[f.kind] = f
    return out


def form_for_labels(forms: dict[str, Form], labels: list[str]) -> Form | None:
    kinds = sorted({KIND_OF_LABEL[x] for x in labels if x in KIND_OF_LABEL})
    if len(kinds) != 1:
        return None
    return forms.get(kinds[0])


def _value(f: FormField, raw: str):
    raw = raw.strip()
    if raw == NO_RESPONSE:
        raw = ""
    if f.type == "checkboxes":
        state = {o: False for o in f.options}
        for line in raw.splitlines():
            m = CHECKBOX.match(line)
            if m:
                state[m[2]] = m[1] in "xX"
        return state
    if f.render and raw:
        m = FENCE.match(raw)
        if m:
            raw = m[1].strip("\n")
    if f.type == "dropdown" and f.multiple:
        return [x.strip() for x in raw.split(", ") if x.strip()] if raw else []
    return raw


def parse_body(form: Form, body: str) -> tuple[dict[str, object], list[FormField]]:
    """Values by field id, and the fields whose section is missing from the body."""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    heads: list[tuple[int, FormField]] = []
    pos = 0
    for f in form.fields:
        target = f"### {f.label}"
        for i in range(pos, len(lines)):
            if lines[i].strip() == target:
                heads.append((i, f))
                pos = i + 1
                break
    values: dict[str, object] = {}
    for k, (i, f) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        values[f.id] = _value(f, "\n".join(lines[i + 1:end]))
    missing = [f for f in form.fields if f.id not in values]
    return values, missing


def render_body(form: Form, answers: dict[str, object]) -> str:
    """The markdown GitHub would produce for these answers. Used by tests and fixtures,
    and handy for trying the bot locally."""
    parts = []
    for f in form.fields:
        v = answers.get(f.id)
        if f.type == "checkboxes":
            chosen = set(v or []) if not isinstance(v, dict) else {k for k, on in v.items() if on}
            text = "\n".join(f"- [{'X' if o in chosen else ' '}] {o}" for o in f.options)
        elif f.type == "dropdown" and f.multiple:
            text = ", ".join(v or []) or NO_RESPONSE
        else:
            text = str(v).strip() if v not in (None, "") else NO_RESPONSE
            if f.render and text != NO_RESPONSE:
                text = f"```{f.render}\n{text}\n```"
        parts.append(f"### {f.label}\n\n{text}")
    return "\n\n".join(parts) + "\n"
