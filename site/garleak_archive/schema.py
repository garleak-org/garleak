# SPDX-License-Identifier: AGPL-3.0-or-later
"""A small JSON Schema checker for the subset the archive schemas use.

Supported keywords: type (string or list), required, properties, additionalProperties
(boolean or schema), items, enum, const, pattern, minLength, minItems, minimum, maximum,
format "date", and $ref to "#/$defs/<name>". This keeps the archive tooling free of a
jsonschema dependency; the schema files themselves are standard draft 2020-12 and work
with any full validator.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).parent / "schemas"

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def jsonable(value: Any) -> Any:
    """YAML gives dates as date objects; schemas describe them as strings."""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "") -> list[str]:
    root = root or schema
    errs: list[str] = []
    where = path or "(top)"
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported $ref {ref}")
        return validate(instance, root["$defs"][ref.split("/")[-1]], root, path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            hint = ""
            if isinstance(instance, float) and "string" in types:
                hint = " (quote it, for example \"1.0\")"
            return [f"{where}: expected {' or '.join(types)}, got {type(instance).__name__} {instance!r}{hint}"]
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{where}: {instance!r} is not one of {schema['enum']}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{where}: {instance!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{where}: shorter than {schema['minLength']}")
        if schema.get("format") == "date" and not _DATE.match(instance):
            errs.append(f"{where}: {instance!r} is not a date (YYYY-MM-DD)")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{where}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{where}: above maximum {schema['maximum']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{where}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs.extend(validate(item, schema["items"], root, f"{path}[{i}]"))
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errs.append(f"{where}: missing required field '{key}'")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, value in instance.items():
            sub = f"{path}.{key}" if path else key
            if key in props:
                errs.extend(validate(value, props[key], root, sub))
            elif extra is False:
                errs.append(f"{where}: unknown field '{key}'")
            elif isinstance(extra, dict):
                errs.extend(validate(value, extra, root, sub))
    return errs


def check(name: str, instance: Any) -> list[str]:
    return validate(jsonable(instance), load_schema(name))
