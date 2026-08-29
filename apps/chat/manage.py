"""Common Room lifecycle manager."""

from monotools.orchestration.management import create_app_manager


manager = create_app_manager(
    __file__, tests="tests", ui_suite="tests/e2e/chat.spec.js",
    proof_kinds=frozenset({"acceptance", "visual"}),
)
app = manager.app


if __name__ == "__main__":
    app()
