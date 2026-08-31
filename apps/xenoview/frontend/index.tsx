/** Evidence-first command-and-control views for Xenorepo. */
import { Component, render, type ComponentChildren } from "preact";
import { CommandButton, ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import {
  captureSnapshot,
  loadCockpit,
  loadHistory,
  type ModuleFact,
  type Overview,
  type RepositoryHistory,
  type Snapshot,
  type TreeNode,
} from "./client.js";
import "./styles.css";

type Page = "overview" | "explorer" | "history";
interface State {
  page: Page;
  overview: Overview | null;
  modules: ModuleFact[];
  tree: TreeNode | null;
  repositoryHistory: RepositoryHistory | null;
  snapshots: Snapshot[];
  collapsedPaths: string[];
  message: string;
  failed: boolean;
  busy: boolean;
}

const number = new Intl.NumberFormat("en-US");
const bytes = (value: number) =>
  value < 1024
    ? `${value} B`
    : value < 1024 ** 2
      ? `${(value / 1024).toFixed(1)} KB`
      : `${(value / 1024 ** 2).toFixed(1)} MB`;
const treeLines = (value: number) => `${number.format(value)}L`;
const treeBytes = (value: number): string => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(Math.max(value, 1)) / Math.log(1024)), units.length - 1);
  return `${Math.round(value / 1024 ** exponent)}${units[exponent]}`;
};
const label = (key: string) => key.replaceAll("_", " ");
const isAppRoot = (path: string): boolean => {
  const parts = path.split("/");
  return parts.length === 2 && parts[0] === "apps";
};
const initiallyCollapsed = (node: TreeNode): string[] => [
  ...(node.kind === "directory" && (isAppRoot(node.path) || node.name === "e2e") ? [node.path] : []),
  ...(node.children ?? []).flatMap(initiallyCollapsed),
];
const ansiColor = (code: string): string => {
  const values = code.split(";").map(Number);
  const rgb = values.findIndex((value, index) => value === 38 && values[index + 1] === 2);
  if (rgb >= 0) return `rgb(${values.slice(rgb + 2, rgb + 5).join(" ")})`;
  const palette: Record<number, string> = {
    30: "#282828",
    31: "#cc241d",
    32: "#98971a",
    33: "#d79921",
    34: "#458588",
    35: "#b16286",
    36: "#689d6a",
    37: "#a89984",
    90: "#928374",
    91: "#fb4934",
    92: "#b8bb26",
    93: "#fabd2f",
    94: "#83a598",
    95: "#d3869b",
    96: "#8ec07c",
    97: "#ebdbb2",
  };
  return (
    [...values]
      .reverse()
      .map((value) => palette[value])
      .find(Boolean) ?? "inherit"
  );
};

