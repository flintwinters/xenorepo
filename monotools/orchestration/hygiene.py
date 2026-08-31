"""Measure UI vocabulary and enforce objective toolkit and CSS boundaries.

The analyzer keeps contextual aesthetic evidence separate from the two hard,
deterministic contracts that ordinary lifecycle validation can judge.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from monotools.orchestration.apps import AppDefinition
from monotools.orchestration.lifecycle import LifecycleError


def analyze_ui_hygiene(definition: AppDefinition, workspace: Path, *, enforce: bool = True
    ) -> dict[str, object]:
    """Run the shared analyzer, persist its evidence, and optionally reject violations."""
    command = ["node", "monotools/node/ui-hygiene.mjs", str(definition.directory)]
    completed = subprocess.run(command, cwd=workspace, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no analyzer output"
        raise LifecycleError(f"{definition.name} UI hygiene analyzer failed: {detail}") from error
    artifact = definition.directory / "data" / "ui-check" / "ui-hygiene.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if enforce and report["hardViolationCount"]:
        details = "; ".join(f"{item['code']} {item['location']}: {item['detail']}"
            for item in report["violations"])
        raise LifecycleError(f"{definition.name} UI hygiene failed: {details}")
    return report
