import { LitElement, css, html, nothing } from "lit";
import "@xenorepo/lit-ui";

type Phase = "loading" | "ready" | "running" | "failed";
interface TerminalWindow {
  id: number; title: string; x: number; y: number; width: number; height: number;
  z: number; minimized: boolean; maximized: boolean; phase: Phase;
  transcript: string; source: string; sequence: number; history: string[]; historyIndex: number;
}
type WorkerReply =
  | { type: "progress"; value: string }
  | { type: "ready"; version: string }
  | { type: "stream"; id: number; channel: "stdout" | "stderr"; text: string }
  | { type: "result"; id: number; value: string }
  | { type: "error"; id?: number; value: string };

const PYODIDE_VERSION = "0.28.2";
const PYODIDE_ROOT = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const STARTUP_TIMEOUT = 30_000;
const workerSource = `
import { loadPyodide } from ${JSON.stringify(PYODIDE_ROOT + "pyodide.mjs")};
const root = ${JSON.stringify(PYODIDE_ROOT)};
const sessions = new Map();
let activeId = 0;
const send = (type, payload = {}) => postMessage({ type, ...payload });
try {
  send("progress", { value: "Downloading CPython engine" });
  const runtime = await loadPyodide({
    indexURL: root,
    stdout: text => send("stream", { id: activeId, channel: "stdout", text }),
    stderr: text => send("stream", { id: activeId, channel: "stderr", text }),
  });
  const namespace = id => {
    if (!sessions.has(id)) sessions.set(id, runtime.toPy({ __name__: "__main__" }));
    return sessions.get(id);
  };
  onmessage = async event => {
    const { id, type, source } = event.data;
    if (type === "destroy") { sessions.get(id)?.destroy(); sessions.delete(id); return; }
    if (type !== "execute") return;
    activeId = id;
    try {
      const result = await runtime.runPythonAsync(source, { globals: namespace(id) });
      let value = "";
      if (result !== undefined && result !== null) value = String(result);
      if (result && typeof result.destroy === "function") result.destroy();
      send("result", { id, value });
    } catch (error) { send("error", { id, value: String(error) }); }
  };
  send("ready", { version: runtime.runPython("import sys; sys.version.split()[0]") });
} catch (error) { send("error", { value: "Runtime failed to load: " + String(error) }); }
`;

class WorminalDesktop extends LitElement {
  static properties = {
    windows: { state: true }, runtimePhase: { state: true }, runtimeVersion: { state: true },
    runtimeMessage: { state: true }, clock: { state: true },
  };
  declare windows: TerminalWindow[];
  declare runtimePhase: Phase;
  declare runtimeVersion: string;
  declare runtimeMessage: string;
  declare clock: string;
  private worker?: Worker;
  private workerUrl?: string;
  private nextId = 1;
  private topZ = 1;
  private startupTimer?: number;
  private clockTimer?: number;

  constructor() {
    super();
    this.windows = [];
    this.runtimePhase = "loading";
    this.runtimeVersion = "—";
    this.runtimeMessage = "STARTING PYTHON";
    this.clock = "--:--:--";
  }

