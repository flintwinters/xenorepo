import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import xtermCss from "@xterm/xterm/css/xterm.css";
import { LitElement, css, html, nothing, unsafeCSS } from "lit";
import "@xenorepo/lit-ui";

type Phase = "connecting" | "ready" | "closed" | "failed";
interface WindowState {
  id: number; title: string; x: number; y: number; width: number; height: number;
  z: number; minimized: boolean; maximized: boolean; phase: Phase;
}
interface TerminalSession { socket: WebSocket; terminal: Terminal; fit: FitAddon; resize?: ResizeObserver; }

class WorminalDesktop extends LitElement {
  static properties = { windows: { state: true }, clock: { state: true } };
  declare windows: WindowState[];
  declare clock: string;
  private sessions = new Map<number, TerminalSession>();
  private nextId = 1;
  private topZ = 1;
  private clockTimer?: number;

  constructor() { super(); this.windows = []; this.clock = "--:--:--"; }

  static styles = [unsafeCSS(xtermCss), css`
    :host { display: block; height: 100%; color: #ebdbb2; font: 11px/1.15 "Courier New", monospace; background: #1d2021; }
    * { box-sizing: border-box; } x-console-shell { height: 100%; }
    .brand { color: #fabd2f; font-weight: bold; letter-spacing: .1em; } .push { margin-left: auto; }
    .desktop { position: relative; min-width: 0; min-height: 0; overflow: hidden; background-color: #1a1d1c; background-image: linear-gradient(#282b2a 1px,transparent 1px),linear-gradient(90deg,#282b2a 1px,transparent 1px); background-size: 24px 24px; }
    .welcome { position: absolute; inset: 0; display: grid; place-content: center; gap: 10px; text-align: center; color: #a89984; pointer-events: none; }
    .welcome strong { color: #ebdbb2; font-size: 18px; }
    .window { position: absolute; display: grid; grid-template-rows: 28px minmax(0,1fr); min-width: 300px; min-height: 190px; overflow: hidden; background: #181a1b; border: 1px solid #111; box-shadow: 5px 7px 18px #0009; resize: both; }
    .window.active { border-color: #83a598; box-shadow: 5px 7px 22px #000c,0 0 0 1px #83a598; }
    .window.maximized { inset: 0 !important; width: 100% !important; height: 100% !important; resize: none; }
    .titlebar { display: flex; align-items: center; gap: 7px; min-width: 0; padding-left: 7px; color: #1d2021; font-weight: bold; background: linear-gradient(#83a598,#5f7f75); border-top: 1px solid #b7cfca; border-bottom: 2px solid #354a44; cursor: move; user-select: none; touch-action: none; }
    .window:not(.active) .titlebar { filter: saturate(.35) brightness(.72); }
    .phase { color: #282828; font-weight: normal; } .controls { display: flex; align-self: stretch; margin-left: auto; }
    .titlebar button { width: 30px; padding: 0; color: #ebdbb2; font: inherit; background: #282828; border: 0; border-left: 1px solid #111; cursor: pointer; }
    .titlebar button:hover { background: #3c3836; }
    .terminal-host { min-width: 0; min-height: 0; padding: 5px; overflow: hidden; background: #181a1b; }
    .terminal-host .xterm { height: 100%; } .terminal-host .xterm-viewport { scrollbar-color: #665c54 #181a1b; }
    .taskbar { display: flex; align-items: center; gap: 4px; min-width: 0; overflow-x: auto; }
    .task { min-width: 95px; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .task.active { color: #fabd2f; }
    @media (max-width:620px) { .optional { display:none; } .window { min-width:260px; } }
  `];

  connectedCallback() {
    super.connectedCallback();
    this.renderRoot.addEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    this.clockTimer = window.setInterval(() => this.clock = new Date().toLocaleTimeString([], { hour12: false }), 1000);
    this.spawn();
  }
  disconnectedCallback() { this.renderRoot.removeEventListener("contextmenu", this.blockShiftContextMenu, { capture: true }); for (const id of this.sessions.keys()) this.destroySession(id); clearInterval(this.clockTimer); super.disconnectedCallback(); }

