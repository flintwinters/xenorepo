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


DEFAULT_MODEL = "gpt-5.5"
REQUIRED_RESOLUTIONS = frozenset({"1440x1000", "768x1024", "390x844"})
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "findings"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "resolution", "issue", "recommendation"],
                "properties": {
                    "severity": {"type": "string", "enum": ["major", "minor"]},
                    "resolution": {"type": "string"},
                    "issue": {"type": "string"},
                    "recommendation": {"type": "string"},
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


def _prompt(definition: AppDefinition, screenshots: list[Path]) -> str:
    brief_path = definition.directory / "UI.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else (
        "No app-specific visual brief exists. Judge this as polished production software "
        "whose design should be coherent with its visible purpose."
    )
    inventory = "\n".join(f"- {path.name}" for path in screenshots)
    return f"""Act as a demanding senior product-design reviewer. Decide whether this UI looks
intentional, coherent, attractive, and ready to ship across every supplied resolution. Evaluate
visual hierarchy, composition, alignment, spacing rhythm, typography, color, contrast, density,
responsive adaptation, consistency, and obvious rendering artifacts. Judge the screenshots as a
set, not independently. A technically functional but generic, awkward, cramped, unfinished, or
visually incoherent UI fails. Minor preferences may be reported without failing; any major finding
requires verdict=fail. Do not infer source-code defects or missing interactions from screenshots.

Application: {definition.title}
Screenshot inventory:
{inventory}

App-owned visual brief:
{brief}
"""


def _request_payload(definition: AppDefinition, screenshots: list[Path], model: str) -> dict[str, Any]:
    content: list[dict[str, str]] = [{"type": "input_text", "text": _prompt(definition, screenshots)}]
    for path in screenshots:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{encoded}",
            "detail": "original"})
    return {
        "model": model,
        "store": False,
        "reasoning": {"effort": "high"},
        "input": [{"role": "user", "content": content}],
        "text": {"format": {"type": "json_schema", "name": "aesthetic_review",
            "strict": True, "schema": REVIEW_SCHEMA}},
    }


def _output_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content["text"])
    raise LifecycleError("AESTHETIC_REVIEW_RESPONSE: model returned no structured output")


def review_aesthetics(definition: AppDefinition, screenshot_directory: Path,
    report_path: Path) -> dict[str, Any]:
    """Submit captured UI evidence to a vision model and enforce its verdict."""
    screenshots = screenshot_inventory(screenshot_directory)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LifecycleError("AESTHETIC_REVIEW_AUTH: OPENAI_API_KEY is required")
    model = os.environ.get("MONOTOOLS_AESTHETIC_MODEL", DEFAULT_MODEL)
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(_request_payload(definition, screenshots, model)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
    report = {"schemaVersion": 1, "app": definition.name, "model": response.get("model", model),
        "responseId": response.get("id"), "screenshots": [path.name for path in screenshots], **review}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if review.get("verdict") != "pass":
        raise LifecycleError(
            f"AESTHETIC_REVIEW_FAILED: {review.get('summary', 'visual review did not pass')}; "
            f"inspect {report_path}"
        )
    return report
