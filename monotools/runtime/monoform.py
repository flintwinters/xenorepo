"""Declare and normalize the deliberately small MonoForm CRUD contract."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Literal, TypedDict


EXTENSION = "x-monotools-monoform"
SCHEMA_VERSION = 1
KINDS = frozenset({"create", "update", "delete", "action"})


class MonoFormContractError(ValueError):
    """A declared operation cannot be represented safely by MonoForm."""


class MonoFormDeclaration(TypedDict):
    kind: Literal["create", "update", "delete", "action"]
    entity: str
    title: str
    submitLabel: str
    destructive: bool


def monoform_operation(*, kind: Literal["create", "update", "delete", "action"],
    entity: str, title: str, submit_label: str, destructive: bool = False
    ) -> dict[str, MonoFormDeclaration]:
    """Return validated FastAPI ``openapi_extra`` for one MonoForm operation."""
    values = {"entity": entity, "title": title, "submit_label": submit_label}
    if kind not in KINDS:
        raise MonoFormContractError(f"kind must be one of {', '.join(sorted(KINDS))}")
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise MonoFormContractError(f"{name} must be a non-empty string")
    if not isinstance(destructive, bool):
        raise MonoFormContractError("destructive must be a boolean")
    return {EXTENSION: {"kind": kind, "entity": entity.strip(), "title": title.strip(),
        "submitLabel": submit_label.strip(), "destructive": destructive}}


def _resolve(schema: object, document: Mapping[str, object], location: str) -> dict[str, object]:
    if not isinstance(schema, Mapping):
        raise MonoFormContractError(f"{location} must be a schema")
    value = deepcopy(dict(schema))
    reference = value.pop("$ref", None)
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/components/schemas/"):
            raise MonoFormContractError(f"{location}.$ref must be a local schema reference")
        target: object = document
        for part in reference[2:].split("/"):
            target = target.get(part) if isinstance(target, Mapping) else None
        if not isinstance(target, Mapping):
            raise MonoFormContractError(f"{location}.$ref does not resolve: {reference}")
        value = deepcopy(dict(target)) | value
    for keyword in ("allOf", "oneOf"):
        if keyword in value:
            raise MonoFormContractError(f"{location}.{keyword} is not supported")
    if "anyOf" in value:
        branches = value.pop("anyOf")
        if (not isinstance(branches, list) or len(branches) != 2
            or sum(branch == {"type": "null"} for branch in branches) != 1):
            raise MonoFormContractError(f"{location}.anyOf supports only one schema plus null")
        branch = next(branch for branch in branches if branch != {"type": "null"})
        value = _resolve(branch, document, f"{location}.anyOf") | value | {"nullable": True}
    return value


def _primitive(schema: object, document: Mapping[str, object], location: str,
    *, arrays: bool = True) -> dict[str, object]:
    value = _resolve(schema, document, location)
    kind = value.get("type")
    if kind not in {"string", "integer", "number", "boolean", "array"}:
        raise MonoFormContractError(f"{location}.type {kind!r} is not supported")
    if kind == "array":
        if not arrays:
            raise MonoFormContractError(f"{location}.type arrays are not supported here")
        value["items"] = _primitive(value.get("items"), document, f"{location}.items", arrays=False)
    return value


def _body_schema(schema: object, document: Mapping[str, object], location: str) -> dict[str, object]:
    value = _resolve(schema, document, location)
    if value.get("type") != "object" or not isinstance(value.get("properties"), Mapping):
        raise MonoFormContractError(f"{location} must be a top-level object")
    value["properties"] = {name: _primitive(child, document, f"{location}.properties.{name}")
        for name, child in sorted(value["properties"].items())}
    value["required"] = sorted(value.get("required", []))
    return value


def _operation(path: str, method: str, raw: Mapping[str, object],
    document: Mapping[str, object]) -> dict[str, object]:
    location = f"{method.upper()} {path}"
    if not path.startswith("/api/") or "://" in path or path.startswith("//"):
        raise MonoFormContractError(f"{location} must use a same-origin /api path")
    operation_id = raw.get("operationId")
    if not isinstance(operation_id, str) or not operation_id:
        raise MonoFormContractError(f"{location} must declare operationId")
    declaration = raw.get(EXTENSION)
    if not isinstance(declaration, Mapping):
        raise MonoFormContractError(f"{location}.{EXTENSION} must be a mapping")
    parameters = []
    for index, parameter in enumerate(raw.get("parameters", [])):
        parameter_location = f"{location}.parameters[{index}]"
        if not isinstance(parameter, Mapping) or parameter.get("in") not in {"path", "query"}:
            raise MonoFormContractError(f"{parameter_location}.in must be path or query")
        parameters.append({"name": parameter.get("name"), "in": parameter.get("in"),
            "required": bool(parameter.get("required")), "schema": _primitive(
                parameter.get("schema"), document, f"{parameter_location}.schema", arrays=False)})
    body = None
    request_body = raw.get("requestBody")
    if request_body is not None:
        content = request_body.get("content") if isinstance(request_body, Mapping) else None
        json_body = content.get("application/json") if isinstance(content, Mapping) else None
        if not isinstance(json_body, Mapping):
            raise MonoFormContractError(f"{location}.requestBody must use application/json")
        body = _body_schema(json_body.get("schema"), document,
            f"{location}.requestBody.content.application/json.schema")
    statuses = sorted(int(status) for status in raw.get("responses", {})
        if str(status).isdigit() and 200 <= int(status) < 300)
    return {"operationId": operation_id, **dict(declaration), "method": method.upper(),
        "path": path, "parameters": parameters, "bodySchema": body, "successStatuses": statuses}


def monoform_manifest(document: Mapping[str, object], *, app: str, title: str) -> dict[str, object]:
    """Normalize annotated OpenAPI operations into a byte-stable manifest value."""
    operations = []
    paths = document.get("paths", {})
    if not isinstance(paths, Mapping):
        raise MonoFormContractError("OpenAPI paths must be a mapping")
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, Mapping):
            continue
        for method, raw in sorted(path_item.items()):
            if isinstance(raw, Mapping) and EXTENSION in raw:
                operations.append(_operation(str(path), str(method), raw, document))
    operations.sort(key=lambda value: str(value["operationId"]))
    return {"schemaVersion": SCHEMA_VERSION, "application": {"name": app, "title": title},
        "operations": operations}
