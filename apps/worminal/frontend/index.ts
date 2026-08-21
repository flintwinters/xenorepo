import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import xtermCss from "@xterm/xterm/css/xterm.css";
import { LitElement, css, html, nothing, unsafeCSS } from "lit";
import "@xenorepo/lit-ui";

type Phase = "connecting" | "ready" | "closed" | "failed";
const TERMINAL_FONT_SIZE = 11;
const TERMINAL_ROW_HEIGHT = 9;
interface WindowState {
  id: string; title: string; x: number; y: number; width: number; height: number;
  z: number; minimized: boolean; maximized: boolean; phase: Phase;
}
interface Shortcut { action: "new-shell"; key: string; control: boolean; alt: boolean; shift: boolean; meta: boolean; }
interface TerminalSession { socket: WebSocket; terminal: Terminal; fit: FitAddon; resize?: ResizeObserver; }

class WorminalDesktop extends LitElement {
  static properties = { windows: { state: true }, clock: { state: true }, shortcuts: { state: true }, settingsOpen: { state: true }, passwordRequired: { state: true }, accessPassword: { state: true }, accessError: { state: true }, currentAccessPassword: { state: true }, newAccessPassword: { state: true }, confirmedAccessPassword: { state: true }, settingsError: { state: true }, settingsSaving: { state: true } };
  declare windows: WindowState[];
  declare clock: string;
  declare shortcuts: Shortcut[];
  declare settingsOpen: boolean;
  declare passwordRequired: boolean;
  declare accessPassword: string;
  declare accessError: string;
  declare currentAccessPassword: string;
  declare newAccessPassword: string;
  declare confirmedAccessPassword: string;
  declare settingsError: string;
  declare settingsSaving: boolean;
  private sessions = new Map<string, TerminalSession>();
  private nextTitle = 1;
  private topZ = 1;
  private clockTimer?: number;
  private workspaceTimer?: number;
  private editingWindow = false;
  private pendingSaves = 0;
  private persistence = Promise.resolve();
  private shortcutsBeforeSettings?: Shortcut[];
  private standaloneShortcutHeld?: string;

  constructor() { super(); this.windows = []; this.clock = "--:--:--"; this.shortcuts = [this.defaultShortcut()]; this.settingsOpen = false; this.passwordRequired = false; this.accessPassword = ""; this.accessError = ""; this.currentAccessPassword = ""; this.newAccessPassword = ""; this.confirmedAccessPassword = ""; this.settingsError = ""; this.settingsSaving = false; }

