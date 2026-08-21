import { LitElement, css, html } from "lit";
import "@xenorepo/lit-ui";

type Phase = "loading" | "ready" | "running" | "failed";
type WorkerReply =
  | { type: "progress"; value: string }
  | { type: "ready"; version: string }
  | { type: "stream"; channel: "stdout" | "stderr"; text: string }
  | { type: "result"; value: string }
  | { type: "error"; value: string };

const PYODIDE_VERSION = "0.28.2";
const PYODIDE_ROOT = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

const workerSource = `
const root = ${JSON.stringify(PYODIDE_ROOT)};
let runtime;
const send = (type, payload = {}) => postMessage({ type, ...payload });
async function boot() {
  try {
    send("progress", { value: "Downloading CPython engine…" });
    importScripts(root + "pyodide.js");
    send("progress", { value: "Initializing browser sandbox…" });
    runtime = await loadPyodide({
      indexURL: root,
      stdout: text => send("stream", { channel: "stdout", text }),
      stderr: text => send("stream", { channel: "stderr", text }),
    });
    send("ready", { version: runtime.runPython("import sys; sys.version.split()[0]") });
  } catch (error) {
    send("error", { value: "Runtime failed to load: " + String(error) });
  }
}
onmessage = async event => {
  if (!runtime || event.data.type !== "execute") return;
  try {
    const result = await runtime.runPythonAsync(event.data.source);
    let value = "";
    if (result !== undefined && result !== null) value = String(result);
    if (result && typeof result.destroy === "function") result.destroy();
    send("result", { value });
  } catch (error) {
    send("error", { value: String(error) });
  }
};
setTimeout(boot, 0);
`;

class PythonTerminal extends LitElement {
  static properties = {
    phase: { state: true }, transcript: { state: true }, source: { state: true },
    runtimeVersion: { state: true }, sequence: { state: true },
  };
  phase: Phase = "loading";
  transcript = "PY/WEB BOOTING · fetching isolated Python runtime…\n";
  source = "";
  runtimeVersion = "—";
  sequence = 0;
  private worker?: Worker;
  private history: string[] = [];
  private historyIndex = 0;

  static styles = css`
    :host { display: block; height: 100%; --console-font: 13px/1.45 "Courier New", monospace; }
    x-console-shell { height: 100%; }
    x-console-shell::part(main) { min-height: 0; }
    .brand { color: #fabd2f; font-weight: bold; letter-spacing: .08em; }
    .push { margin-left: auto; }
    .workspace { display: grid; min-width: 0; min-height: 0; grid-template-rows: minmax(0, 1fr) auto; background: #181a1b; }
    pre { min-height: 0; margin: 0; padding: 14px 16px; overflow: auto; color: #ebdbb2; white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 4; }
    .entry { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 8px; padding: 9px 12px 11px; border-top: 1px solid #504945; background: #202221; }
    .prompt { padding-top: 5px; color: #b8bb26; font-weight: bold; }
    textarea { width: 100%; min-height: 32px; max-height: 28vh; resize: vertical; padding: 5px 7px; color: #ebdbb2; font: inherit; background: #111313; border: 1px solid #504945; outline: none; }
    textarea:focus { border-color: #fabd2f; box-shadow: 0 0 0 1px #fabd2f; }
    textarea:disabled { color: #928374; cursor: wait; }
    .error { color: #fb4934; }
    .hint { color: #a89984; }
    @media (max-width: 620px) { .optional { display: none; } pre { padding: 10px; } }
  `;

  connectedCallback() {
    super.connectedCallback();
    const blob = new Blob([workerSource], { type: "text/javascript" });
    this.worker = new Worker(URL.createObjectURL(blob));
    this.worker.onmessage = (event: MessageEvent<WorkerReply>) => this.receive(event.data);
    this.worker.onerror = (event: ErrorEvent) => {
      this.phase = "failed";
      this.append(`Worker failed: ${event.message || "unknown browser error"}\n`, true);
    };
  }

  disconnectedCallback() { this.worker?.terminate(); super.disconnectedCallback(); }