  static styles = css`
    :host { display: block; height: 100%; color: #ebdbb2; font: 12px/1.35 "Courier New", monospace; background: #1d2021; }
    * { box-sizing: border-box; }
    x-console-shell { height: 100%; }
    .brand { color: #fabd2f; font-weight: bold; letter-spacing: .1em; }
    .push { margin-left: auto; }
    .desktop { position: relative; min-width: 0; min-height: 0; overflow: hidden; background-color: #1a1d1c; background-image: linear-gradient(#282b2a 1px, transparent 1px), linear-gradient(90deg, #282b2a 1px, transparent 1px); background-size: 24px 24px; }
    .welcome { position: absolute; inset: 0; display: grid; place-content: center; gap: 10px; text-align: center; color: #a89984; pointer-events: none; }
    .welcome strong { color: #ebdbb2; font-size: 18px; }
    .window { position: absolute; display: grid; grid-template-rows: 28px minmax(0, 1fr); min-width: 300px; min-height: 190px; overflow: hidden; background: #181a1b; border: 1px solid #111; box-shadow: 5px 7px 18px #0009; resize: both; }
    .window.active { border-color: #83a598; box-shadow: 5px 7px 22px #000c, 0 0 0 1px #83a598; }
    .window.maximized { inset: 0 !important; width: 100% !important; height: 100% !important; resize: none; }
    .titlebar { display: flex; align-items: center; gap: 7px; min-width: 0; padding-left: 7px; color: #1d2021; font-weight: bold; background: linear-gradient(#83a598, #5f7f75); border-top: 1px solid #b7cfca; border-bottom: 2px solid #354a44; cursor: move; user-select: none; touch-action: none; }
    .window:not(.active) .titlebar { filter: saturate(.35) brightness(.72); }
    .titlebar .controls { display: flex; align-self: stretch; margin-left: auto; }
    .titlebar button { width: 30px; padding: 0; color: #ebdbb2; font: inherit; background: #282828; border: 0; border-left: 1px solid #111; cursor: pointer; }
    .titlebar button:hover { background: #3c3836; }
    .terminal { display: grid; min-height: 0; grid-template-rows: minmax(0, 1fr) auto; }
    pre { min-height: 0; margin: 0; padding: 10px; overflow: auto; color: #ebdbb2; white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 4; }
    .entry { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 7px; padding: 7px 9px 9px; border-top: 1px solid #504945; background: #202221; }
    .prompt { padding-top: 4px; color: #b8bb26; font-weight: bold; }
    textarea { width: 100%; min-height: 29px; max-height: 120px; resize: vertical; padding: 4px 6px; color: #ebdbb2; font: inherit; background: #111313; border: 1px solid #504945; outline: 0; }
    textarea:focus { border-color: #fabd2f; box-shadow: 0 0 0 1px #fabd2f; }
    textarea:disabled { color: #928374; cursor: wait; }
    .taskbar { display: flex; align-items: center; gap: 4px; min-width: 0; overflow-x: auto; }
    .task { min-width: 95px; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .task.active { color: #fabd2f; }
    .failed { color: #fb4934; }
    @media (max-width: 620px) { .optional { display: none; } .window { min-width: 260px; } }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.clockTimer = window.setInterval(() => this.clock = new Date().toLocaleTimeString([], { hour12: false }), 1000);
    this.startRuntime();
    this.spawn();
  }
  disconnectedCallback() { this.stopRuntime(); clearInterval(this.clockTimer); super.disconnectedCallback(); }

  private stopRuntime() {
    this.worker?.terminate(); this.worker = undefined;
    if (this.workerUrl) URL.revokeObjectURL(this.workerUrl);
    clearTimeout(this.startupTimer);
  }

  private startRuntime() {
    this.stopRuntime(); this.runtimePhase = "loading"; this.runtimeMessage = "STARTING PYTHON";
    this.windows = this.windows.map(window => ({ ...window, phase: "loading" }));
    this.workerUrl = URL.createObjectURL(new Blob([workerSource], { type: "text/javascript" }));
    this.worker = new Worker(this.workerUrl, { type: "module", name: "worminal-python" });
    this.worker.onmessage = (event: MessageEvent<WorkerReply>) => this.receive(event.data);
    this.worker.onerror = event => this.failRuntime(event.message || "Python worker failed");
    this.startupTimer = window.setTimeout(() => this.failRuntime("Python startup timed out. Check network access, then retry."), STARTUP_TIMEOUT);
  }

  private failRuntime(message: string) {
    if (this.runtimePhase !== "loading") return;
    clearTimeout(this.startupTimer); this.worker?.terminate();
    this.runtimePhase = "failed"; this.runtimeMessage = message;
    this.windows = this.windows.map(window => ({ ...window, phase: "failed", transcript: window.transcript + `[error] ${message}\n` }));
  }

  private receive(message: WorkerReply) {
    if (message.type === "progress") { this.runtimeMessage = message.value; return; }
    if (message.type === "ready") {
      clearTimeout(this.startupTimer); this.runtimePhase = "ready"; this.runtimeVersion = message.version; this.runtimeMessage = "PYTHON READY";
      this.windows = this.windows.map(window => ({ ...window, phase: "ready", transcript: window.transcript + `Python ${message.version} ready.\n\n` }));
      return;
    }
    if (message.type === "error" && message.id === undefined) { this.failRuntime(message.value); return; }
    if (message.id === undefined) return;
    this.updateWindow(message.id, window => {
      if (message.type === "stream") return { ...window, transcript: window.transcript + message.text + "\n" };
      const value = message.type === "error" ? message.value.replace(/^PythonError: /, "") : message.value;
      return { ...window, phase: "ready", transcript: window.transcript + (value ? `${message.type === "error" ? "[error] " : ""}${value}\n` : "") };
    });
  }

  private spawn() {
    const id = this.nextId++; const offset = (id - 1) % 7;
    this.windows = [...this.windows, {
      id, title: `python-${id}`, x: 32 + offset * 28, y: 30 + offset * 24, width: 610, height: 390,
      z: ++this.topZ, minimized: false, maximized: false, phase: this.runtimePhase,
      transcript: `Worminal session ${id}\n`, source: "", sequence: 0, history: [], historyIndex: 0,
    }];
    this.updateComplete.then(() => this.input(id)?.focus());
  }

  private updateWindow(id: number, change: (window: TerminalWindow) => TerminalWindow) {
    this.windows = this.windows.map(window => window.id === id ? change(window) : window);
    this.updateComplete.then(() => { const output = this.renderRoot.querySelector<HTMLElement>(`[data-output="${id}"]`); if (output) output.scrollTop = output.scrollHeight; });
  }
  private focus(id: number) { this.updateWindow(id, window => ({ ...window, z: ++this.topZ, minimized: false })); }
  private input(id: number) { return this.renderRoot.querySelector<HTMLTextAreaElement>(`textarea[data-id="${id}"]`); }
  private close(id: number) { this.worker?.postMessage({ type: "destroy", id }); this.windows = this.windows.filter(window => window.id !== id); }
  private toggleMaximize(id: number) { this.updateWindow(id, window => ({ ...window, maximized: !window.maximized, minimized: false, z: ++this.topZ })); }
  private toggleMinimize(id: number) { this.updateWindow(id, window => ({ ...window, minimized: !window.minimized })); }

  private drag(event: PointerEvent, id: number) {
    if ((event.target as Element).closest("button")) return;
    const item = this.windows.find(window => window.id === id);
    if (!item || item.maximized) return;
    this.focus(id); const startX = event.clientX; const startY = event.clientY; const originX = item.x; const originY = item.y;
    const move = (next: PointerEvent) => this.updateWindow(id, window => ({ ...window, x: Math.max(0, originX + next.clientX - startX), y: Math.max(0, originY + next.clientY - startY) }));
    const stop = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", stop); };
    addEventListener("pointermove", move); addEventListener("pointerup", stop, { once: true });
  }

  private execute(id: number) {
    const terminal = this.windows.find(window => window.id === id);
    if (!terminal || terminal.phase !== "ready" || !terminal.source.trimEnd()) return;
    const command = terminal.source.trimEnd();
    this.updateWindow(id, window => ({ ...window, phase: "running", source: "", sequence: window.sequence + 1, history: [...window.history, command], historyIndex: window.history.length + 1, transcript: window.transcript + `${String(window.sequence + 1).padStart(3, "0")} >>> ${command.replaceAll("\n", "\n        ")}\n` }));
    this.worker?.postMessage({ type: "execute", id, source: command });
  }

  private keydown(event: KeyboardEvent, id: number) {
    const terminal = this.windows.find(window => window.id === id); if (!terminal) return;
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); this.execute(id); return; }
    if ((event.key === "ArrowUp" || event.key === "ArrowDown") && !terminal.source.includes("\n")) {
      event.preventDefault(); const index = Math.max(0, Math.min(terminal.history.length, terminal.historyIndex + (event.key === "ArrowUp" ? -1 : 1)));
      this.updateWindow(id, window => ({ ...window, historyIndex: index, source: window.history[index] ?? "" }));
    }
  }

  private renderWindow(window: TerminalWindow) {
    if (window.minimized) return nothing;
    const style = `left:${window.x}px;top:${window.y}px;width:${window.width}px;height:${window.height}px;z-index:${window.z}`;
    return html`<section class="window ${window.z === this.topZ ? "active" : ""} ${window.maximized ? "maximized" : ""}" style=${style} @pointerdown=${() => this.focus(window.id)} aria-label=${window.title}>
      <header class="titlebar" @pointerdown=${(event: PointerEvent) => this.drag(event, window.id)} @dblclick=${() => this.toggleMaximize(window.id)}><span>▣</span><span>${window.title}</span><div class="controls"><button aria-label="Minimize ${window.title}" @click=${() => this.toggleMinimize(window.id)}>_</button><button aria-label="Maximize ${window.title}" @click=${() => this.toggleMaximize(window.id)}>□</button><button aria-label="Close ${window.title}" @click=${() => this.close(window.id)}>×</button></div></header>
      <section class="terminal"><pre data-output=${window.id} aria-live="polite" aria-label=${`${window.title} output`}>${window.transcript}</pre><label class="entry"><span class="prompt">${window.phase === "ready" ? ">>>" : "···"}</span><textarea data-id=${window.id} aria-label=${`${window.title} command`} spellcheck="false" .value=${window.source} ?disabled=${window.phase !== "ready"} @input=${(event: InputEvent) => this.updateWindow(window.id, item => ({ ...item, source: (event.target as HTMLTextAreaElement).value }))} @keydown=${(event: KeyboardEvent) => this.keydown(event, window.id)}></textarea></label></section>
    </section>`;
  }

  render() {
    return html`<x-console-shell>
      <x-utility-rail slot="header"><span class="brand">WORMINAL</span><x-command-button @click=${this.spawn}>+ NEW TERMINAL</x-command-button>${this.runtimePhase === "failed" ? html`<x-command-button @click=${this.startRuntime}>RETRY PYTHON</x-command-button>` : nothing}<span class="push optional">BROWSER WORKSPACE · ${this.windows.length} WINDOW${this.windows.length === 1 ? "" : "S"}</span></x-utility-rail>
      <main class="desktop" aria-label="Worminal desktop">${this.windows.length ? nothing : html`<div class="welcome"><strong>NO OPEN TERMINALS</strong><span>Use NEW TERMINAL to create a session.</span></div>`}${this.windows.map(window => this.renderWindow(window))}</main>
      <x-status-rail slot="footer"><x-status-indicator .label=${this.runtimeMessage} tone=${this.runtimePhase === "failed" ? "orange" : this.runtimePhase === "ready" ? "green" : "blue"}></x-status-indicator><nav class="taskbar" aria-label="Open terminals">${this.windows.map(window => html`<x-command-button class="task ${window.z === this.topZ && !window.minimized ? "active" : ""}" @click=${() => this.focus(window.id)}>${window.title}</x-command-button>`)}</nav><span class="push">PY ${this.runtimeVersion} · ${this.clock}</span></x-status-rail>
    </x-console-shell>`;
  }
}
customElements.define("worminal-desktop", WorminalDesktop);

export function mount(root: HTMLElement) { root.replaceChildren(document.createElement("worminal-desktop")); }
