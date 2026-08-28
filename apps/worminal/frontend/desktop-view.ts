import { html, nothing, type TemplateResult } from "lit";

import type { Shortcut, WindowState } from "./types.js";

export interface DesktopView {
  windows: WindowState[];
  clock: string;
  settingsOpen: boolean;
  currentAccessPassword: string;
  newAccessPassword: string;
  confirmedAccessPassword: string;
  settingsError: string;
  settingsSaving: boolean;
  topZ: number;
  spawn(): unknown;
  openSettings(): void;
  focusWindow(id: string): void;
  closeSettings(): void;
  saveSettings(): unknown;
  newShellShortcut(): Shortcut;
  shortcutLabel(shortcut: Shortcut): string;
  captureShortcut(event: KeyboardEvent): void;
  windowPointerDown(event: PointerEvent, id: string): void;
  titlePointerDown(event: PointerEvent, id: string): void;
  toggleMaximize(id: string): void;
  dragTab(event: PointerEvent, windowId: string, tabId: string): void;
  closeTab(windowId: string, tabId: string): void;
  newTab(windowId: string): unknown;
  toggleMinimize(id: string): void;
  close(id: string): void;
}

function renderWindow(view: DesktopView, window: WindowState): TemplateResult | typeof nothing {
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
      class="window ${window.z === view.topZ ? "active" : ""} ${window.maximized ? "maximized" : ""}"
      style=${style}
      @pointerdown=${(event: PointerEvent) => view.windowPointerDown(event, window.id)}
      aria-label=${window.title}
    >
      <header
        class="titlebar"
        data-tab-drop-window=${window.id}
        @pointerdown=${(event: PointerEvent) => view.titlePointerDown(event, window.id)}
        @dblclick=${() => view.toggleMaximize(window.id)}
      >
        <div class="tabs">
          ${window.tabs.map(
            (tab) =>
              html`<div
                class="tab ${tab.id === window.active_tab_id ? "active" : ""}"
                data-tab=${tab.id}
                @pointerdown=${(event: PointerEvent) => view.dragTab(event, window.id, tab.id)}
                @dblclick=${(event: Event) => event.stopPropagation()}
              >
                <span>▣</span><span class="tab-title">${tab.title}</span
                ><span class="phase">${tab.phase === "ready" ? "" : tab.phase.toUpperCase()}</span
                ><button
                  class="tab-close"
                  aria-label="Close tab ${tab.title}"
                  @click=${() => view.closeTab(window.id, tab.id)}
                >
                  ×
                </button>
              </div>`,
          )}
        </div>
        <button class="new-tab" aria-label=${`New tab in ${window.title}`} @click=${() => view.newTab(window.id)}>
          +
        </button>
        <div class="controls">
          <button aria-label="Minimize ${window.title}" @click=${() => view.toggleMinimize(window.id)}>_</button
          ><button aria-label="Maximize ${window.title}" @click=${() => view.toggleMaximize(window.id)}>□</button
          ><button aria-label="Close ${window.title}" @click=${() => view.close(window.id)}>×</button>
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


export function renderDesktop(view: DesktopView) {
    const tabs = view.windows.flatMap((item) => item.tabs);
    const ready = tabs.filter((tab) => tab.phase === "ready").length;
    return html`<x-console-shell
        ><x-utility-rail slot="header"
          ><span class="brand">WORMINAL</span><x-command-button @click=${view.spawn}>+ NEW SHELL</x-command-button
          ><span class="push optional"
            >LOCALHOST WORKSPACE · ${view.windows.length} WINDOW${view.windows.length === 1 ? "" : "S"}</span
          ><x-command-button aria-label="Settings" @click=${view.openSettings}
            >SETTINGS</x-command-button
          ></x-utility-rail
        >
        <main class="desktop" aria-label="Worminal desktop">
          ${view.windows.length
            ? nothing
            : html`<div class="welcome">
                <strong>NO OPEN SHELLS</strong><span>Use NEW SHELL to start a local terminal.</span>
              </div>`}${view.windows.map((window) => renderWindow(view, window))}
        </main>
        <x-status-rail slot="footer"
          ><x-status-indicator
            .label=${`${ready} SHELL${ready === 1 ? "" : "S"} CONNECTED`}
            tone=${ready ? "green" : "orange"}
          ></x-status-indicator>
          <nav class="taskbar" aria-label="Open shells">
            ${view.windows.map(
              (window) =>
                html`<x-command-button
                  class="task ${window.z === view.topZ && !window.minimized ? "active" : ""}"
                  @click=${() => view.focusWindow(window.id)}
                  >${window.title}${window.tabs.length > 1 ? ` (${window.tabs.length})` : ""}</x-command-button
                >`,
            )}
          </nav>
          <span class="push">LOCAL PTY · ${view.clock}</span></x-status-rail
        ></x-console-shell
      >
      ${view.settingsOpen
        ? html`<div class="settings" role="presentation" @click=${view.closeSettings}>
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
                  .value=${view.shortcutLabel(view.newShellShortcut())}
                  @keydown=${view.captureShortcut}
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
                    .value=${view.currentAccessPassword}
                    @input=${(event: InputEvent) =>
                      (view.currentAccessPassword = (event.target as HTMLInputElement).value)} /></label
                ><label
                  ><span>New password</span
                  ><input
                    aria-label="New access password"
                    type="password"
                    autocomplete="new-password"
                    .value=${view.newAccessPassword}
                    @input=${(event: InputEvent) =>
                      (view.newAccessPassword = (event.target as HTMLInputElement).value)} /></label
                ><label
                  ><span>Confirm password</span
                  ><input
                    aria-label="Confirm new access password"
                    type="password"
                    autocomplete="new-password"
                    .value=${view.confirmedAccessPassword}
                    @input=${(event: InputEvent) =>
                      (view.confirmedAccessPassword = (event.target as HTMLInputElement).value)}
                /></label>
                <div class="settings-error" role="alert">${view.settingsError}</div>
              </div>
              <div class="settings-actions">
                <x-command-button ?disabled=${view.settingsSaving} @click=${view.closeSettings}>CANCEL</x-command-button
                ><x-command-button ?disabled=${view.settingsSaving} @click=${view.saveSettings}
                  >${view.settingsSaving ? "SAVING…" : "SAVE"}</x-command-button
                >
              </div>
            </section>
          </div>`
        : nothing}`;
  }