  private receive(message: WorkerReply) {
    if (message.type === "ready") {
      this.phase = "ready"; this.runtimeVersion = message.version;
      this.append(`Python ${message.version} ready. Type an expression or statement.\n\n`);
      this.updateComplete.then(() => this.input()?.focus());
      return;
    }
    if (message.type === "progress") { this.append(message.value + "\n"); return; }
    if (message.type === "stream") { this.append(message.text + "\n"); return; }
    if (message.type === "result") {
      if (message.value) this.append(message.value + "\n");
      this.finish(); return;
    }
    this.append(message.value.replace(/^PythonError: /, "") + "\n", true);
    this.phase = message.value.startsWith("Runtime failed") ? "failed" : "ready";
    if (this.phase === "ready") this.finish();
  }

  private append(text: string, error = false) {
    this.transcript += error ? `[error] ${text}` : text;
    this.updateComplete.then(() => { const output = this.renderRoot.querySelector("pre"); if (output) output.scrollTop = output.scrollHeight; });
  }

  private finish() { this.phase = "ready"; this.updateComplete.then(() => this.input()?.focus()); }
  private input() { return this.renderRoot.querySelector<HTMLTextAreaElement>("textarea"); }

  private execute() {
    const command = this.source.trimEnd();
    if (!command || this.phase !== "ready") return;
    this.sequence += 1; this.history.push(command); this.historyIndex = this.history.length;
    this.append(`${this.sequence.toString().padStart(3, "0")} >>> ${command.replaceAll("\n", "\n        ")}\n`);
    this.source = ""; this.phase = "running";
    this.worker?.postMessage({ type: "execute", source: command });
  }

  private keydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); this.execute(); return; }
    if ((event.key === "ArrowUp" || event.key === "ArrowDown") && !this.source.includes("\n")) {
      event.preventDefault();
      this.historyIndex = Math.max(0, Math.min(this.history.length, this.historyIndex + (event.key === "ArrowUp" ? -1 : 1)));
      this.source = this.history[this.historyIndex] ?? "";
    }
  }

  private clear() { this.transcript = `Python ${this.runtimeVersion} · transcript cleared\n\n`; this.sequence = 0; }

  render() {
    const status = { loading: "LOADING RUNTIME", ready: "READY", running: "EXECUTING", failed: "LOAD FAILED" }[this.phase];
    return html`<x-console-shell @keydown=${(event: KeyboardEvent) => { if (event.ctrlKey && event.key.toLowerCase() === "l") { event.preventDefault(); this.clear(); } }}>
      <x-utility-rail slot="header"><span class="brand">PY/WEB</span><span class="optional">BROWSER PYTHON TERMINAL</span><x-command-button class="push" @click=${this.clear}>CLEAR</x-command-button></x-utility-rail>
      <x-console-pane title="INTERACTIVE SESSION" index="01" tone="green"><section class="workspace">
        <pre aria-live="polite" aria-label="Terminal output">${this.transcript}</pre>
        <label class="entry"><span class="prompt">${this.phase === "ready" ? ">>>" : "···"}</span><textarea aria-label="Python command" spellcheck="false" .value=${this.source} ?disabled=${this.phase !== "ready"} @input=${(event: InputEvent) => this.source = (event.target as HTMLTextAreaElement).value} @keydown=${this.keydown}></textarea></label>
      </section></x-console-pane>
      <x-status-rail slot="footer"><x-status-indicator .label=${status} tone=${this.phase === "failed" ? "orange" : this.phase === "ready" ? "green" : "blue"}></x-status-indicator><span class="hint optional">ENTER EXECUTE · SHIFT+ENTER NEWLINE · ↑↓ HISTORY · CTRL+L CLEAR</span><span class="push">PY ${this.runtimeVersion} · LOCAL WORKER</span></x-status-rail>
    </x-console-shell>`;
  }
}
customElements.define("python-terminal", PythonTerminal);

export function mount(root: HTMLElement) { root.replaceChildren(document.createElement("python-terminal")); }
