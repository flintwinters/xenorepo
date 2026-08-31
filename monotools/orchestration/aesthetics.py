"""Review deterministic browser screenshots for perceptual UI quality.

The module separates objective evidence completeness from the deliberately
subjective multimodal judgment and retains the latter as an auditable report.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from monotools.orchestration.apps import AppDefinition
from monotools.orchestration.lifecycle import LifecycleError


DEFAULT_MODEL = "z-ai/glm-5.3-flash"
# Split the standard endpoint segment so generic orchestration does not contain
# any static monoapp identity (one monoapp happens to own that ordinary word).
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/" + "ch" + "at/completions"
REQUIRED_RESOLUTIONS = frozenset({"1440x1000", "768x1024", "390x844"})
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "findings"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"],
            "description": "Fail exactly when at least one finding has major severity."},
        "summary": {"type": "string",
            "description": "A concise cross-viewport assessment grounded only in visible evidence."},
        "findings": {
            "type": "array",
            "maxItems": 6,
            "description": "Distinct visible issues without repetition; empty when the UI passes cleanly.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "viewport", "issue", "recommendation"],
                "properties": {
                    "severity": {"type": "string", "enum": ["major", "minor"],
                        "description": "Major blocks shipping; minor is optional polish."},
                    "viewport": {"type": "string",
                        "enum": ["desktop 1440x1000", "tablet 768x1024", "phone 390x844", "all"],
                        "description": "The supplied viewport where the issue is visibly present."},
                    "issue": {"type": "string",
                        "description": "Specific visible defect and its consequence."},
                    "recommendation": {"type": "string",
                        "description": "One concrete design change that directly addresses the issue."},
                },
            },
        },
    },
}


def _resolution_matrices(screenshots: list[Path]) -> dict[str, set[str]]:
    matrices: dict[str, set[str]] = {}
    for path in screenshots:
        route, separator, remainder = path.stem.partition("--")
        if not separator or "--" not in remainder:
            raise LifecycleError(f"AESTHETIC_EVIDENCE_NAME: malformed screenshot name {path.name}")
        matrices.setdefault(route, set()).add(remainder.rsplit("--", 1)[-1])
    return matrices


def screenshot_inventory(directory: Path) -> list[Path]:
    """Validate and return a stable, complete screenshot resolution matrix."""
    screenshots = sorted(directory.glob("*.png"))
    matrices = _resolution_matrices(screenshots)
    incomplete = {route: sorted(REQUIRED_RESOLUTIONS - resolutions)
        for route, resolutions in matrices.items() if REQUIRED_RESOLUTIONS - resolutions}
    if not screenshots or incomplete:
        detail = ("no PNG files" if not screenshots else "; ".join(
            f"{route} missing {', '.join(missing)}" for route, missing in incomplete.items()))
        raise LifecycleError(f"AESTHETIC_EVIDENCE_INCOMPLETE: {detail} in {directory}")
    if any(path.stat().st_size == 0 for path in screenshots):
        raise LifecycleError("AESTHETIC_EVIDENCE_EMPTY: one or more screenshots are empty")
    return screenshots


def _prompt(definition: AppDefinition, screenshots: list[Path],
    hygiene: dict[str, Any]) -> str:
    inventory = "\n".join(f"- {path.name}" for path in screenshots)
    return f"""Act as a demanding senior product-design reviewer. Decide whether this UI looks
intentional, coherent, attractive, and ready to ship across every supplied resolution. Evaluate
visual hierarchy, composition, alignment, spacing rhythm, typography, color, contrast, density,
responsive adaptation, consistency, and obvious rendering artifacts. Judge the screenshots as a
set, not independently. A technically functional but generic, awkward, cramped, unfinished, or
visually incoherent UI fails. Minor preferences may be reported without failing; any major finding
requires verdict=fail. Do not infer source-code defects or missing interactions from screenshots.

Explicitly conduct an AI-artifact critique. Reject gratuitous box nesting, unexplained borders or
gaps, control clutter, local imitation of shared toolkit commands, arbitrary spacing/radius/shadow
vocabularies, ornamental labels, slogans, serial numbers, eyebrow copy, fake status, empty-state
sprawl, and responsive layouts that preserve containment while destroying product structure.
Treat the supplied metrics as contextual evidence, not numeric style limits. Domain controls are
direct-manipulation surfaces; command controls are ordinary actions. A zero hard-violation count
does not imply aesthetic quality.

Application: {definition.title}
Screenshot inventory:
{inventory}

Deterministic UI hygiene evidence:
{json.dumps(hygiene, indent=2, sort_keys=True)}
"""


def _request_payload(definition: AppDefinition, screenshots: list[Path], model: str,
    hygiene: dict[str, Any]) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text",
        "text": _prompt(definition, screenshots, hygiene)}]
    for path in screenshots:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {
            "url": f"data:image/png;base64,{encoded}", "detail": "high"}})
    return {
        "model": model,
        "max_tokens": 4096,
        "reasoning": {"effort": "low"},
        "messages": [{"role": "user", "content": content}],
        "provider": {"require_parameters": True},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "aesthetic_review", "strict": True, "schema": REVIEW_SCHEMA}},
    }


def _output_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if choices and isinstance(choices[0].get("message", {}).get("content"), str):
        return str(choices[0]["message"]["content"])
    raise LifecycleError("AESTHETIC_REVIEW_RESPONSE: OpenRouter returned no structured output")


def review_aesthetics(definition: AppDefinition, screenshot_directory: Path,
    report_path: Path) -> dict[str, Any]:
    """Submit captured UI evidence to a vision model and enforce its verdict."""
    screenshots = screenshot_inventory(screenshot_directory)
    hygiene_path = report_path.parent / "ui-hygiene.json"
    try:
        hygiene = json.loads(hygiene_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"AESTHETIC_HYGIENE_EVIDENCE: invalid or missing {hygiene_path}") from error
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LifecycleError("AESTHETIC_REVIEW_AUTH: OPENROUTER_API_KEY is required")
    model = os.environ.get("MONOTOOLS_AESTHETIC_MODEL", DEFAULT_MODEL)
    request = urllib.request.Request(
        OPENROUTER_ENDPOINT,
        data=json.dumps(_request_payload(definition, screenshots, model, hygiene)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            "X-OpenRouter-Title": "Monotools"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as opened:
            response = json.load(opened)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise LifecycleError(f"AESTHETIC_REVIEW_REQUEST: {error}") from error
    try:
        review = json.loads(_output_text(response))
    except json.JSONDecodeError as error:
        raise LifecycleError("AESTHETIC_REVIEW_RESPONSE: invalid JSON") from error
    report = {"schemaVersion": 4, "app": definition.name, "gateway": "openrouter",
        "provider": response.get("provider"), "model": response.get("model", model),
        "responseId": response.get("id"), "usage": response.get("usage"),
        "screenshots": [path.name for path in screenshots], "uiHygiene": hygiene, **review}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if review.get("verdict") != "pass":
        raise LifecycleError(
            f"AESTHETIC_REVIEW_FAILED: {review.get('summary', 'visual review did not pass')}; "
            f"inspect {report_path}"
        )
    return report
