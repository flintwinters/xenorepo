"""Calendar Console lifecycle manager."""

from monotools.management import create_app_manager


manager = create_app_manager(
    __file__,
    tests="tests",
    ui_suite="tests/e2e/calendar.spec.ts",
)
app = manager.app


if __name__ == "__main__":
    app()