  static styles = [unsafeCSS(xtermCss), css`
    :host { display: block; height: 100%; color: #ebdbb2; font: 11px/1.15 "Courier New", monospace; background: #1d2021; }
    * { box-sizing: border-box; } x-console-shell { height: 100%; }
    .brand { color: #fabd2f; font-weight: bold; letter-spacing: .1em; } .push { margin-left: auto; }
    .desktop { position: relative; min-width: 0; min-height: 0; overflow: hidden; background-color: #1a1d1c; background-image: linear-gradient(#282b2a 1px,transparent 1px),linear-gradient(90deg,#282b2a 1px,transparent 1px); background-size: 24px 24px; }
    .welcome { position: absolute; inset: 0; display: grid; place-content: center; gap: 10px; text-align: center; color: #a89984; pointer-events: none; }
    .welcome strong { color: #ebdbb2; font-size: 18px; }
    .window { position: absolute; display: grid; grid-template-rows: 20px minmax(0,1fr); min-width: 300px; min-height: 190px; overflow: hidden; background: #181a1b; border: 1px solid #111; box-shadow: 5px 7px 18px #0009; resize: both; }
    .window.active { border-color: #83a598; box-shadow: 5px 7px 22px #000c,0 0 0 1px #83a598; }
    .window.maximized { inset: 0 !important; width: 100% !important; height: 100% !important; resize: none; }
    .titlebar { display: flex; align-items: center; gap: 5px; min-width: 0; padding-left: 5px; color: #1d2021; font-weight: bold; background: linear-gradient(#83a598,#5f7f75); border-top: 1px solid #b7cfca; border-bottom: 2px solid #354a44; cursor: move; user-select: none; touch-action: none; }
    .window:not(.active) .titlebar { filter: saturate(.35) brightness(.72); }
    .phase { color: #282828; font-weight: normal; } .controls { display: flex; align-self: stretch; margin-left: auto; }
    .titlebar button { width: 24px; padding: 0; color: #ebdbb2; font: inherit; background: #282828; border: 0; border-left: 1px solid #111; cursor: pointer; }
    .titlebar button:hover { background: #3c3836; }
    .terminal-host { min-width: 0; min-height: 0; padding: 5px; overflow: hidden; background: #181a1b; }
    .terminal-host .xterm { height: 100%; } .terminal-host .xterm-viewport { scrollbar-color: #665c54 #181a1b; }
    .terminal-host .xterm-rows > div { height: ${TERMINAL_ROW_HEIGHT}px !important; line-height: ${TERMINAL_ROW_HEIGHT}px !important; overflow: visible !important; }
    .taskbar { display: flex; align-items: center; gap: 4px; min-width: 0; overflow-x: auto; }
    .task { min-width: 95px; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .task.active { color: #fabd2f; }
    .settings { position: fixed; inset: 0; z-index: 200000; display: grid; place-items: center; padding: 18px; background: #000a; }
    .settings-panel { width: min(440px,100%); padding: 16px; color: #ebdbb2; background: #282828; border: 1px solid #83a598; box-shadow: 8px 10px 30px #000; }
    .settings-panel h2 { margin: 0 0 8px; color: #fabd2f; font-size: 15px; letter-spacing: .08em; }
    .settings-panel p { margin: 0 0 14px; color: #a89984; }
    .shortcut-row { display: grid; grid-template-columns: 1fr minmax(160px, 1fr); gap: 10px; align-items: center; padding: 10px 0; border-top: 1px solid #504945; }
    .shortcut-row input { width: 100%; padding: 7px; color: #ebdbb2; font: inherit; background: #1d2021; border: 1px solid #665c54; }
    .shortcut-row input:focus { outline: 1px solid #fabd2f; border-color: #fabd2f; }
    .password-settings { display: grid; gap: 8px; padding-top: 12px; border-top: 1px solid #504945; }
    .password-settings h3 { margin: 0 0 2px; color: #83a598; font-size: 12px; letter-spacing: .06em; }
    .password-settings label { display: grid; grid-template-columns: 1fr minmax(160px, 1fr); gap: 10px; align-items: center; }
    .password-settings input { width: 100%; padding: 7px; color: #ebdbb2; font: inherit; background: #1d2021; border: 1px solid #665c54; }
    .password-settings input:focus { outline: 1px solid #fabd2f; border-color: #fabd2f; }
    .settings-error { min-height: 15px; color: #fb4934; }
    .settings-actions { display: flex; justify-content: flex-end; gap: 7px; margin-top: 14px; }
    .access-panel { width: min(360px,100%); padding: 16px; color: #ebdbb2; background: #282828; border: 1px solid #fabd2f; box-shadow: 8px 10px 30px #000; }
    .access-panel h2 { margin: 0 0 8px; color: #fabd2f; font-size: 15px; letter-spacing: .08em; }
    .access-panel p { margin: 0 0 12px; color: #a89984; }.access-panel input { width: 100%; padding: 8px; color: #ebdbb2; font: inherit; background: #1d2021; border: 1px solid #665c54; }
    .access-error { min-height: 15px; margin-top: 8px; color: #fb4934; }
    @media (max-width:620px) { .optional { display:none; } .window { min-width:260px; } }
  `];

  connectedCallback() {
    super.connectedCallback();
    this.renderRoot.addEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.addEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.addEventListener("keydown", this.handleSuperKeyDown, { capture: true });
    window.addEventListener("keyup", this.handleSuperKeyUp, { capture: true });
    this.clockTimer = window.setInterval(() => this.clock = new Date().toLocaleTimeString([], { hour12: false }), 1000);
    this.workspaceTimer = window.setInterval(() => void this.syncWorkspace(), 750);
    void this.restoreWorkspace();
  }
  disconnectedCallback() { this.renderRoot.removeEventListener("contextmenu", this.blockShiftContextMenu, { capture: true }); window.removeEventListener("contextmenu", this.blockShiftContextMenu, { capture: true }); window.removeEventListener("keydown", this.handleSuperKeyDown, { capture: true }); window.removeEventListener("keyup", this.handleSuperKeyUp, { capture: true }); for (const id of this.sessions.keys()) this.destroySession(id); clearInterval(this.clockTimer); clearInterval(this.workspaceTimer); super.disconnectedCallback(); }

