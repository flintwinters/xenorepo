#!/usr/bin/env python3
"""Xenorepo Cockpit lifecycle manager."""

from monotools.management import create_app_manager


manager = create_app_manager(
    __file__, tests="tests", ui_suite="tests/e2e/cockpit.spec.ts",
    proof_kinds=frozenset({"acceptance", "visual"}),
    input_modalities=frozenset({"mouse"}),
)
app = manager.app


if __name__ == "__main__":
    app()
