"""Build-time composition for the repository's standalone console documents."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
import re


class FrontendCompositionError(ValueError):
    """Raised when a document cannot satisfy the standalone frontend contract."""


@dataclass(frozen=True)
class DocumentParts:
    """The app-owned portions of a composed browser document."""

    title: str
    body: str
    styles: str
    script: str


CONSOLE_SHELL = """/* tooling.frontend: console shell */
:root {
  color-scheme: dark;
  --bg: #1d2021;
  --panel: #282828;
  --well: #181a1b;
  --line: #504945;
  --hi: #665c54;
  --fg: #ebdbb2;
  --muted: #a89984;
  --red: #fb4934;
  --green: #b8bb26;
  --yellow: #fabd2f;
  --blue: #83a598;
  --purple: #d3869b;
  --aqua: #8ec07c;
  --orange: #fe8019;
  font: 12px/1.3 "Courier New", monospace;
}

* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; background: var(--bg); color: var(--fg); }
button, input, textarea, select { font: inherit; color: inherit; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible,
.key:focus-visible, .tab:focus-visible {
  outline: 2px solid var(--yellow);
  outline-offset: 1px;
}
.utility, .status, .rail {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 2px 6px;
  background: linear-gradient(#3c3836, #282828);
  border-bottom: 1px solid #101112;
  white-space: nowrap;
  overflow: hidden;
}
.brand { color: var(--yellow); font-weight: bold; letter-spacing: .08em; }
.pane { min-width: 0; min-height: 0; overflow: hidden; background: var(--panel); }
.pane-body { min-height: 0; overflow: auto; }
.pane-title, .title {
  --chrome-rim: #b7cfca;
  --chrome-shade: #354a44;
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
  margin: 0;
  padding-right: 7px;
  color: #1d2021;
  font-size: 12px;
  font-weight: bold;
  background: linear-gradient(#83a598, #5f7f75);
  border-top: 1px solid var(--chrome-rim);
  border-bottom: 2px solid var(--chrome-shade);
  box-shadow: 0 2px 2px #111;
}
.pane-title.green, .title.green {
  --chrome-rim: #d5d87a;
  --chrome-shade: #57580e;
}
.pane-title.orange, .title.orange {
  --chrome-rim: #ffaf66;
  --chrome-shade: #7a3307;
}
.pane-title.purple, .title.purple {
  --chrome-rim: #edb8c5;
  --chrome-shade: #65364c;
}
.index, .plaque {
  align-self: stretch;
  display: grid;
  place-items: center;
  min-width: 25px;
  padding: 0 5px;
  color: var(--fg);
  background: var(--panel);
  border-right: 1px solid #111;
}
.key, button {
  min-height: 20px;
  padding: 1px 8px;
  color: var(--fg);
  background: linear-gradient(#3c3836, #282828);
  border: 1px solid #111;
  border-top-color: #7c6f64;
  border-left-color: #665c54;
  box-shadow: inset -1px -1px #1d2021, 0 2px #101112;
  cursor: pointer;
}
.key:active, button:active, .key.pressed {
  transform: translateY(1px);
  box-shadow: inset 1px 1px #101112;
}
.key:disabled, button:disabled { color: #665c54; cursor: not-allowed; }
@media (max-width: 620px) {
  .utility .context, .rail .low, .status .hint { display: none; }
}
"""


_TITLE = re.compile(r"<title>(?P<value>.*?)</title>", re.DOTALL | re.IGNORECASE)
_STYLE = re.compile(r"<style>(?P<value>.*?)</style>", re.DOTALL | re.IGNORECASE)
_BODY = re.compile(r"<body[^>]*>(?P<value>.*?)</body>", re.DOTALL | re.IGNORECASE)
_SCRIPT = re.compile(r"<script>(?P<value>.*?)</script>", re.DOTALL | re.IGNORECASE)
_EXTERNAL_ASSET = re.compile(r"(?:src|href)\s*=\s*[\"']", re.IGNORECASE)


def parse_document(source: Path) -> DocumentParts:
    """Read an app document into its app-owned composition inputs."""
    text = source.read_text(encoding="utf-8")
    title = _required(_TITLE, text, source, "title")
    styles = _required(_STYLE, text, source, "style block")
    body = _required(_BODY, text, source, "body")
    script = _required(_SCRIPT, text, source, "script block")
    if _EXTERNAL_ASSET.search(text):
        raise FrontendCompositionError(f"{source} references an external asset")
    return DocumentParts(title=title.strip(), body=body.strip(), styles=styles.strip(), script=script.strip())


def compose_console(parts: DocumentParts) -> str:
    """Compose a complete self-contained Gruvbox console document."""
    return """<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<meta name=\"tooling-shell\" content=\"console\">
<title>{title}</title>
<style>
{shell}
</style>
<style>
/* app-owned styles */
{styles}
</style>
</head>
<body>
{body}
<script>
{script}
</script>
</body>
</html>
""".format(title=escape(parts.title), shell=CONSOLE_SHELL.strip(), styles=parts.styles,
           body=parts.body, script=parts.script)


def compose_document(source: Path, shell: str) -> str:
    """Build one supported document shell from an app's frontend source."""
    if shell != "console":
        raise FrontendCompositionError(f"unsupported frontend shell: {shell!r}")
    return compose_console(parse_document(source))


def _required(pattern: re.Pattern[str], text: str, source: Path, label: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise FrontendCompositionError(f"{source} is missing a {label}")
    return match.group("value")