  private blockShiftContextMenu = (event: Event) => {
    const target = event.target as Node | null;
    if (!(event as MouseEvent).shiftKey || !(target && this.renderRoot.contains(target) || event.composedPath().includes(this))) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  };

  private handleSuperKeyDown = (event: KeyboardEvent) => {
    if (this.settingsOpen) {
      if (event.key === "Escape") this.closeSettings();
      return;
    }
    const shortcut = this.newShellShortcut();
    if (this.isStandaloneModifier(shortcut)) {
      if (event.key === shortcut.key && !event.repeat) this.standaloneShortcutHeld = shortcut.key;
      else this.standaloneShortcutHeld = undefined;
      return;
    }
    if (event.repeat || !this.matchesShortcut(event, shortcut)) return;
    event.preventDefault(); event.stopImmediatePropagation(); void this.spawn();
  };

  private handleSuperKeyUp = (event: KeyboardEvent) => {
    if (this.settingsOpen || event.key !== this.standaloneShortcutHeld) return;
    this.standaloneShortcutHeld = undefined; void this.spawn();
  };

  private defaultShortcut(): Shortcut { return { action: "new-shell", key: "Meta", control: false, alt: false, shift: false, meta: false }; }
  private newShellShortcut() { return this.shortcuts.find(shortcut => shortcut.action === "new-shell") || this.defaultShortcut(); }
  private matchesShortcut(event: KeyboardEvent, shortcut: Shortcut) {
    return event.key.toLowerCase() === shortcut.key.toLowerCase() && event.ctrlKey === shortcut.control
      && event.altKey === shortcut.alt && event.shiftKey === shortcut.shift && event.metaKey === shortcut.meta;
  }
  private isStandaloneModifier(shortcut: Shortcut) {
    return ["Control", "Alt", "Shift", "Meta"].includes(shortcut.key)
      && !shortcut.control && !shortcut.alt && !shortcut.shift && !shortcut.meta;
  }
  private shortcutLabel(shortcut: Shortcut) {
    return [...(shortcut.control ? ["Ctrl"] : []), ...(shortcut.alt ? ["Alt"] : []), ...(shortcut.shift ? ["Shift"] : []), ...(shortcut.meta ? ["Meta"] : []), shortcut.key].join(" + ");
  }
  private captureShortcut(event: KeyboardEvent) {
    event.preventDefault(); event.stopPropagation();
    const shortcut: Shortcut = { action: "new-shell", key: event.key, control: event.ctrlKey && event.key !== "Control", alt: event.altKey && event.key !== "Alt", shift: event.shiftKey && event.key !== "Shift", meta: event.metaKey && event.key !== "Meta" };
    this.shortcuts = [shortcut];
  }

  private updateWindow(id: string, change: (window: WindowState) => WindowState) {
    this.windows = this.windows.map(window => window.id === id ? change(window) : window);
  }

  private async restoreWorkspace() {
    let response = await fetch("/api/workspace");
    if (response.status === 401) {
      this.passwordRequired = true;
      return;
    }
    if (!response.ok) return;
    const state = await response.json() as { windows: Omit<WindowState, "phase">[]; shortcuts?: Shortcut[] };
    this.windows = state.windows.map(window => ({ ...window, phase: "connecting" }));
    this.shortcuts = state.shortcuts?.length ? state.shortcuts : [this.defaultShortcut()];
    this.topZ = Math.max(1, ...this.windows.map(window => window.z));
    this.nextTitle = Math.max(1, ...this.windows.map(window => Number(window.title.match(/^shell-(\d+)$/)?.[1] || 0) + 1));
    if (!this.windows.length) { this.spawn(); return; }
    await this.updateComplete;
    for (const window of this.windows) if (!window.minimized) this.connect(window.id);
  }

