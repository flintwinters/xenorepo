"""Regression policy for concise, structured agent startup context."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_WORDS = 600
MAX_CONTEXT_CHAIN_WORDS = 1_000
REQUIRED_SECTIONS = 3


def _word_count(path: Path) -> int:
    return len(re.findall(r"\b[\w'-]+\b", path.read_text(encoding="utf-8")))


def _context_chain(path: Path) -> tuple[Path, ...]:
    ancestors = (path.parent, *path.parent.parents)
    return tuple(
        directory / "AGENTS.md"
        for directory in reversed(ancestors)
        if directory == ROOT or ROOT in directory.parents
        if (directory / "AGENTS.md").is_file()
    )


class AgentContextTests(unittest.TestCase):
    def test_agent_context_is_short_and_has_only_the_required_sections(self) -> None:
        context_files = tuple(ROOT.rglob("AGENTS.md"))

        self.assertTrue(context_files)
        for path in context_files:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                headings = re.findall(r"^##\s+", text, flags=re.MULTILINE)
                self.assertEqual(len(headings), REQUIRED_SECTIONS)
                self.assertLessEqual(_word_count(path), MAX_FILE_WORDS)

    def test_nested_startup_context_stays_within_its_total_budget(self) -> None:
        for path in ROOT.rglob("AGENTS.md"):
            chain = _context_chain(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertLessEqual(
                    sum(_word_count(item) for item in chain),
                    MAX_CONTEXT_CHAIN_WORDS,
                )


if __name__ == "__main__":
    unittest.main()
