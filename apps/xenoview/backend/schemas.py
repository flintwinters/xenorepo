"""Explicit HTTP response contracts for repository cockpit projections."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Specification(Contract):
    covered: int
    total: int


class LanguageLines(Contract):
    language: str
    lines: int
    files: int


class TestBreakdown(Contract):
    total: int
    monorepo: int
    monoapps: dict[str, int]


class FileSummary(Contract):
    path: str
    lines: int
    bytes: int


class Overview(Contract):
    metrics: dict[str, int]
    delta: dict[str, int]
    revision: str
    dirty: bool
    fingerprint: str
    specification: Specification
    exclusions: list[str]
    language_lines: list[LanguageLines]
    test_breakdown: TestBreakdown
    largest_files: list[FileSummary]


class ModuleFact(Contract):
    name: str
    path: str
    lines: int
    bytes: int
    public_definitions: int
    inbound_apps: int
    used_by_apps: list[str]
    description: str
    explanation: str
    dependencies: list[str]


class ChangeFact(Contract):
    name: str
    added: int
    deleted: int


class CommitFact(Contract):
    revision: str
    committed_at: str
    subject: str
    additions: int
    deletions: int
    apps: list[ChangeFact]
    languages: list[ChangeFact]


class RepositoryHistory(Contract):
    available: bool
    truncated: bool
    limit: int
    commits: list[CommitFact]


class TreeNode(Contract):
    name: str
    path: str
    kind: str
    bytes: int
    lines: int
    children: list[TreeNode] | None = None
    ls_colors: str | None = None


class ArchitectureNode(Contract):
    id: str
    label: str
    kind: str


class ArchitectureEdge(Contract):
    source: str
    target: str
    label: str


class Architecture(Contract):
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]


class SnapshotView(Contract):
    id: int
    schema_version: int
    fingerprint: str
    revision: str
    dirty: bool
    captured_at: str
    metrics: dict[str, int]


class SnapshotResult(Contract):
    snapshot: SnapshotView
    created: bool
