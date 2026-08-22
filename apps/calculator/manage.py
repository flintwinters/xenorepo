"""Calculation Control lifecycle manager."""

from monotools.management import create_app_cli


app = create_app_cli(__file__, tests="../../tests")


if __name__ == "__main__":
    app()