class XenorepoCockpit extends Component<Record<string, never>, State> {
  override state: State = {
    page: "overview",
    overview: null,
    modules: [],
    tree: null,
    repositoryHistory: null,
    snapshots: [],
    collapsedPaths: [],
    message: "Scanning repository…",
    failed: false,
    busy: false,
  };
  override componentDidMount(): void {
    void this.load();
  }
  private perform = async (action: () => Promise<void>): Promise<void> => {
    this.setState({ busy: true });
    try {
      await action();
      this.setState({ failed: false });
    } catch (error) {
      this.setState({ failed: true, message: error instanceof Error ? error.message : "Unexpected error" });
    } finally {
      this.setState({ busy: false });
    }
  };
  private load = async (): Promise<void> =>
    this.perform(async () => {
      const [overview, modules, tree, repositoryHistory, snapshots] = await loadCockpit();
      const state = overview.dirty ? " · working tree modified" : " · clean";
      this.setState({
        overview,
        modules,
        tree,
        repositoryHistory,
        snapshots,
        collapsedPaths: initiallyCollapsed(tree),
        message: `Scan complete · ${overview.revision}${state}`,
      });
    });
  private capture = async (): Promise<void> =>
    this.perform(async () => {
      const created = await captureSnapshot();
      const snapshots = await loadHistory();
      const overview = this.state.overview;
      if (overview) overview.delta = Object.fromEntries(Object.keys(overview.metrics).map((key) => [key, 0]));
      this.setState({
        snapshots,
        overview,
        page: "history",
        message: created ? "Snapshot recorded" : "Current repository state was already recorded",
      });
    });
  private metric(key: string, value: number): ComponentChildren {
    const delta = this.state.overview?.delta[key] ?? 0;
    return (
      <article class="metric">
        <span>{label(key)}</span>
        <strong>{key.includes("bytes") ? bytes(value) : number.format(value)}</strong>
        <small class={delta > 0 ? "up" : delta < 0 ? "down" : ""}>
          {delta ? `${delta > 0 ? "+" : ""}${number.format(delta)} since snapshot` : "no saved change"}
        </small>
      </article>
    );
  }
  private overviewPage(): ComponentChildren {
    const overview = this.state.overview;
    if (!overview) return <p class="empty">Scanning repository…</p>;
    const primary = [
      "source_files",
      "source_lines",
      "repository_bytes",
      "monoapps",
      "monotools_modules",
      "test_cases",
      "specified_apps",
      "architecture_violations",
      "large_files",
      "complex_functions",
      "shared_import_edges",
      "median_file_lines",
    ];
    return (
      <section class="page overview">
        <div class="page-heading">
          <div>
            <p class="eyebrow">Repository scorecard</p>
            <h1>Broad strokes, concrete units.</h1>
          </div>
          <p>
            {overview.specification.covered}/{overview.specification.total} active apps specified
          </p>
        </div>
        <div class="metrics">{primary.map((key) => this.metric(key, overview.metrics[key] ?? 0))}</div>
        <div class="evidence-grid">
          <ConsolePane title="Lines by language" tone="purple" contentHeight>
            <table class="console-table">
              <thead>
                <tr>
                  <th class="identity">Language</th>
                  <th class="numeric">Files</th>
                  <th class="numeric">Lines</th>
                </tr>
              </thead>
              <tbody>
                {overview.language_lines.map((item) => (
                  <tr>
                    <td>{item.language}</td>
                    <td class="numeric">{number.format(item.files)}</td>
                    <td class="numeric">{number.format(item.lines)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ConsolePane>
          <ConsolePane title="Test cases" tone="green" contentHeight>
            <table class="console-table">
              <thead>
                <tr>
                  <th>Scope</th>
                  <th class="numeric">Cases</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Monorepo</td>
                  <td class="numeric">{number.format(overview.test_breakdown.monorepo)}</td>
                </tr>
                {Object.entries(overview.test_breakdown.monoapps).map(([name, count]) => (
                  <tr>
                    <td>apps/{name}</td>
                    <td class="numeric">{number.format(count)}</td>
                  </tr>
                ))}
                <tr class="total">
                  <td>Total</td>
                  <td class="numeric">{number.format(overview.test_breakdown.total)}</td>
                </tr>
              </tbody>
            </table>
          </ConsolePane>
        </div>
        <div class="split">
          <ConsolePane title="Largest maintained files" tone="orange" contentHeight>
            <table class="console-table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th class="numeric">Lines</th>
                  <th class="numeric">Size</th>
                </tr>
              </thead>
              <tbody>
                {overview.largest_files.map((item) => (
                  <tr>
                    <td>{item.path}</td>
                    <td class="numeric">{number.format(item.lines)}</td>
                    <td class="numeric">{bytes(item.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ConsolePane>
          <ConsolePane title="Measurement boundary" tone="blue">
            <div class="note">
              <p>
                Counts include maintained source and project documentation. Audit numbers use the root structural audit.
              </p>
              <p>
                <b>Excluded:</b> {overview.exclusions.join(", ")}
              </p>
              <p>No composite quality score is calculated: unrelated evidence stays independently inspectable.</p>
            </div>
          </ConsolePane>
        </div>
      </section>
    );
  }
  private treeColor(node: TreeNode): string {
    const entries = new Map(
      (this.state.tree?.ls_colors ?? "").split(":").flatMap((entry) => {
        const separator = entry.indexOf("=");
        return separator < 0 ? [] : [[entry.slice(0, separator), entry.slice(separator + 1)]];
      }),
    );
    const extension = [...entries.keys()]
      .filter((key) => key.startsWith("*.") && node.name.endsWith(key.slice(1)))
      .sort((left, right) => right.length - left.length)[0];
    const colorKey = node.kind === "directory" ? "di" : extension;
    return ansiColor(colorKey ? (entries.get(colorKey) ?? "") : "");
  }
  private treeRows(node: TreeNode, modules: Map<string, ModuleFact>, depth = 0): ComponentChildren {
    const style = { "--depth": depth, "--ls-color": this.treeColor(node) };
    const module = modules.get(node.path);
    const directory = node.kind === "directory";
    const collapsed = directory && this.state.collapsedPaths.includes(node.path);
    const toggle = (): void =>
      this.setState(({ collapsedPaths }) => ({
        collapsedPaths: collapsed
          ? collapsedPaths.filter((path) => path !== node.path)
          : [...collapsedPaths, node.path],
      }));
    return (
      <>
        <tr class={`tree-row ${node.kind}`} style={style}>
          <td
            class="tree-entry"
            data-path={node.path}
            data-lines={treeLines(node.lines)}
            data-bytes={treeBytes(node.bytes)}
          >
            {directory ? (
              <button
                data-ui-control="domain"
                type="button"
                aria-expanded={!collapsed}
                aria-label={`${collapsed ? "Expand" : "Collapse"} ${node.name} directory`}
                onClick={toggle}
              >
                <span aria-hidden="true">{collapsed ? "▸ " : "▾ "}</span>
                {node.name}
              </button>
            ) : (
              <span>{node.name}</span>
            )}
          </td>
          <td class="identity">{module && <strong>{module.name}</strong>}</td>
          <td class="prose">{module?.description}</td>
          <td class="prose">{module?.explanation}</td>
          <td class="numeric">{module && number.format(module.public_definitions)}</td>
          <td class="numeric">{module && number.format(module.inbound_apps)}</td>
          <td>{module && (module.used_by_apps.join(", ") || "—")}</td>
          <td>{module && (module.dependencies.join(", ") || "—")}</td>
        </tr>
        {!collapsed && node.children?.map((child) => this.treeRows(child, modules, depth + 1))}
      </>
    );
  }
  private explorerPage(): ComponentChildren {
    const modules = new Map(this.state.modules.map((item) => [item.path, item]));
    return (
      <section class="page">
        <div class="page-heading">
          <div>
            <p class="eyebrow">Maintained footprint</p>
            <h1>Repository explorer</h1>
          </div>
          <p>Generated and runtime-heavy paths excluded</p>
        </div>
        <div class="explorer-summary">
          <span>Files and semantic Monotools modules</span>
          <span>{this.state.modules.length} documented Python modules</span>
        </div>
        <div class="explorer-table">
          <table class="console-table">
            <thead>
              <tr>
                <th>File · lines · size</th>
                <th class="identity">Module</th>
                <th class="prose">Description</th>
                <th class="prose">Explanation</th>
                <th class="numeric">Definitions</th>
                <th class="numeric">Apps</th>
                <th>Used by</th>
                <th>Dependencies</th>
              </tr>
            </thead>
            <tbody>{this.state.tree && this.treeRows(this.state.tree, modules)}</tbody>
          </table>
        </div>
      </section>
    );
  }
  private appLineGraphs(): ComponentChildren {
    const series = this.state.repositoryHistory?.app_lines ?? [];
    return (
      <section class="app-lines" aria-label="App line counts over time">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Maintained lines by app</p>
            <h2>Absolute line counts over time</h2>
          </div>
          <p>Oldest visible commit → HEAD</p>
        </div>
        <div class="line-graphs">
          {series.map((item) => {
            const values = item.points.map((point) => point.lines);
            const low = Math.min(...values),
              high = Math.max(...values);
            const range = Math.max(1, high - low),
              denominator = Math.max(1, item.points.length - 1);
            const coordinates = item.points
              .map((point, index) => `${(index / denominator) * 320},${82 - ((point.lines - low) / range) * 72}`)
              .join(" ");
            const first = item.points[0],
              last = item.points.at(-1);
            return (
              <article class="line-graph">
                <header>
                  <strong>{item.name}</strong>
                  <span>{number.format(last?.lines ?? 0)} lines</span>
                </header>
                <svg
                  viewBox="0 0 320 90"
                  role="img"
                  aria-label={`${item.name} line count from ${number.format(
                    first?.lines ?? 0,
                  )} to ${number.format(last?.lines ?? 0)}`}
                >
                  <line x1="0" y1="82" x2="320" y2="82" />
                  <polyline points={coordinates} />
                </svg>
                <footer>
                  <span>{first ? new Date(first.committed_at).toLocaleDateString() : "—"}</span>
                  <span>
                    {number.format(low)}–{number.format(high)}
                  </span>
                  <span>{last ? new Date(last.committed_at).toLocaleDateString() : "—"}</span>
                </footer>
              </article>
            );
          })}
        </div>
      </section>
    );
  }
  private historyPage(): ComponentChildren {
    const history = this.state.repositoryHistory;
    const changes = (items: { name: string; added: number; deleted: number }[]) =>
      items.length
        ? items.map((item) => `${item.name} +${number.format(item.added)} −${number.format(item.deleted)}`).join(" · ")
        : "—";
    return (
      <section class="page">
        <div class="page-heading">
          <div>
            <p class="eyebrow">Automatic Git timeline</p>
            <h1>Repository trajectory</h1>
          </div>
          <p>
            {history?.commits.length ?? 0} commits loaded
            {history?.truncated ? ` · newest ${history.limit}` : ""}
          </p>
        </div>
        {history?.available && history.app_lines.length ? this.appLineGraphs() : null}
        {history?.available && history.commits.length ? (
          <div class="history">
            <table class="console-table">
              <thead>
                <tr>
                  <th class="compact">Committed</th>
                  <th class="compact">Revision</th>
                  <th>Change</th>
                  <th class="numeric">Lines</th>
                  <th>Apps</th>
                  <th>Languages</th>
                </tr>
              </thead>
              <tbody>
                {history.commits.map((item) => (
                  <tr>
                    <td>{new Date(item.committed_at).toLocaleString()}</td>
                    <td>{item.revision}</td>
                    <td class="subject">{item.subject}</td>
                    <td class="numeric change-lines">
                      <span>+{number.format(item.additions)}</span>
                      <b>−{number.format(item.deletions)}</b>
                    </td>
                    <td>{changes(item.apps)}</td>
                    <td>{changes(item.languages)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div class="empty">
            <h2>Git history unavailable</h2>
            <p>The current repository can still be inspected; initialize or fetch Git history to see its trajectory.</p>
          </div>
        )}
        <p class="history-note">
          Derived from maintained text-file numstats. Binary and excluded generated/runtime paths are not represented as
          line changes. {this.state.snapshots.length} optional metric baselines recorded.
        </p>
      </section>
    );
  }
  override render(): ComponentChildren {
    const pages: Page[] = ["overview", "explorer", "history"];
    const header = (
      <UtilityRail>
        <span class="brand">XENO // COCKPIT</span>
        <nav>
          {pages.map((page) => (
            <CommandButton aria-label={page} pressed={this.state.page === page} onClick={() => this.setState({ page })}>
              {page}
            </CommandButton>
          ))}
        </nav>
        <span class="push" />
        <CommandButton aria-label="RESCAN" disabled={this.state.busy} onClick={() => void this.load()}>
          RESCAN
        </CommandButton>
        <CommandButton aria-label="RECORD SNAPSHOT" disabled={this.state.busy} onClick={() => void this.capture()}>
          RECORD SNAPSHOT
        </CommandButton>
      </UtilityRail>
    );
    const footer = (
      <StatusRail>
        <span class={this.state.failed ? "error" : "ok"}>{this.state.failed ? "FAULT" : "READY"}</span>
        <span>{this.state.message}</span>
        <span class="push">{this.state.overview?.fingerprint.slice(0, 10) ?? "----------"}</span>
      </StatusRail>
    );
    const content =
      this.state.page === "overview"
        ? this.overviewPage()
        : this.state.page === "explorer"
          ? this.explorerPage()
          : this.historyPage();
    return (
      <ConsoleShell header={header} footer={footer}>
        <div class="cockpit-main">{content}</div>
      </ConsoleShell>
    );
  }
}

export function mount(root: HTMLElement): void {
  render(<XenorepoCockpit />, root);
}
