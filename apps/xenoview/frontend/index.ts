/** Evidence-first command-and-control views for Xenorepo. */
import { LitElement, html, nothing } from "lit";
import { cockpitStyles } from "./styles.js";

type Page = "overview" | "modules" | "explorer" | "architecture" | "history";
interface Metrics { [key: string]: number }
interface Overview {
  metrics: Metrics; delta: Metrics; revision: string; dirty: boolean; fingerprint: string;
  specification: { covered: number; total: number }; exclusions: string[];
  largest_files: Array<{ path: string; lines: number; bytes: number }>;
}
interface ModuleFact {
  name: string; path: string; lines: number; bytes: number; public_definitions: number;
  inbound_apps: number; dependencies: string[];
}
interface TreeNode {
  name: string; path: string; kind: "file" | "directory"; bytes: number; lines: number;
  children?: TreeNode[];
}
interface Architecture {
  nodes: Array<{ id: string; label: string; kind: string }>;
  edges: Array<{ source: string; target: string; label: string }>;
}
interface Snapshot {
  id: number; captured_at: string; revision: string; dirty: boolean; fingerprint: string; metrics: Metrics;
}

const number = new Intl.NumberFormat("en-US");
const bytes = (value: number) => value < 1024 ? `${value} B` : value < 1024 ** 2
  ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 ** 2).toFixed(1)} MB`;
const label = (key: string) => key.replaceAll("_", " ");

class XenorepoCockpit extends LitElement {
  static properties = {
    page: { state: true }, overview: { state: true }, modules: { state: true },
    tree: { state: true }, architecture: { state: true }, history: { state: true },
    message: { state: true }, failed: { state: true }, busy: { state: true },
  };
  declare page: Page;
  declare overview: Overview | null;
  declare modules: ModuleFact[];
  declare tree: TreeNode | null;
  declare architecture: Architecture | null;
  declare history: Snapshot[];
  declare message: string;
  declare failed: boolean;
  declare busy: boolean;

  constructor() {
    super();
    this.page = "overview";
    this.overview = null;
    this.modules = [];
    this.tree = null;
    this.architecture = null;
    this.history = [];
    this.message = "Scanning repository…";
    this.failed = false;
    this.busy = false;
  }

  static styles = cockpitStyles;

  connectedCallback(): void {
    super.connectedCallback();
    void this.load();
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(path, options);
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.json() as Promise<T>;
  }

  private async perform(action: () => Promise<void>): Promise<void> {
    this.busy = true;
    try {
      await action();
      this.failed = false;
    } catch (error) {
      this.failed = true;
      this.message = error instanceof Error ? error.message : "Unexpected error";
    } finally {
      this.busy = false;
    }
  }

  private async load(): Promise<void> {
    await this.perform(async () => {
      [this.overview, this.modules, this.tree, this.architecture, this.history] = await Promise.all([
        this.request<Overview>("/api/overview"), this.request<ModuleFact[]>("/api/modules"),
        this.request<TreeNode>("/api/tree"), this.request<Architecture>("/api/architecture"),
        this.request<Snapshot[]>("/api/history"),
      ]);
      const state = this.overview.dirty ? " · working tree modified" : " · clean";
      this.message = `Scan complete · ${this.overview.revision}${state}`;
    });
  }

  private async capture(): Promise<void> {
    await this.perform(async () => {
      const result = await this.request<{ created: boolean }>("/api/snapshots", { method: "POST" });
      this.history = await this.request<Snapshot[]>("/api/history");
      if (this.overview) this.overview.delta = Object.fromEntries(
        Object.keys(this.overview.metrics).map((key) => [key, 0]),
      );
      this.message = result.created ? "Snapshot recorded" : "Current repository state was already recorded";
      this.page = "history";
    });
  }

  private metric(key: string, value: number) {
    const delta = this.overview?.delta[key] ?? 0;
    const formatted = key.includes("bytes") ? bytes(value) : number.format(value);
    return html`<article class="metric">
      <span>${label(key)}</span><strong>${formatted}</strong>
      <small class=${delta > 0 ? "up" : delta < 0 ? "down" : ""}>
        ${delta ? `${delta > 0 ? "+" : ""}${number.format(delta)} since snapshot` : "no saved change"}
      </small>
    </article>`;
  }

  private overviewPage() {
    if (!this.overview) return html`<p class="empty">Scanning repository…</p>`;
    const primary = ["source_files", "source_lines", "repository_bytes", "monoapps",
      "monotools_modules", "test_cases", "specified_apps", "architecture_violations",
      "large_files", "complex_functions", "shared_import_edges", "median_file_lines"];
    return html`<section class="page overview">
      <div class="page-heading"><div><p class="eyebrow">Repository scorecard</p>
        <h1>Broad strokes, concrete units.</h1></div>
        <p>${this.overview.specification.covered}/${this.overview.specification.total} active apps specified</p></div>
      <div class="metrics">${primary.map((key) => this.metric(key, this.overview!.metrics[key]))}</div>
      <div class="split">
        <x-console-pane title="Largest maintained files" tone="orange">
          <table><thead><tr><th>Path</th><th>Lines</th><th>Size</th></tr></thead><tbody>
          ${this.overview.largest_files.map((item) => html`<tr><td>${item.path}</td>
            <td>${number.format(item.lines)}</td><td>${bytes(item.bytes)}</td></tr>`)}</tbody></table>
        </x-console-pane>
        <x-console-pane title="Measurement boundary" tone="blue"><div class="note">
          <p>Counts include maintained source and project documentation.
            Audit numbers use the root structural audit.</p>
          <p><b>Excluded:</b> ${this.overview.exclusions.join(", ")}</p>
          <p>No composite quality score is calculated: unrelated evidence stays independently inspectable.</p>
        </div></x-console-pane>
      </div>
    </section>`;
  }

  private modulesPage() {
    return html`<section class="page"><div class="page-heading"><div><p class="eyebrow">Platform anatomy</p>
      <h1>Monotools modules</h1></div><p>${this.modules.length} top-level Python modules</p></div>
      <div class="module-grid">${this.modules.map((item) => html`<article class="module">
        <header><strong>${item.name}</strong><span>${item.lines} lines · ${bytes(item.bytes)}</span></header>
        <div><b>${item.public_definitions}</b> public definitions <b>${item.inbound_apps}</b> declaring apps</div>
        <p>${item.dependencies.length ? `uses ${item.dependencies.join(", ")}` : "no direct Monotools dependencies"}</p>
      </article>`)}</div></section>`;
  }

  private treeNode(node: TreeNode, depth = 0): unknown {
    if (node.kind === "file") return html`<div class="tree-row file" style=${`--depth:${depth}`}>
      <span>${node.name}</span><small>${number.format(node.lines)} lines</small>
      <small>${bytes(node.bytes)}</small></div>`;
    return html`<details ?open=${depth < 2}><summary class="tree-row" style=${`--depth:${depth}`}>
      <span>${node.name}</span><small>${number.format(node.lines)} lines</small>
      <small>${bytes(node.bytes)}</small></summary>
      ${node.children?.map((child) => this.treeNode(child, depth + 1))}</details>`;
  }

  private explorerPage() {
    return html`<section class="page"><div class="page-heading"><div><p class="eyebrow">Maintained footprint</p>
      <h1>Repository explorer</h1></div><p>Generated and runtime-heavy paths excluded</p></div>
      <div class="tree">${this.tree ? this.treeNode(this.tree) : nothing}</div></section>`;
  }

  private architecturePage() {
    if (!this.architecture) return nothing;
    const groups = ["repository", "platform", "runtime", "app", "storage"];
    const names = new Map(this.architecture.nodes.map((item) => [item.id, item.label]));
    return html`<section class="page"><div class="page-heading"><div><p class="eyebrow">Declared relationships</p>
      <h1>High-level architecture</h1></div><p>Derived from app metadata and capabilities</p></div>
      <div class="diagram">${groups.map((kind) => html`<div class="layer"><h2>${kind}</h2><div>
        ${this.architecture!.nodes.filter((node) => node.kind === kind).map((node) => html`
          <article class=${`node ${kind}`}><strong>${node.label}</strong>
            <small>${node.id}</small></article>`)}</div></div>`)}</div>
      <x-console-pane title="Relationship ledger" tone="purple"><div class="edges">
        ${this.architecture.edges.map((edge) => html`<div><b>${names.get(edge.source)}</b>
          <span>→ ${edge.label} →</span><b>${names.get(edge.target)}</b></div>`)}</div>
      </x-console-pane></section>`;
  }

  private historyPage() {
    const keys = ["source_lines", "source_files", "repository_bytes", "test_cases",
      "architecture_violations", "large_files", "complex_functions"];
    return html`<section class="page"><div class="page-heading"><div><p class="eyebrow">Schema v1 timeline</p>
      <h1>Repository trajectory</h1></div><p>${this.history.length} explicit snapshots</p></div>
      ${this.history.length ? html`<div class="history"><table><thead><tr><th>Captured</th><th>Revision</th>
        ${keys.map((key) => html`<th>${label(key)}</th>`)}</tr></thead><tbody>
        ${[...this.history].reverse().map((item) => html`<tr>
          <td>${new Date(item.captured_at).toLocaleString()}</td>
          <td>${item.revision}${item.dirty ? "*" : ""}</td>${keys.map((key) => html`<td>
          ${key.includes("bytes") ? bytes(item.metrics[key]) : number.format(item.metrics[key])}</td>`)}
        </tr>`)}</tbody></table></div>` : html`<div class="empty"><h2>No snapshots yet</h2>
          <p>Record the current state to establish a baseline. Sampling is explicit so the timeline
            reflects meaningful checkpoints.</p></div>`}
    </section>`;
  }

  render() {
    const pages: Page[] = ["overview", "modules", "explorer", "architecture", "history"];
    return html`<x-console-shell><x-utility-rail slot="header"><span class="brand">XENO // COCKPIT</span>
      <nav>${pages.map((page) => html`<x-command-button label=${page} .pressed=${this.page === page}
        @click=${() => { this.page = page; }}></x-command-button>`)}</nav>
      <span class="push"></span><x-command-button label="RESCAN" ?disabled=${this.busy}
        @click=${() => void this.load()}></x-command-button>
      <x-command-button label="RECORD SNAPSHOT" ?disabled=${this.busy}
        @click=${() => void this.capture()}></x-command-button>
      </x-utility-rail>
      <main>${this.page === "overview" ? this.overviewPage() : this.page === "modules" ? this.modulesPage()
        : this.page === "explorer" ? this.explorerPage() : this.page === "architecture"
        ? this.architecturePage() : this.historyPage()}</main>
      <x-status-rail slot="footer"><span class=${this.failed ? "error" : "ok"}>
        ${this.failed ? "FAULT" : "READY"}</span><span>${this.message}</span>
        <span class="push">${this.overview?.fingerprint.slice(0, 10) ?? "----------"}</span></x-status-rail>
    </x-console-shell>`;
  }
}

customElements.define("x-xenorepo-cockpit", XenorepoCockpit);

export function mount(root: HTMLElement): void {
  root.append(document.createElement("x-xenorepo-cockpit"));
}
