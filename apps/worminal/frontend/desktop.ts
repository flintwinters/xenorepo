import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import xtermCss from "@xterm/xterm/css/xterm.css";
import { LitElement, css, html, nothing, unsafeCSS } from "lit";
import "@xenorepo/lit-ui";
import { WorminalClient } from "./services/api.js";
import { captureShortcut, defaultShortcut, isStandaloneModifier, matchesShortcut, shortcutLabel } from "./shortcuts.js";
import { SessionRegistry, type TerminalSession } from "./sessions.js";
import { TERMINAL_FONT_SIZE, TERMINAL_ROW_HEIGHT } from "./styles.js";
import type { Phase, Shortcut, TabState, WindowState, WorkspacePayload } from "./types.js";

const FAVICON = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">',
  '<path d="M2 14c3-7 7-7 11-2s7 5 9-2" fill="none" stroke="#ff69b4" ',
  'stroke-width="4" stroke-linecap="round"/></svg>',
].join("");

export class WorminalDesktop extends LitElement {
  static properties = {
    windows: { state: true },
    clock: { state: true },
    shortcuts: { state: true },
    settingsOpen: { state: true },
    currentAccessPassword: { state: true },
    newAccessPassword: { state: true },
    confirmedAccessPassword: { state: true },
    settingsError: { state: true },
    settingsSaving: { state: true },
  };
  declare windows: WindowState[];
  declare clock: string;
  declare shortcuts: Shortcut[];
  declare settingsOpen: boolean;
  declare currentAccessPassword: string;
  declare newAccessPassword: string;
  declare confirmedAccessPassword: string;
  declare settingsError: string;
  declare settingsSaving: boolean;
  private sessionRegistry = new SessionRegistry();
  private sessions = this.sessionRegistry.sessions;
  private client = new WorminalClient();
  private nextTitle = 1;
  private topZ = 1;
  private clockTimer?: number;
  private workspaceTimer?: number;
  private editingWindow = false;
  private pendingSaves = 0;
  private workspaceDirty = false;
  private persistence: Promise<unknown> = Promise.resolve();
  private shortcutsBeforeSettings?: Shortcut[];
  private standaloneShortcutHeld?: string;

  constructor() {
    super();
    this.windows = [];
    this.clock = "--:--:--";
    this.shortcuts = [this.defaultShortcut()];
    this.settingsOpen = false;
    this.currentAccessPassword = "";
    this.newAccessPassword = "";
    this.confirmedAccessPassword = "";
    this.settingsError = "";
    this.settingsSaving = false;
  }

