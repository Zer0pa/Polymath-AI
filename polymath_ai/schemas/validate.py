"""Lightweight structural validation.

Schemas are dictionaries with the form:

    {
        "type": "object",
        "required": ["a", "b"],
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "object", "schema": <nested>}
        }
    }

This validator covers what the substrate needs - presence of required keys,
type-of for primitives, and recursive validation of object/array members. It
is not jsonschema-spec-complete; if a richer language is ever required, swap
in ``jsonschema`` and update the import sites in one place.
"""
from __future__ import annotations

from typing import Any, List


class ValidationError(ValueError):
    """Raised when a record fails its schema."""


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _check(node: Any, schema: dict, path: str, errs: List[str]) -> None:
    if "type" in schema:
        ty = schema["type"]
        if isinstance(ty, list):
            allowed = tuple(_TYPE_MAP[t] for t in ty)
        else:
            allowed = _TYPE_MAP[ty]
            allowed = (allowed,) if not isinstance(allowed, tuple) else allowed
        if not isinstance(node, allowed):
            errs.append(f"{path}: expected {ty}, got {type(node).__name__}")
            return

    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                errs.append(f"{path}.{req}: required key missing")
        for k, sub in (schema.get("properties") or {}).items():
            if k in node:
                _check(node[k], sub, f"{path}.{k}", errs)
        # disallow truly empty schema-required dict where parents required keys.

    if isinstance(node, list) and schema.get("items"):
        for i, item in enumerate(node):
            _check(item, schema["items"], f"{path}[{i}]", errs)

    if "enum" in schema and node not in schema["enum"]:
        errs.append(f"{path}: value {node!r} not in enum {schema['enum']}")


def validate(record: Any, schema: dict, path: str = "$") -> None:
    """Validate ``record`` against ``schema`` and raise on failure."""
    errs: List[str] = []
    _check(record, schema, path, errs)
    if errs:
        raise ValidationError("; ".join(errs))
