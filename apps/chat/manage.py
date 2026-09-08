"""Common Room lifecycle manager."""

from monotools.orchestration.management import create_app_manager


manager = create_app_manager(__file__)
app = manager.app


if __name__ == "__main__":
    app()
