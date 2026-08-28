import { FitAddon } from "@xterm/addon-fit"; import { Terminal } from "@xterm/xterm";
import { LitElement } from "lit";
import "@xenorepo/lit-ui";
import { WorminalClient } from "./services/api.js";
import { desktopStyles } from "./desktop-styles.js";
import { renderDesktop, type DesktopView } from "./desktop-view.js";
import { captureShortcut, defaultShortcut, isStandaloneModifier, matchesShortcut, shortcutLabel } from "./shortcuts.js";
import { SessionRegistry, type TerminalSession } from "./sessions.js";
import { TERMINAL_FONT_SIZE, TERMINAL_ROW_HEIGHT } from "./styles.js";
import type { Shortcut, TabState, WindowState, WorkspacePayload } from "./types.js";
export { installFavicon } from "./favicon.js";
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
  declare windows: WindowState[]; declare clock: string; declare shortcuts: Shortcut[];
  declare settingsOpen: boolean; declare settingsSaving: boolean; declare settingsError: string;
  declare currentAccessPassword: string; declare newAccessPassword: string; declare confirmedAccessPassword: string;
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
  static styles = desktopStyles;
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
    this.applyWorkspace(state, new Map());
    if (!this.windows.length) {
      this.spawn();
      return;
    }
    await this.updateComplete;
    this.reconcileSessions();
  }
  private async syncWorkspace() {
    if (!this.workspaceCanSync()) return;
    if (this.workspaceDirty) {
      void this.saveWorkspace();
      return;
    }
    const response = await this.client.workspace();
    if (!response.ok) return;
    const state = (await response.json()) as WorkspacePayload;
    const previousTabs = new Map(this.windows.flatMap((item) => item.tabs).map((tab) => [tab.id, tab]));
    this.removeUndeclaredSessions(state);
    this.applyWorkspace(state, previousTabs);
    await this.updateComplete;
    this.reconcileSessions();
  }
  private workspaceCanSync() {
    return !this.settingsOpen && !this.editingWindow && !this.pendingSaves;
  }
  private removeUndeclaredSessions(state: WorkspacePayload) {
    const declared = new Set(state.windows.flatMap((item) => item.tabs).map((tab) => tab.id));
    for (const id of this.sessions.keys()) if (!declared.has(id)) this.destroySession(id);
  }
  private applyWorkspace(state: WorkspacePayload, previousTabs: Map<string, TabState>) {
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
  }
  private reconcileSessions() {
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
    const validationError = this.passwordValidationError();
    if (validationError) return void (this.settingsError = validationError);
    if (this.passwordFieldsUsed() && !(await this.changePassword())) return;
    void this.saveWorkspace();
    this.shortcutsBeforeSettings = undefined;
    this.settingsOpen = false;
  }
  private passwordFieldsUsed() {
    return Boolean(this.currentAccessPassword || this.newAccessPassword || this.confirmedAccessPassword);
  }
  private passwordValidationError() {
    if (!this.passwordFieldsUsed()) return "";
    if (!this.currentAccessPassword || !this.newAccessPassword || !this.confirmedAccessPassword)
      return "Complete all password fields.";
    return this.newAccessPassword === this.confirmedAccessPassword ? "" : "New passwords do not match.";
  }
  private async changePassword() {
    this.settingsSaving = true;
    this.settingsError = "";
    try {
      const response = await fetch("/api/access/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: this.currentAccessPassword, new_password: this.newAccessPassword }),
      });
      if (!response.ok) {
        this.settingsError = response.status === 401
          ? "Current password was not accepted." : "Could not change password.";
        return false;
      }
      this.clearSettingsPassword();
      return true;
    } catch {
      this.settingsError = "Could not change password.";
      return false;
    } finally {
      this.settingsSaving = false;
    }
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
    this.removeTabFromSource(sourceCopy, tabId);
    if (!sourceCopy.tabs.length) windows = windows.filter((item) => item.id !== sourceWindowId);
    const target = targetWindowId ? windows.find((item) => item.id === targetWindowId) : undefined;
    if (target) this.insertTab(target, tab, beforeTabId);
    else windows.push(this.detachedWindow(source, tab, x, y));
    this.windows = windows;
    void this.saveWorkspace();
    if (!sourceCopy.tabs.length)
      this.persistence = this.persistence.then(() => this.client.deleteWindow(sourceWindowId)).catch(() => undefined);
    this.updateComplete.then(() => {
      this.fitTerminal(tabId);
      this.sessions.get(tabId)?.terminal.focus();
    });
  }
  private removeTabFromSource(source: WindowState, tabId: string) {
    source.tabs = source.tabs.filter((item) => item.id !== tabId)
      .map((item, position) => ({ ...item, position }));
    if (!source.tabs.length) return;
    const active = source.active_tab_id === tabId
      ? source.tabs[0] : source.tabs.find((item) => item.id === source.active_tab_id)!;
    source.active_tab_id = active.id;
    source.title = active.title;
  }
  private insertTab(target: WindowState, tab: TabState, beforeTabId?: string) {
    const requested = beforeTabId ? target.tabs.findIndex((item) => item.id === beforeTabId) : -1;
    target.tabs.splice(requested >= 0 ? requested : target.tabs.length, 0, tab);
    target.tabs = target.tabs.map((item, position) => ({ ...item, position }));
    target.active_tab_id = tab.id;
    target.title = tab.title;
    target.z = ++this.topZ;
  }
  private detachedWindow(source: WindowState, tab: TabState, x: number, y: number): WindowState {
    return { id: crypto.randomUUID(), title: tab.title, x: Math.max(0, x - 90),
      y: Math.max(0, y - 10), width: source.width, height: source.height,
      z: ++this.topZ, minimized: false, maximized: false,
      active_tab_id: tab.id, tabs: [{ ...tab, position: 0 }] };
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
  render() {
    return renderDesktop(this as unknown as DesktopView);
  }
}