  private blockShiftContextMenu(event: Event) {
    if (!(event as MouseEvent).shiftKey) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  private updateWindow(id: number, change: (window: WindowState) => WindowState) {
    this.windows = this.windows.map(window => window.id === id ? change(window) : window);
  }

  private spawn() {
    const id = this.nextId++; const offset = (id - 1) % 7;
    this.windows = [...this.windows, { id, title: `shell-${id}`, x: 32 + offset * 28, y: 30 + offset * 24, width: 650, height: 410, z: ++this.topZ, minimized: false, maximized: false, phase: "connecting" }];
    this.updateComplete.then(() => this.connect(id));
  }

  private connect(id: number) {
    const host = this.renderRoot.querySelector<HTMLElement>(`[data-terminal="${id}"]`);
    if (!host || this.sessions.has(id)) return;
    const terminal = new Terminal({ cursorBlink: true, convertEol: false, fontFamily: '"Courier New", monospace', fontSize: 11, lineHeight: 1, letterSpacing: 0, scrollback: 5000, theme: { background: "#181a1b", foreground: "#ebdbb2", cursor: "#fabd2f", selectionBackground: "#504945" } });
    const fit = new FitAddon(); terminal.loadAddon(fit); terminal.open(host); fit.fit();
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${location.host}/ws/terminal`);
    socket.binaryType = "arraybuffer";
    const session: TerminalSession = { socket, terminal, fit }; this.sessions.set(id, session);
    terminal.writeln("\x1b[33mWorminal\x1b[0m · opening localhost shell…");
    socket.onopen = () => { this.updateWindow(id, window => ({ ...window, phase: "ready" })); this.sendResize(id); terminal.focus(); };
    socket.onmessage = event => terminal.write(event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data);
    socket.onerror = () => { terminal.writeln("\r\n\x1b[31mShell connection failed.\x1b[0m"); this.updateWindow(id, window => ({ ...window, phase: "failed" })); };
    socket.onclose = () => { if (this.windows.some(window => window.id === id)) this.updateWindow(id, window => ({ ...window, phase: window.phase === "failed" ? "failed" : "closed" })); };
    terminal.onData(data => { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "input", data })); });
    session.resize = new ResizeObserver(() => { fit.fit(); this.sendResize(id); }); session.resize.observe(host);
  }

  private sendResize(id: number) {
    const session = this.sessions.get(id); if (!session || session.socket.readyState !== WebSocket.OPEN) return;
    session.socket.send(JSON.stringify({ type: "resize", columns: session.terminal.cols, rows: session.terminal.rows }));
  }

  private destroySession(id: number) {
    const session = this.sessions.get(id); if (!session) return;
    session.resize?.disconnect(); session.socket.close(); session.terminal.dispose(); this.sessions.delete(id);
  }
  private close(id: number) { this.destroySession(id); this.windows = this.windows.filter(window => window.id !== id); }
  private focus(id: number) { this.updateWindow(id, window => ({ ...window, z: ++this.topZ, minimized: false })); this.updateComplete.then(() => this.sessions.get(id)?.terminal.focus()); }
  private toggleMaximize(id: number) { this.updateWindow(id, window => ({ ...window, maximized: !window.maximized, minimized: false, z: ++this.topZ })); this.updateComplete.then(() => { this.sessions.get(id)?.fit.fit(); this.sendResize(id); }); }
  private toggleMinimize(id: number) { this.updateWindow(id, window => ({ ...window, minimized: !window.minimized })); }

  private moveWindow(event: PointerEvent, id: number) {
    const item = this.windows.find(window => window.id === id); if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.focus(id); const startX = event.clientX; const startY = event.clientY; const originX = item.x; const originY = item.y;
    const move = (next: PointerEvent) => this.updateWindow(id, window => ({ ...window, x: originX + next.clientX - startX, y: originY + next.clientY - startY, width: bounds?.width ?? window.width, height: bounds?.height ?? window.height }));
    const stop = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", stop); };
    addEventListener("pointermove", move); addEventListener("pointerup", stop, { once: true });
  }

  private resizeWindow(event: PointerEvent, id: number) {
    const item = this.windows.find(window => window.id === id); if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.focus(id); const startX = event.clientX; const startY = event.clientY; const width = bounds?.width ?? item.width; const height = bounds?.height ?? item.height;
    const move = (next: PointerEvent) => this.updateWindow(id, window => ({ ...window, width: Math.max(300, width + next.clientX - startX), height: Math.max(190, height + next.clientY - startY) }));
    const stop = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", stop); };
    addEventListener("pointermove", move); addEventListener("pointerup", stop, { once: true });
  }

  private windowPointerDown(event: PointerEvent, id: number) {
    this.focus(id);
    if ((event.target as Element).closest("button") || !event.shiftKey || ![0, 2].includes(event.button)) return;
    event.preventDefault(); event.stopPropagation();
    if (event.button === 0) this.moveWindow(event, id); else this.resizeWindow(event, id);
  }

  private titlePointerDown(event: PointerEvent, id: number) {
    if (event.shiftKey || event.button !== 0 || (event.target as Element).closest("button")) return;
    event.stopPropagation(); this.moveWindow(event, id);
  }

  private renderWindow(window: WindowState) {
    if (window.minimized) return nothing;
    const style = `left:${window.x}px;top:${window.y}px;width:${window.width}px;height:${window.height}px;z-index:${window.z}`;
    return html`<section data-window=${window.id} class="window ${window.z === this.topZ ? "active" : ""} ${window.maximized ? "maximized" : ""}" style=${style} @pointerdown=${(event: PointerEvent) => this.windowPointerDown(event, window.id)} aria-label=${window.title}>
      <header class="titlebar" @pointerdown=${(event: PointerEvent) => this.titlePointerDown(event, window.id)} @dblclick=${() => this.toggleMaximize(window.id)}><span>▣</span><span>${window.title}</span><span class="phase">${window.phase.toUpperCase()}</span><div class="controls"><button aria-label="Minimize ${window.title}" @click=${() => this.toggleMinimize(window.id)}>_</button><button aria-label="Maximize ${window.title}" @click=${() => this.toggleMaximize(window.id)}>□</button><button aria-label="Close ${window.title}" @click=${() => this.close(window.id)}>×</button></div></header>
      <div class="terminal-host" data-terminal=${window.id} aria-label=${`${window.title} terminal`}></div>
    </section>`;
  }

  render() {
    const ready = this.windows.filter(window => window.phase === "ready").length;
    return html`<x-console-shell><x-utility-rail slot="header"><span class="brand">WORMINAL</span><x-command-button @click=${this.spawn}>+ NEW SHELL</x-command-button><span class="push optional">LOCALHOST WORKSPACE · ${this.windows.length} WINDOW${this.windows.length === 1 ? "" : "S"}</span></x-utility-rail>
      <main class="desktop" aria-label="Worminal desktop">${this.windows.length ? nothing : html`<div class="welcome"><strong>NO OPEN SHELLS</strong><span>Use NEW SHELL to start a local terminal.</span></div>`}${this.windows.map(window => this.renderWindow(window))}</main>
      <x-status-rail slot="footer"><x-status-indicator .label=${`${ready} SHELL${ready === 1 ? "" : "S"} CONNECTED`} tone=${ready ? "green" : "orange"}></x-status-indicator><nav class="taskbar" aria-label="Open shells">${this.windows.map(window => html`<x-command-button class="task ${window.z === this.topZ && !window.minimized ? "active" : ""}" @click=${() => this.focus(window.id)}>${window.title}</x-command-button>`)}</nav><span class="push">LOCAL PTY · ${this.clock}</span></x-status-rail></x-console-shell>`;
  }
}
customElements.define("worminal-desktop", WorminalDesktop);

export function mount(root: HTMLElement) { root.replaceChildren(document.createElement("worminal-desktop")); }
