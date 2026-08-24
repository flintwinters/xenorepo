"""Kanban Console lifecycle manager."""

from monotools.management import create_app_cli


app = create_app_cli(
    __file__,
    tests="tests",
    ui_suite="tests/e2e/board.spec.ts",
)


if __name__ == "__main__":
    app()