  private async syncWorkspace() {
    if (this.passwordRequired || this.settingsOpen || this.editingWindow || this.pendingSaves) return;
    const response = await fetch("/api/workspace");
    if (!response.ok) return;
    const state = await response.json() as { windows: Omit<WindowState, "phase">[]; shortcuts?: Shortcut[] };
    const previous = new Map(this.windows.map(window => [window.id, window]));
    const declared = new Set(state.windows.map(window => window.id));
    for (const id of this.sessions.keys()) if (!declared.has(id)) this.destroySession(id);
    this.windows = state.windows.map(window => ({ ...window, phase: previous.get(window.id)?.phase || "connecting" }));
    this.shortcuts = state.shortcuts?.length ? state.shortcuts : [this.defaultShortcut()];
    this.topZ = Math.max(1, ...this.windows.map(window => window.z));
    this.nextTitle = Math.max(1, ...this.windows.map(window => Number(window.title.match(/^shell-(\d+)$/)?.[1] || 0) + 1));
    await this.updateComplete;
    for (const window of this.windows) window.minimized ? this.destroySession(window.id) : this.connect(window.id);
  }

  private async grantAccess(password: string) {
    const access = await fetch("/api/access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
    if (access.ok) return true;
    this.accessError = "The password was not accepted.";
    return false;
  }

  private submitAccess = async (event: Event) => {
    event.preventDefault();
    if (!await this.grantAccess(this.accessPassword)) return;
    this.accessPassword = ""; this.accessError = ""; this.passwordRequired = false;
    await this.restoreWorkspace();
  };

  private savedWindows() {
    return this.windows.map(({ phase, ...window }) => window);
  }

  private saveWorkspace() {
    const body = JSON.stringify({ windows: this.savedWindows(), shortcuts: this.shortcuts });
    this.pendingSaves++;
    this.persistence = this.persistence.then(async () => {
      const response = await fetch("/api/workspace", { method: "PUT", headers: { "Content-Type": "application/json" }, body });
      if (!response.ok) throw new Error("Could not save Worminal workspace.");
    }).catch(() => undefined).finally(() => this.pendingSaves--);
    return this.persistence;
  }

  private async spawn() {
    const id = crypto.randomUUID(); const number = this.nextTitle++; const offset = (number - 1) % 7;
    this.windows = [...this.windows, { id, title: `shell-${number}`, x: 32 + offset * 28, y: 30 + offset * 24, width: 650, height: 410, z: ++this.topZ, minimized: false, maximized: false, phase: "connecting" }];
    await this.saveWorkspace(); await this.updateComplete; this.connect(id);
  }

  private clearSettingsPassword() {
    this.currentAccessPassword = ""; this.newAccessPassword = ""; this.confirmedAccessPassword = ""; this.settingsError = "";
  }

  private openSettings() {
    this.shortcutsBeforeSettings = this.shortcuts.map(shortcut => ({ ...shortcut }));
    this.clearSettingsPassword(); this.settingsOpen = true;
  }

  private closeSettings() {
    if (this.settingsSaving) return;
    this.shortcuts = this.shortcutsBeforeSettings || this.shortcuts; this.shortcutsBeforeSettings = undefined;
    this.clearSettingsPassword(); this.settingsOpen = false;
  }

  private async saveSettings() {
    const changesPassword = Boolean(this.currentAccessPassword || this.newAccessPassword || this.confirmedAccessPassword);
    if (changesPassword) {
      if (!this.currentAccessPassword || !this.newAccessPassword || !this.confirmedAccessPassword) {
        this.settingsError = "Complete all password fields."; return;
      }
      if (this.newAccessPassword !== this.confirmedAccessPassword) {
        this.settingsError = "New passwords do not match."; return;
      }
      this.settingsSaving = true; this.settingsError = "";
      try {
        const response = await fetch("/api/access/password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: this.currentAccessPassword, new_password: this.newAccessPassword }) });
        if (!response.ok) { this.settingsError = response.status === 401 ? "Current password was not accepted." : "Could not change password."; return; }
        this.clearSettingsPassword();
      } catch {
        this.settingsError = "Could not change password."; return;
      } finally {
        this.settingsSaving = false;
      }
    }
    void this.saveWorkspace(); this.shortcutsBeforeSettings = undefined; this.settingsOpen = false;
  }

  private connect(id: string) {
    const host = this.renderRoot.querySelector<HTMLElement>(`[data-terminal="${id}"]`);
    if (!host || this.sessions.has(id)) return;
    const terminal = new Terminal({ cursorBlink: true, convertEol: false, fontFamily: '"Courier New", monospace', fontSize: TERMINAL_FONT_SIZE, lineHeight: 1, letterSpacing: 0, scrollback: 5000, theme: { background: "#181a1b", foreground: "#ebdbb2", cursor: "#fabd2f", selectionBackground: "#504945" } });
    const fit = new FitAddon(); terminal.loadAddon(fit); terminal.open(host);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${location.host}/ws/terminal/${id}`);
    socket.binaryType = "arraybuffer";
    const session: TerminalSession = { socket, terminal, fit }; this.sessions.set(id, session);
    terminal.writeln("\x1b[33mWorminal\x1b[0m · opening localhost shell…");
    this.fitTerminal(id);
    socket.onopen = () => { this.updateWindow(id, window => ({ ...window, phase: "ready" })); this.fitTerminal(id); terminal.focus(); };
    socket.onmessage = event => terminal.write(event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data);
    socket.onerror = () => { terminal.writeln("\r\n\x1b[31mShell connection failed.\x1b[0m"); this.updateWindow(id, window => ({ ...window, phase: "failed" })); };
    socket.onclose = () => { if (this.windows.some(window => window.id === id)) this.updateWindow(id, window => ({ ...window, phase: window.phase === "failed" ? "failed" : "closed" })); };
    terminal.onData(data => { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "input", data })); });
    session.resize = new ResizeObserver(() => this.fitTerminal(id)); session.resize.observe(host);
  }

  private fitTerminal(id: string) {
    const session = this.sessions.get(id);
    const host = this.renderRoot.querySelector<HTMLElement>(`[data-terminal="${id}"]`);
    if (!session || !host) return;
    session.fit.fit();
    const rows = Math.max(1, Math.floor(host.clientHeight / TERMINAL_ROW_HEIGHT));
    if (session.terminal.rows !== rows) session.terminal.resize(session.terminal.cols, rows);
    this.sendResize(id);
  }

  private sendResize(id: string) {
    const session = this.sessions.get(id); if (!session || session.socket.readyState !== WebSocket.OPEN) return;
    session.socket.send(JSON.stringify({ type: "resize", columns: session.terminal.cols, rows: session.terminal.rows }));
  }

  private destroySession(id: string) {
    const session = this.sessions.get(id); if (!session) return;
    session.resize?.disconnect(); session.socket.close(); session.terminal.dispose(); this.sessions.delete(id);
  }
  private close(id: string) { this.destroySession(id); this.windows = this.windows.filter(window => window.id !== id); this.persistence = this.persistence.then(() => fetch(`/api/workspace/windows/${id}`, { method: "DELETE" })).catch(() => undefined); }
  private focus(id: string) { this.updateWindow(id, window => ({ ...window, z: ++this.topZ, minimized: false })); void this.saveWorkspace(); this.updateComplete.then(() => this.sessions.get(id)?.terminal.focus()); }
  private toggleMaximize(id: string) { this.updateWindow(id, window => ({ ...window, maximized: !window.maximized, minimized: false, z: ++this.topZ })); void this.saveWorkspace(); this.updateComplete.then(() => this.fitTerminal(id)); }
  private toggleMinimize(id: string) { const item = this.windows.find(window => window.id === id); if (!item) return; if (!item.minimized) this.destroySession(id); this.updateWindow(id, window => ({ ...window, minimized: !window.minimized })); void this.saveWorkspace(); if (item.minimized) this.updateComplete.then(() => this.connect(id)); }

  private moveWindow(event: PointerEvent, id: string) {
    const item = this.windows.find(window => window.id === id); if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.editingWindow = true; this.focus(id); const startX = event.clientX; const startY = event.clientY; const originX = item.x; const originY = item.y;
    const move = (next: PointerEvent) => this.updateWindow(id, window => ({ ...window, x: originX + next.clientX - startX, y: originY + next.clientY - startY, width: bounds?.width ?? window.width, height: bounds?.height ?? window.height }));
    const stop = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", stop); this.editingWindow = false; void this.saveWorkspace(); };
    addEventListener("pointermove", move); addEventListener("pointerup", stop, { once: true });
  }

  private resizeWindow(event: PointerEvent, id: string) {
    const item = this.windows.find(window => window.id === id); if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.editingWindow = true; this.focus(id); const startX = event.clientX; const startY = event.clientY; const width = bounds?.width ?? item.width; const height = bounds?.height ?? item.height;
    const move = (next: PointerEvent) => this.updateWindow(id, window => ({ ...window, width: Math.max(300, width + next.clientX - startX), height: Math.max(190, height + next.clientY - startY) }));
    const stop = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", stop); this.editingWindow = false; void this.saveWorkspace(); };
    addEventListener("pointermove", move); addEventListener("pointerup", stop, { once: true });
  }

  private windowPointerDown(event: PointerEvent, id: string) {
    this.focus(id);
    if ((event.target as Element).closest("button") || !event.shiftKey || ![0, 2].includes(event.button)) return;
    event.preventDefault(); event.stopPropagation();
    if (event.button === 0) this.moveWindow(event, id); else this.resizeWindow(event, id);
  }

  private titlePointerDown(event: PointerEvent, id: string) {
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
    return html`<x-console-shell><x-utility-rail slot="header"><span class="brand">WORMINAL</span><x-command-button @click=${this.spawn}>+ NEW SHELL</x-command-button><span class="push optional">LOCALHOST WORKSPACE · ${this.windows.length} WINDOW${this.windows.length === 1 ? "" : "S"}</span><x-command-button aria-label="Settings" @click=${this.openSettings}>SETTINGS</x-command-button></x-utility-rail>
      <main class="desktop" aria-label="Worminal desktop">${this.windows.length ? nothing : html`<div class="welcome"><strong>NO OPEN SHELLS</strong><span>Use NEW SHELL to start a local terminal.</span></div>`}${this.windows.map(window => this.renderWindow(window))}</main>
      <x-status-rail slot="footer"><x-status-indicator .label=${`${ready} SHELL${ready === 1 ? "" : "S"} CONNECTED`} tone=${ready ? "green" : "orange"}></x-status-indicator><nav class="taskbar" aria-label="Open shells">${this.windows.map(window => html`<x-command-button class="task ${window.z === this.topZ && !window.minimized ? "active" : ""}" @click=${() => this.focus(window.id)}>${window.title}</x-command-button>`)}</nav><span class="push">LOCAL PTY · ${this.clock}</span></x-status-rail></x-console-shell>
      ${this.settingsOpen ? html`<div class="settings" role="presentation" @click=${this.closeSettings}><section class="settings-panel" role="dialog" aria-modal="true" aria-labelledby="settings-title" @click=${(event: Event) => event.stopPropagation()}><h2 id="settings-title">SETTINGS</h2><p>Press any key or key combination to set the action.</p><label class="shortcut-row"><span>New shell</span><input aria-label="New shell shortcut" .value=${this.shortcutLabel(this.newShellShortcut())} @keydown=${this.captureShortcut} readonly></label><div class="password-settings"><h3>ACCESS PASSWORD</h3><label><span>Current password</span><input aria-label="Current access password" type="password" autocomplete="current-password" .value=${this.currentAccessPassword} @input=${(event: InputEvent) => this.currentAccessPassword = (event.target as HTMLInputElement).value}></label><label><span>New password</span><input aria-label="New access password" type="password" autocomplete="new-password" .value=${this.newAccessPassword} @input=${(event: InputEvent) => this.newAccessPassword = (event.target as HTMLInputElement).value}></label><label><span>Confirm password</span><input aria-label="Confirm new access password" type="password" autocomplete="new-password" .value=${this.confirmedAccessPassword} @input=${(event: InputEvent) => this.confirmedAccessPassword = (event.target as HTMLInputElement).value}></label><div class="settings-error" role="alert">${this.settingsError}</div></div><div class="settings-actions"><x-command-button ?disabled=${this.settingsSaving} @click=${this.closeSettings}>CANCEL</x-command-button><x-command-button ?disabled=${this.settingsSaving} @click=${this.saveSettings}>${this.settingsSaving ? "SAVING…" : "SAVE"}</x-command-button></div></section></div>` : nothing}
      ${this.passwordRequired ? html`<div class="settings"><form class="access-panel" aria-label="Worminal access" @submit=${this.submitAccess}><h2>ACCESS PASSWORD</h2><p>Enter the single password for this Worminal host.</p><input aria-label="Access password" type="password" autocomplete="current-password" .value=${this.accessPassword} @input=${(event: InputEvent) => this.accessPassword = (event.target as HTMLInputElement).value} autofocus><div class="access-error" role="alert">${this.accessError}</div><div class="settings-actions"><x-command-button @click=${this.submitAccess}>CONNECT</x-command-button></div></form></div>` : nothing}`;
  }
}
customElements.define("worminal-desktop", WorminalDesktop);

export function mount(root: HTMLElement) { root.replaceChildren(document.createElement("worminal-desktop")); }
