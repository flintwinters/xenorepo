"""Create deterministic monoapp walking skeletons from platform-owned templates.

The scaffolder owns only repeatable application structure and boundary wiring;
product intent remains app-owned in the generated specification and agent context.
"""

from pathlib import Path
import shutil

from monotools.orchestration.apps import AppDefinitionError, load_app, validate_app_name


class ScaffoldError(RuntimeError):
    """Raised when a monoapp skeleton cannot be created without ambiguity."""


TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "templates" / "monoapp"
TOKENS = ("app_name", "app_title")


def _template_files() -> tuple[Path, ...]:
    return tuple(sorted(path for path in TEMPLATE_DIRECTORY.rglob("*") if path.is_file()))


def _render(source: Path, values: dict[str, str]) -> str:
    rendered = source.read_text(encoding="utf-8")
    for token in TOKENS:
        rendered = rendered.replace("{{" + token + "}}", values[token])
    unresolved = [token for token in TOKENS if "{{" + token + "}}" in rendered]
    if unresolved:
        raise ScaffoldError(f"unresolved template tokens in {source}: {', '.join(unresolved)}")
    return rendered


def scaffold_app(apps_directory: Path, name: str, title: str) -> Path:
    """Create and structurally validate one complete monoapp skeleton."""
    try:
        validate_app_name(name)
    except AppDefinitionError as error:
        raise ScaffoldError(str(error)) from error
    if not title.strip():
        raise ScaffoldError("app title must not be empty")
    target = apps_directory / name
    if target.exists():
        raise ScaffoldError(f"refusing to overwrite existing path: {target}")
    sources = _template_files()
    if not sources:
        raise ScaffoldError(f"monoapp template is empty: {TEMPLATE_DIRECTORY}")
    values = {"app_name": name, "app_title": title.strip()}
    rendered = [(source.relative_to(TEMPLATE_DIRECTORY), _render(source, values))
        for source in sources]
    try:
        for relative, content in rendered:
            output = target / relative.with_suffix("")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
        load_app(target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target
