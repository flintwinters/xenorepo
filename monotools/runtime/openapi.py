"""Validate agent-facing OpenAPI documents as rigorous tool contracts.

The validator is independent of application identity and rejects ambiguous input
and output shapes before schemas reach generated clients or provisioning gates.
"""

from collections.abc import Mapping

HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put", "trace"})


class OpenAPIContractError(ValueError):
    """Report all actionable OpenAPI contract violations in one pass."""


def _schema_violations(schema: object, location: str) -> list[str]:
    if not isinstance(schema, Mapping) or not schema:
        return [f"{location} must declare a non-empty schema"]
    violations = _composition_violations(schema, location)
    if not any(key in schema for key in ("$ref", "allOf", "anyOf", "const", "enum", "oneOf", "type")):
        violations.append(f"{location} must declare a concrete type, reference, or composition")
    if schema.get("type") == "array":
        violations.extend(_schema_violations(schema.get("items"), f"{location}.items"))
    if schema.get("type") == "object":
        violations.extend(_object_schema_violations(schema, location))
    return violations


def _composition_violations(schema: Mapping[object, object], location: str) -> list[str]:
    violations: list[str] = []
    for composition in ("allOf", "anyOf", "oneOf"):
        if composition not in schema:
            continue
        branches = schema[composition]
        if not isinstance(branches, list) or not branches:
            violations.append(f"{location}.{composition} must contain schemas")
            continue
        for index, branch in enumerate(branches):
            violations.extend(_schema_violations(branch,
                f"{location}.{composition}[{index}]"))
    return violations


def _object_schema_violations(schema: Mapping[object, object], location: str) -> list[str]:
    properties = schema.get("properties")
    additional = schema.get("additionalProperties")
    if not isinstance(properties, Mapping) and not isinstance(additional, Mapping):
        return [f"{location} must constrain object properties or additionalProperties"]
    violations: list[str] = []
    if isinstance(properties, Mapping):
        for name, child in properties.items():
            violations.extend(_schema_violations(child, f"{location}.properties.{name}"))
    if isinstance(additional, Mapping):
        violations.extend(_schema_violations(additional, f"{location}.additionalProperties"))
    return violations


def _content_violations(content: object, location: str) -> list[str]:
    if not isinstance(content, Mapping) or not content:
        return [f"{location} must declare typed content"]
    violations: list[str] = []
    for media_type, declaration in content.items():
        if not isinstance(declaration, Mapping):
            violations.append(f"{location}.{media_type} must be a mapping")
            continue
        violations.extend(_schema_violations(declaration.get("schema"),
            f"{location}.{media_type}.schema"))
    return violations


def _operation_violations(operation: Mapping[object, object], location: str) -> list[str]:
    violations: list[str] = []
    operation_id = operation.get("operationId")
    if not isinstance(operation_id, str) or not operation_id.strip():
        violations.append(f"{location} must declare operationId")
    for index, parameter in enumerate(operation.get("parameters", [])):
        if not isinstance(parameter, Mapping):
            violations.append(f"{location}.parameters[{index}] must be a mapping")
        else:
            violations.extend(_schema_violations(parameter.get("schema"),
                f"{location}.parameters[{index}].schema"))
    request_body = operation.get("requestBody")
    if request_body is not None:
        content = request_body.get("content") if isinstance(request_body, Mapping) else None
        violations.extend(_content_violations(content, f"{location}.requestBody.content"))
    violations.extend(_response_violations(operation.get("responses"), location))
    return violations


def _response_violations(responses: object, location: str) -> list[str]:
    if not isinstance(responses, Mapping) or not responses:
        return [f"{location} must declare responses"]
    violations: list[str] = []
    for status, response in responses.items():
        violations.extend(_single_response_violations(status, response, location))
    return violations


def _single_response_violations(status: object, response: object, location: str) -> list[str]:
    response_location = f"{location}.responses.{status}"
    if not isinstance(response, Mapping):
        return [f"{response_location} must be a mapping"]
    content = response.get("content")
    if str(status).startswith("2") and str(status) != "204" and content is None:
        return [f"{response_location} must declare typed content"]
    violations = (_content_violations(content, f"{response_location}.content")
        if content is not None else [])
    violations.extend(_header_violations(response.get("headers"), response_location))
    return violations


def _header_violations(headers: object, location: str) -> list[str]:
    if headers is None:
        return []
    if not isinstance(headers, Mapping):
        return [f"{location}.headers must be a mapping"]
    violations: list[str] = []
    for name, header in headers.items():
        schema = header.get("schema") if isinstance(header, Mapping) else None
        violations.extend(_schema_violations(schema, f"{location}.headers.{name}.schema"))
    return violations


def _path_violations(path: object, path_item: object,
    operation_ids: dict[str, str]) -> list[str]:
    if not isinstance(path_item, Mapping):
        return [f"paths.{path} must be a mapping"]
    violations: list[str] = []
    for method, operation in path_item.items():
        if method in HTTP_METHODS:
            violations.extend(_registered_operation_violations(
                path, method, operation, operation_ids))
    return violations


def _registered_operation_violations(path: object, method: object, operation: object,
    operation_ids: dict[str, str]) -> list[str]:
    location = f"{str(method).upper()} {path}"
    if not isinstance(operation, Mapping):
        return [f"{location} must be a mapping"]
    violations = _operation_violations(operation, location)
    operation_id = operation.get("operationId")
    if isinstance(operation_id, str) and operation_id:
        if operation_id in operation_ids:
            violations.append(
                f"{location} duplicates operationId from {operation_ids[operation_id]}"
            )
        operation_ids[operation_id] = location
    return violations


def validate_api_openapi_schema(schema: object) -> None:
    """Reject an API registry containing ambiguous operation or data contracts."""
    paths = schema.get("paths") if isinstance(schema, Mapping) else None
    if not isinstance(paths, Mapping):
        raise OpenAPIContractError("OpenAPI paths must be a mapping")
    violations: list[str] = []
    operation_ids: dict[str, str] = {}
    for path, path_item in paths.items():
        violations.extend(_path_violations(path, path_item, operation_ids))
    if violations:
        raise OpenAPIContractError("OpenAPI tool contract failed:\n- " + "\n- ".join(violations))