  static styles = [
    unsafeCSS(xtermCss),
    css`
      :host {
        display: block;
        height: 100%;
        color: #ebdbb2;
        font:
          11px/1.15 "Courier New",
          monospace;
        background: #1d2021;
      }
      * {
        box-sizing: border-box;
      }
      x-console-shell {
        height: 100%;
      }
      .brand {
        color: #fabd2f;
        font-weight: bold;
        letter-spacing: 0.1em;
      }
      .push {
        margin-left: auto;
      }
      .desktop {
        position: relative;
        min-width: 0;
        min-height: 0;
        overflow: hidden;
        background-color: #1a1d1c;
        background-image:
          linear-gradient(#282b2a 1px, transparent 1px), linear-gradient(90deg, #282b2a 1px, transparent 1px);
        background-size: 24px 24px;
      }
      .welcome {
        position: absolute;
        inset: 0;
        display: grid;
        place-content: center;
        gap: 10px;
        text-align: center;
        color: #a89984;
        pointer-events: none;
      }
      .welcome strong {
        color: #ebdbb2;
        font-size: 18px;
      }
      .window {
        position: absolute;
        display: grid;
        grid-template-rows: 20px minmax(0, 1fr);
        min-width: 300px;
        min-height: 190px;
        overflow: hidden;
        background: #181a1b;
        border: 1px solid #111;
        box-shadow: 5px 7px 18px #0009;
        resize: both;
      }
      .window.active {
        border-color: #83a598;
        box-shadow:
          5px 7px 22px #000c,
          0 0 0 1px #83a598;
      }
      .window.maximized {
        inset: 0 !important;
        width: 100% !important;
        height: 100% !important;
        resize: none;
      }
      .titlebar {
        display: flex;
        align-items: stretch;
        min-width: 0;
        color: #1d2021;
        font-weight: bold;
        background: linear-gradient(#83a598, #5f7f75);
        border-top: 1px solid #b7cfca;
        border-bottom: 2px solid #354a44;
        cursor: move;
        user-select: none;
        touch-action: none;
      }
      .window:not(.active) .titlebar {
        filter: saturate(0.35) brightness(0.72);
      }
      .tabs {
        display: flex;
        min-width: 0;
        overflow: hidden;
      }
      .tab {
        display: flex;
        align-items: center;
        gap: 5px;
        min-width: 72px;
        max-width: 180px;
        padding: 0 5px;
        opacity: 0.68;
        border-right: 1px solid #354a44;
        cursor: grab;
      }
      .tab.active {
        opacity: 1;
        background: #b7cfca55;
      }
      .tab-title {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .tab-close {
        width: auto !important;
        padding: 0 2px !important;
        color: #282828 !important;
        background: transparent !important;
        border: 0 !important;
      }
      .new-tab {
        width: 24px;
        color: #282828 !important;
        background: transparent !important;
        border: 0 !important;
      }
      .phase {
        color: #282828;
        font-weight: normal;
      }
      .controls {
        display: flex;
        align-self: stretch;
        margin-left: auto;
      }
      .titlebar button {
        width: 24px;
        padding: 0;
        color: #ebdbb2;
        font: inherit;
        background: #35312f;
        border: 1px solid #928374;
        cursor: pointer;
      }
      .titlebar button:hover {
        background: #45413f;
        border-color: #c6b58f;
      }
      .titlebar button:active {
        background: #181716;
      }
      .terminal-stack {
        position: relative;
        min-width: 0;
        min-height: 0;
      }
      .terminal-host {
        position: absolute;
        inset: 0;
        min-width: 0;
        min-height: 0;
        padding: 5px;
        overflow: hidden;
        background: #181a1b;
      }
      .terminal-host:not(.active) {
        visibility: hidden;
        pointer-events: none;
      }
      .terminal-host .xterm {
        height: 100%;
      }
      .terminal-host .xterm-viewport {
        scrollbar-color: #665c54 #181a1b;
      }
      .terminal-host .xterm-rows > div {
        height: ${TERMINAL_ROW_HEIGHT}px !important;
        line-height: ${TERMINAL_ROW_HEIGHT}px !important;
        overflow: visible !important;
      }
      .taskbar {
        display: flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        overflow-x: auto;
      }
      .task {
        min-width: 95px;
        max-width: 170px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .task.active {
        color: #fabd2f;
      }
      .settings {
        position: fixed;
        inset: 0;
        z-index: 200000;
        display: grid;
        place-items: center;
        padding: 18px;
        background: #000a;
      }
      .settings-panel {
        width: min(440px, 100%);
        padding: 16px;
        color: #ebdbb2;
        background: #282828;
        border: 1px solid #83a598;
        box-shadow: 8px 10px 30px #000;
      }
      .settings-panel h2 {
        margin: 0 0 8px;
        color: #fabd2f;
        font-size: 15px;
        letter-spacing: 0.08em;
      }
      .settings-panel p {
        margin: 0 0 14px;
        color: #a89984;
      }
      .shortcut-row {
        display: grid;
        grid-template-columns: 1fr minmax(160px, 1fr);
        gap: 10px;
        align-items: center;
        padding: 10px 0;
        border-top: 1px solid #504945;
      }
      .shortcut-row input {
        width: 100%;
        padding: 7px;
        color: #ebdbb2;
        font: inherit;
        background: #1d2021;
        border: 1px solid #665c54;
      }
      .shortcut-row input:focus {
        outline: 1px solid #fabd2f;
        border-color: #fabd2f;
      }
      .password-settings {
        display: grid;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #504945;
      }
      .password-settings h3 {
        margin: 0 0 2px;
        color: #83a598;
        font-size: 12px;
        letter-spacing: 0.06em;
      }
      .password-settings label {
        display: grid;
        grid-template-columns: 1fr minmax(160px, 1fr);
        gap: 10px;
        align-items: center;
      }
      .password-settings input {
        width: 100%;
        padding: 7px;
        color: #ebdbb2;
        font: inherit;
        background: #1d2021;
        border: 1px solid #665c54;
      }
      .password-settings input:focus {
        outline: 1px solid #fabd2f;
        border-color: #fabd2f;
      }
      .settings-error {
        min-height: 15px;
        color: #fb4934;
      }
      .settings-actions {
        display: flex;
        justify-content: flex-end;
        gap: 7px;
        margin-top: 14px;
      }
      @media (max-width: 620px) {
        .optional {
          display: none;
        }
        .window {
          min-width: 260px;
        }
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();
    this.renderRoot.addEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.addEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.addEventListener("keydown", this.handleSuperKeyDown, { capture: true });
    window.addEventListener("keyup", this.handleSuperKeyUp, { capture: true });
    this.clockTimer = window.setInterval(
      () => (this.clock = new Date().toLocaleTimeString([], { hour12: false })),
      1000,
    );
    this.workspaceTimer = window.setInterval(() => void this.syncWorkspace(), 750);
    void this.restoreWorkspace();
  }
  disconnectedCallback() {
    this.renderRoot.removeEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.removeEventListener("contextmenu", this.blockShiftContextMenu, { capture: true });
    window.removeEventListener("keydown", this.handleSuperKeyDown, { capture: true });
    window.removeEventListener("keyup", this.handleSuperKeyUp, { capture: true });
    for (const id of this.sessions.keys()) this.destroySession(id);
    clearInterval(this.clockTimer);
    clearInterval(this.workspaceTimer);
    super.disconnectedCallback();
  }

  private blockShiftContextMenu = (event: Event) => {
    const target = event.target as Node | null;
    if (
      !(event as MouseEvent).shiftKey ||
      !((target && this.renderRoot.contains(target)) || event.composedPath().includes(this))
    )
      return;
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
    event.preventDefault();
    event.stopImmediatePropagation();
    void this.spawn();
  };

  private handleSuperKeyUp = (event: KeyboardEvent) => {
    if (this.settingsOpen || event.key !== this.standaloneShortcutHeld) return;
    this.standaloneShortcutHeld = undefined;
    void this.spawn();
  };

  private defaultShortcut(): Shortcut {
    return defaultShortcut();
  }
  private newShellShortcut() {
    return this.shortcuts.find((shortcut) => shortcut.action === "new-shell") || this.defaultShortcut();
  }
  private matchesShortcut(event: KeyboardEvent, shortcut: Shortcut) {
    return matchesShortcut(event, shortcut);
  }
  private isStandaloneModifier(shortcut: Shortcut) {
    return isStandaloneModifier(shortcut);
  }
  private shortcutLabel(shortcut: Shortcut) {
    return shortcutLabel(shortcut);
  }
  private captureShortcut(event: KeyboardEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.shortcuts = [captureShortcut(event)];
  }

  private updateWindow(id: string, change: (window: WindowState) => WindowState) {
    this.windows = this.windows.map((window) => (window.id === id ? change(window) : window));
  }

  private updateTab(id: string, change: (tab: TabState) => TabState) {
    this.windows = this.windows.map((item) => ({
      ...item,
      tabs: item.tabs.map((tab) => (tab.id === id ? change(tab) : tab)),
    }));
  }

  private async restoreWorkspace() {
    let response = await this.client.workspace();
    while (response.status === 401) {
      const password = window.prompt("Worminal access password:");
      if (password === null) return;
      if (!(await this.grantAccess(password))) continue;
      response = await this.client.workspace();
    }
    if (!response.ok) return;
    const state = (await response.json()) as WorkspacePayload;
    this.windows = state.windows.map((window) => ({
      ...window,
      tabs: window.tabs.map((tab) => ({ ...tab, phase: "connecting" as Phase })),
    }));
    this.shortcuts = state.shortcuts?.length ? state.shortcuts : [this.defaultShortcut()];
    this.topZ = Math.max(1, ...this.windows.map((window) => window.z));
    this.nextTitle = Math.max(
      1,
      ...this.windows.flatMap((item) => item.tabs).map((tab) => Number(tab.title.match(/^shell-(\d+)$/)?.[1] || 0) + 1),
    );
    if (!this.windows.length) {
      this.spawn();
      return;
    }
    await this.updateComplete;
    for (const item of this.windows) if (!item.minimized) for (const tab of item.tabs) this.connect(tab.id);
  }

  private async syncWorkspace() {
    if (this.settingsOpen || this.editingWindow || this.pendingSaves) return;
    if (this.workspaceDirty) {
      void this.saveWorkspace();
      return;
    }
    const response = await this.client.workspace();
    if (!response.ok) return;
    const state = (await response.json()) as WorkspacePayload;
    const previousTabs = new Map(this.windows.flatMap((item) => item.tabs).map((tab) => [tab.id, tab]));
    const declared = new Set(state.windows.flatMap((item) => item.tabs).map((tab) => tab.id));
    for (const id of this.sessions.keys()) if (!declared.has(id)) this.destroySession(id);
    this.windows = state.windows.map((window) => ({
      ...window,
      tabs: window.tabs.map((tab) => ({ ...tab, phase: previousTabs.get(tab.id)?.phase || "connecting" })),
    }));
    this.shortcuts = state.shortcuts?.length ? state.shortcuts : [this.defaultShortcut()];
    this.topZ = Math.max(1, ...this.windows.map((window) => window.z));
    this.nextTitle = Math.max(
      1,
      ...this.windows.flatMap((item) => item.tabs).map((tab) => Number(tab.title.match(/^shell-(\d+)$/)?.[1] || 0) + 1),
    );
    await this.updateComplete;
    for (const item of this.windows)
      for (const tab of item.tabs) item.minimized ? this.destroySession(tab.id) : this.connect(tab.id);
  }

  private async grantAccess(password: string) {
    const access = await this.client.grantAccess(password);
    if (access.ok) return true;
    window.alert("The password was not accepted.");
    return false;
  }

  private savedWindows() {
    return this.windows.map((item) => ({ ...item, tabs: item.tabs.map(({ phase, ...tab }) => tab) }));
  }

  private saveWorkspace() {
    const body = JSON.stringify({ windows: this.savedWindows(), shortcuts: this.shortcuts });
    this.workspaceDirty = true;
    this.pendingSaves++;
    this.persistence = this.persistence
      .then(async () => {
        const payload = JSON.parse(body) as { windows: WorkspacePayload["windows"]; shortcuts: Shortcut[] };
        const response = await this.client.saveWorkspace(payload.windows, payload.shortcuts);
        if (!response.ok) throw new Error("Could not save Worminal workspace.");
        const current = JSON.stringify({ windows: this.savedWindows(), shortcuts: this.shortcuts });
        if (current === body) this.workspaceDirty = false;
      })
      .catch(() => undefined)
      .finally(() => this.pendingSaves--);
    return this.persistence;
  }

  private async spawn() {
    const id = crypto.randomUUID();
    const tab = this.createTab();
    const offset = (this.nextTitle - 2) % 7;
    this.windows = [
      ...this.windows,
      {
        id,
        title: tab.title,
        x: 32 + offset * 28,
        y: 30 + offset * 24,
        width: 650,
        height: 410,
        z: ++this.topZ,
        minimized: false,
        maximized: false,
        active_tab_id: tab.id,
        tabs: [tab],
      },
    ];
    await this.saveWorkspace();
    await this.updateComplete;
    this.connect(tab.id);
  }

  private createTab(): TabState {
    return { id: crypto.randomUUID(), title: `shell-${this.nextTitle++}`, position: 0, phase: "connecting" };
  }

  private async newTab(windowId: string) {
    const tab = this.createTab();
    this.updateWindow(windowId, (item) => ({
      ...item,
      title: tab.title,
      active_tab_id: tab.id,
      tabs: [...item.tabs, { ...tab, position: item.tabs.length }],
    }));
    await this.saveWorkspace();
    await this.updateComplete;
    this.connect(tab.id);
  }

  private clearSettingsPassword() {
    this.currentAccessPassword = "";
    this.newAccessPassword = "";
    this.confirmedAccessPassword = "";
    this.settingsError = "";
  }

  private openSettings() {
    this.shortcutsBeforeSettings = this.shortcuts.map((shortcut) => ({ ...shortcut }));
    this.clearSettingsPassword();
    this.settingsOpen = true;
  }

  private closeSettings() {
    if (this.settingsSaving) return;
    this.shortcuts = this.shortcutsBeforeSettings || this.shortcuts;
    this.shortcutsBeforeSettings = undefined;
    this.clearSettingsPassword();
    this.settingsOpen = false;
  }

  private async saveSettings() {
    const changesPassword = Boolean(
      this.currentAccessPassword || this.newAccessPassword || this.confirmedAccessPassword,
    );
    if (changesPassword) {
      if (!this.currentAccessPassword || !this.newAccessPassword || !this.confirmedAccessPassword) {
        this.settingsError = "Complete all password fields.";
        return;
      }
      if (this.newAccessPassword !== this.confirmedAccessPassword) {
        this.settingsError = "New passwords do not match.";
        return;
      }
      this.settingsSaving = true;
      this.settingsError = "";
      try {
        const response = await fetch("/api/access/password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ current_password: this.currentAccessPassword, new_password: this.newAccessPassword }),
        });
        if (!response.ok) {
          this.settingsError =
            response.status === 401 ? "Current password was not accepted." : "Could not change password.";
          return;
        }
        this.clearSettingsPassword();
      } catch {
        this.settingsError = "Could not change password.";
        return;
      } finally {
        this.settingsSaving = false;
      }
    }
    void this.saveWorkspace();
    this.shortcutsBeforeSettings = undefined;
    this.settingsOpen = false;
  }

  private connect(id: string) {
    const host = this.renderRoot.querySelector<HTMLElement>(`[data-terminal="${id}"]`);
    if (!host || this.sessions.has(id)) return;
    const terminal = new Terminal({
      cursorBlink: true,
      convertEol: false,
      fontFamily: '"Courier New", monospace',
      fontSize: TERMINAL_FONT_SIZE,
      lineHeight: 1,
      letterSpacing: 0,
      scrollback: 5000,
      theme: { background: "#181a1b", foreground: "#ebdbb2", cursor: "#fabd2f", selectionBackground: "#504945" },
    });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(host);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${location.host}/ws/terminal/${id}`);
    socket.binaryType = "arraybuffer";
    const session: TerminalSession = { socket, terminal, fit };
    this.sessions.set(id, session);
    terminal.writeln("\x1b[33mWorminal\x1b[0m · opening localhost shell…");
    this.fitTerminal(id);
    socket.onopen = () => {
      this.updateTab(id, (tab) => ({ ...tab, phase: "ready" }));
      this.fitTerminal(id);
      terminal.focus();
    };
    socket.onmessage = (event) =>
      terminal.write(event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data);
    socket.onerror = () => {
      terminal.writeln("\r\n\x1b[31mShell connection failed.\x1b[0m");
      this.updateTab(id, (tab) => ({ ...tab, phase: "failed" }));
    };
    socket.onclose = () => {
      if (this.windows.some((item) => item.tabs.some((tab) => tab.id === id)))
        this.updateTab(id, (tab) => ({ ...tab, phase: tab.phase === "failed" ? "failed" : "closed" }));
    };
    terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "input", data }));
    });
    session.resize = new ResizeObserver(() => this.fitTerminal(id));
    session.resize.observe(host);
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
    const session = this.sessions.get(id);
    if (!session || session.socket.readyState !== WebSocket.OPEN) return;
    session.socket.send(
      JSON.stringify({ type: "resize", columns: session.terminal.cols, rows: session.terminal.rows }),
    );
  }

  private destroySession(id: string) {
    const session = this.sessions.get(id);
    if (!session) return;
    this.sessionRegistry.destroy(id);
  }
  private close(id: string) {
    const item = this.windows.find((window) => window.id === id);
    if (!item) return;
    for (const tab of item.tabs) this.destroySession(tab.id);
    this.windows = this.windows.filter((window) => window.id !== id);
    this.persistence = this.persistence.then(() => this.client.deleteWindow(id)).catch(() => undefined);
  }
  private closeTab(windowId: string, tabId: string) {
    const item = this.windows.find((window) => window.id === windowId);
    if (!item) return;
    if (item.tabs.length === 1) {
      this.close(windowId);
      return;
    }
    this.destroySession(tabId);
    const tabs = item.tabs.filter((tab) => tab.id !== tabId).map((tab, position) => ({ ...tab, position }));
    const active =
      item.active_tab_id === tabId
        ? tabs[
            Math.min(
              item.tabs.findIndex((tab) => tab.id === tabId),
              tabs.length - 1,
            )
          ]
        : tabs.find((tab) => tab.id === item.active_tab_id)!;
    this.updateWindow(windowId, (window) => ({ ...window, tabs, active_tab_id: active.id, title: active.title }));
    void this.saveWorkspace();
    this.persistence = this.persistence.then(() => this.client.deleteTab(tabId)).catch(() => undefined);
  }
  private focusWindow(id: string) {
    const item = this.windows.find((window) => window.id === id);
    this.updateWindow(id, (window) => ({ ...window, z: ++this.topZ, minimized: false }));
    void this.saveWorkspace();
    this.updateComplete.then(() => {
      if (item) {
        this.connect(item.active_tab_id);
        this.fitTerminal(item.active_tab_id);
        this.sessions.get(item.active_tab_id)?.terminal.focus();
      }
    });
  }
  private activateTab(windowId: string, tabId: string) {
    const tab = this.windows.find((item) => item.id === windowId)?.tabs.find((candidate) => candidate.id === tabId);
    if (!tab) return;
    this.updateWindow(windowId, (item) => ({ ...item, active_tab_id: tabId, title: tab.title, z: ++this.topZ }));
    void this.saveWorkspace();
    this.updateComplete.then(() => {
      this.fitTerminal(tabId);
      this.sessions.get(tabId)?.terminal.focus();
    });
  }
  private toggleMaximize(id: string) {
    this.updateWindow(id, (window) => ({ ...window, maximized: !window.maximized, minimized: false, z: ++this.topZ }));
    void this.saveWorkspace();
    this.updateComplete.then(() => this.fitTerminal(id));
  }
  private toggleMinimize(id: string) {
    const item = this.windows.find((window) => window.id === id);
    if (!item) return;
    if (!item.minimized) for (const tab of item.tabs) this.destroySession(tab.id);
    this.updateWindow(id, (window) => ({ ...window, minimized: !window.minimized }));
    void this.saveWorkspace();
    if (item.minimized)
      this.updateComplete.then(() => {
        for (const tab of item.tabs) this.connect(tab.id);
      });
  }

  private dragTab(event: PointerEvent, sourceWindowId: string, tabId: string) {
    if (event.shiftKey || event.button !== 0 || (event.target as Element).closest("button")) return;
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startY = event.clientY;
    const stop = (released: PointerEvent) => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", stop);
      if (Math.hypot(released.clientX - startX, released.clientY - startY) < 8) {
        this.activateTab(sourceWindowId, tabId);
        return;
      }
      const elements = (this.renderRoot as ShadowRoot).elementsFromPoint(released.clientX, released.clientY);
      const targetTab = elements.find((element) => element instanceof HTMLElement && element.dataset.tab) as
        | HTMLElement
        | undefined;
      const targetWindow = elements.find(
        (element) => element instanceof HTMLElement && element.dataset.tabDropWindow,
      ) as HTMLElement | undefined;
      this.moveTab(
        sourceWindowId,
        targetWindow?.dataset.tabDropWindow,
        tabId,
        released.clientX,
        released.clientY,
        targetTab?.dataset.tab,
      );
    };
    const move = () => undefined;
    addEventListener("pointermove", move);
    addEventListener("pointerup", stop, { once: true });
  }

  private moveTab(
    sourceWindowId: string,
    targetWindowId: string | undefined,
    tabId: string,
    x: number,
    y: number,
    beforeTabId?: string,
  ) {
    const source = this.windows.find((item) => item.id === sourceWindowId);
    const tab = source?.tabs.find((item) => item.id === tabId);
    if (!source || !tab) return;
    let windows = this.windows.map((item) => ({ ...item, tabs: [...item.tabs] }));
    const sourceCopy = windows.find((item) => item.id === sourceWindowId)!;
    sourceCopy.tabs = sourceCopy.tabs
      .filter((item) => item.id !== tabId)
      .map((item, position) => ({ ...item, position }));
    if (sourceCopy.tabs.length) {
      const active =
        sourceCopy.active_tab_id === tabId
          ? sourceCopy.tabs[0]
          : sourceCopy.tabs.find((item) => item.id === sourceCopy.active_tab_id)!;
      sourceCopy.active_tab_id = active.id;
      sourceCopy.title = active.title;
    } else windows = windows.filter((item) => item.id !== sourceWindowId);
    const target = targetWindowId ? windows.find((item) => item.id === targetWindowId) : undefined;
    if (target) {
      const requested = beforeTabId ? target.tabs.findIndex((item) => item.id === beforeTabId) : -1;
      const insertion = requested >= 0 ? requested : target.tabs.length;
      target.tabs.splice(insertion, 0, tab);
      target.tabs = target.tabs.map((item, position) => ({ ...item, position }));
      target.active_tab_id = tab.id;
      target.title = tab.title;
      target.z = ++this.topZ;
    } else {
      const id = crypto.randomUUID();
      windows.push({
        id,
        title: tab.title,
        x: Math.max(0, x - 90),
        y: Math.max(0, y - 10),
        width: source.width,
        height: source.height,
        z: ++this.topZ,
        minimized: false,
        maximized: false,
        active_tab_id: tab.id,
        tabs: [{ ...tab, position: 0 }],
      });
    }
    this.windows = windows;
    void this.saveWorkspace();
    if (!sourceCopy.tabs.length)
      this.persistence = this.persistence.then(() => this.client.deleteWindow(sourceWindowId)).catch(() => undefined);
    this.updateComplete.then(() => {
      this.fitTerminal(tabId);
      this.sessions.get(tabId)?.terminal.focus();
    });
  }

  private moveWindow(event: PointerEvent, id: string) {
    const item = this.windows.find((window) => window.id === id);
    if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.editingWindow = true;
    this.focusWindow(id);
    const startX = event.clientX;
    const startY = event.clientY;
    const originX = item.x;
    const originY = item.y;
    const move = (next: PointerEvent) =>
      this.updateWindow(id, (window) => ({
        ...window,
        x: originX + next.clientX - startX,
        y: originY + next.clientY - startY,
        width: bounds?.width ?? window.width,
        height: bounds?.height ?? window.height,
      }));
    const stop = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", stop);
      this.editingWindow = false;
      void this.saveWorkspace();
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", stop, { once: true });
  }

  private resizeWindow(event: PointerEvent, id: string) {
    const item = this.windows.find((window) => window.id === id);
    if (!item || item.maximized) return;
    const frame = this.renderRoot.querySelector<HTMLElement>(`[data-window="${id}"]`);
    const bounds = frame?.getBoundingClientRect();
    this.editingWindow = true;
    this.focusWindow(id);
    const startX = event.clientX;
    const startY = event.clientY;
    const width = bounds?.width ?? item.width;
    const height = bounds?.height ?? item.height;
    const move = (next: PointerEvent) =>
      this.updateWindow(id, (window) => ({
        ...window,
        width: Math.max(300, width + next.clientX - startX),
        height: Math.max(190, height + next.clientY - startY),
      }));
    const stop = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", stop);
      this.editingWindow = false;
      void this.saveWorkspace();
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", stop, { once: true });
  }

  private windowPointerDown(event: PointerEvent, id: string) {
    this.focusWindow(id);
    if ((event.target as Element).closest("button") || !event.shiftKey || ![0, 2].includes(event.button)) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.button === 0) this.moveWindow(event, id);
    else this.resizeWindow(event, id);
  }

  private titlePointerDown(event: PointerEvent, id: string) {
    if (event.shiftKey || event.button !== 0 || (event.target as Element).closest("button")) return;
    event.stopPropagation();
    this.moveWindow(event, id);
  }

  private renderWindow(window: WindowState) {
    if (window.minimized) return nothing;
    const style = [
      `left:${window.x}px`,
      `top:${window.y}px`,
      `width:${window.width}px`,
      `height:${window.height}px`,
      `z-index:${window.z}`,
    ].join(";");
    return html`<section
      data-window=${window.id}
      class="window ${window.z === this.topZ ? "active" : ""} ${window.maximized ? "maximized" : ""}"
      style=${style}
      @pointerdown=${(event: PointerEvent) => this.windowPointerDown(event, window.id)}
      aria-label=${window.title}
    >
      <header
        class="titlebar"
        data-tab-drop-window=${window.id}
        @pointerdown=${(event: PointerEvent) => this.titlePointerDown(event, window.id)}
        @dblclick=${() => this.toggleMaximize(window.id)}
      >
        <div class="tabs">
          ${window.tabs.map(
            (tab) =>
              html`<div
                class="tab ${tab.id === window.active_tab_id ? "active" : ""}"
                data-tab=${tab.id}
                @pointerdown=${(event: PointerEvent) => this.dragTab(event, window.id, tab.id)}
                @dblclick=${(event: Event) => event.stopPropagation()}
              >
                <span>▣</span><span class="tab-title">${tab.title}</span
                ><span class="phase">${tab.phase === "ready" ? "" : tab.phase.toUpperCase()}</span
                ><button
                  class="tab-close"
                  aria-label="Close tab ${tab.title}"
                  @click=${() => this.closeTab(window.id, tab.id)}
                >
                  ×
                </button>
              </div>`,
          )}
        </div>
        <button class="new-tab" aria-label=${`New tab in ${window.title}`} @click=${() => this.newTab(window.id)}>
          +
        </button>
        <div class="controls">
          <button aria-label="Minimize ${window.title}" @click=${() => this.toggleMinimize(window.id)}>_</button
          ><button aria-label="Maximize ${window.title}" @click=${() => this.toggleMaximize(window.id)}>□</button
          ><button aria-label="Close ${window.title}" @click=${() => this.close(window.id)}>×</button>
        </div>
      </header>
      <div class="terminal-stack">
        ${window.tabs.map(
          (tab) =>
            html`<div
              class="terminal-host ${tab.id === window.active_tab_id ? "active" : ""}"
              data-terminal=${tab.id}
              aria-label=${`${tab.title} terminal`}
            ></div>`,
        )}
      </div>
    </section>`;
  }

  render() {
    const tabs = this.windows.flatMap((item) => item.tabs);
    const ready = tabs.filter((tab) => tab.phase === "ready").length;
    return html`<x-console-shell
        ><x-utility-rail slot="header"
          ><span class="brand">WORMINAL</span><x-command-button @click=${this.spawn}>+ NEW SHELL</x-command-button
          ><span class="push optional"
            >LOCALHOST WORKSPACE · ${this.windows.length} WINDOW${this.windows.length === 1 ? "" : "S"}</span
          ><x-command-button aria-label="Settings" @click=${this.openSettings}
            >SETTINGS</x-command-button
          ></x-utility-rail
        >
        <main class="desktop" aria-label="Worminal desktop">
          ${this.windows.length
            ? nothing
            : html`<div class="welcome">
                <strong>NO OPEN SHELLS</strong><span>Use NEW SHELL to start a local terminal.</span>
              </div>`}${this.windows.map((window) => this.renderWindow(window))}
        </main>
        <x-status-rail slot="footer"
          ><x-status-indicator
            .label=${`${ready} SHELL${ready === 1 ? "" : "S"} CONNECTED`}
            tone=${ready ? "green" : "orange"}
          ></x-status-indicator>
          <nav class="taskbar" aria-label="Open shells">
            ${this.windows.map(
              (window) =>
                html`<x-command-button
                  class="task ${window.z === this.topZ && !window.minimized ? "active" : ""}"
                  @click=${() => this.focusWindow(window.id)}
                  >${window.title}${window.tabs.length > 1 ? ` (${window.tabs.length})` : ""}</x-command-button
                >`,
            )}
          </nav>
          <span class="push">LOCAL PTY · ${this.clock}</span></x-status-rail
        ></x-console-shell
      >
      ${this.settingsOpen
        ? html`<div class="settings" role="presentation" @click=${this.closeSettings}>
            <section
              class="settings-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-title"
              @click=${(event: Event) => event.stopPropagation()}
            >
              <h2 id="settings-title">SETTINGS</h2>
              <p>Press any key or key combination to set the action.</p>
              <label class="shortcut-row"
                ><span>New shell</span
                ><input
                  aria-label="New shell shortcut"
                  .value=${this.shortcutLabel(this.newShellShortcut())}
                  @keydown=${this.captureShortcut}
                  readonly
              /></label>
              <div class="password-settings">
                <h3>ACCESS PASSWORD</h3>
                <label
                  ><span>Current password</span
                  ><input
                    aria-label="Current access password"
                    type="password"
                    autocomplete="current-password"
                    .value=${this.currentAccessPassword}
                    @input=${(event: InputEvent) =>
                      (this.currentAccessPassword = (event.target as HTMLInputElement).value)} /></label
                ><label
                  ><span>New password</span
                  ><input
                    aria-label="New access password"
                    type="password"
                    autocomplete="new-password"
                    .value=${this.newAccessPassword}
                    @input=${(event: InputEvent) =>
                      (this.newAccessPassword = (event.target as HTMLInputElement).value)} /></label
                ><label
                  ><span>Confirm password</span
                  ><input
                    aria-label="Confirm new access password"
                    type="password"
                    autocomplete="new-password"
                    .value=${this.confirmedAccessPassword}
                    @input=${(event: InputEvent) =>
                      (this.confirmedAccessPassword = (event.target as HTMLInputElement).value)}
                /></label>
                <div class="settings-error" role="alert">${this.settingsError}</div>
              </div>
              <div class="settings-actions">
                <x-command-button ?disabled=${this.settingsSaving} @click=${this.closeSettings}>CANCEL</x-command-button
                ><x-command-button ?disabled=${this.settingsSaving} @click=${this.saveSettings}
                  >${this.settingsSaving ? "SAVING…" : "SAVE"}</x-command-button
                >
              </div>
            </section>
          </div>`
        : nothing}`;
  }
}
export function installFavicon(): void {
  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = `data:image/svg+xml,${encodeURIComponent(FAVICON)}`;
  document.head.querySelector('link[rel="icon"]')?.remove();
  document.head.append(favicon);
}
