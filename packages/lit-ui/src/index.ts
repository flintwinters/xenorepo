import { LitElement, css, html, nothing } from "lit";
import { consoleTokens, chrome } from "./styles.js";

export type ConsoleTone = "blue" | "green" | "orange" | "purple" | "neutral";
export interface GridColumn { key: string; label: string; }
export interface GridRow { [key: string]: string | number | null | undefined; }
export interface FeedEvent { title: string; detail?: string; time?: string; tone?: ConsoleTone; }

const tone = (value: ConsoleTone) => ({
  blue: ["#83a598", "#5f7f75", "#b7cfca", "#354a44"],
  green: ["#b8bb26", "#98971a", "#d5d87a", "#57580e"],
  orange: ["#fe8019", "#d65d0e", "#ffaf66", "#7a3307"],
  purple: ["#d3869b", "#b16286", "#edb8c5", "#65364c"],
  neutral: ["#665c54", "#3c3836", "#928374", "#282828"],
}[value]);

/** Preserve the legacy numbered-title shorthand while favoring explicit indices. */
const paneHeading = (title: string, index: string) => {
  const numbered = /^\s*(\d{1,3})\s+(.+?)\s*$/.exec(title);
  return { index: index || numbered?.[1] || "", title: numbered?.[2] || title };
};

class ConsoleElement extends LitElement {
  static styles = consoleTokens;
}

export class ConsoleShell extends ConsoleElement {
  static styles = [consoleTokens, css`
    :host { display: grid; min-height: 100%; grid-template-rows: auto minmax(0, 1fr) auto; background: var(--console-bg, #1d2021); }
    main { display: grid; min-height: 0; overflow: auto; background: var(--console-panel, #282828); }
  `];
  render() { return html`<header><slot name="header"></slot></header><main><slot></slot></main><footer><slot name="footer"></slot></footer>`; }
}
customElements.define("x-console-shell", ConsoleShell);

export class UtilityRail extends ConsoleElement {
  static styles = [consoleTokens, css`
    :host { display: flex; align-items: center; gap: 6px; min-width: 0; padding: 1px 6px; background: linear-gradient(#3c3836, #282828); border-bottom: 1px solid #101112; overflow: hidden; white-space: nowrap; }
  `];
  render() { return html`<slot></slot>`; }
}
customElements.define("x-utility-rail", UtilityRail);

export class StatusRail extends UtilityRail {}
customElements.define("x-status-rail", StatusRail);

export class ConsolePane extends ConsoleElement {
  static properties = { title: { type: String }, index: { type: String }, tone: { type: String } };
  title = "";
  index = "";
  tone: ConsoleTone = "blue";
  static styles = [consoleTokens, chrome, css`
    :host { display: grid; min-height: 0; grid-template-rows: auto minmax(0, 1fr); overflow: hidden; background: var(--console-panel, #282828); }
    .index { align-self: stretch; display: grid; place-items: center; min-width: 21px; padding: 0 4px; color: var(--console-fg, #ebdbb2); background: var(--console-panel, #282828); border-right: 1px solid #111; }
    .body { min-height: 0; overflow: auto; }
  `];
  render() {
    const [light, dark, rim, shadow] = tone(this.tone);
    const style = `--console-tone-light:${light};--console-tone-dark:${dark};--console-tone-rim:${rim};--console-tone-shadow:${shadow}`;
    const heading = paneHeading(this.title, this.index);
    return html`<div class="chrome" style=${style}>${heading.index ? html`<span class="index">${heading.index}</span>` : nothing}<span>${heading.title}</span><slot name="title-end"></slot></div><div class="body"><slot></slot></div>`;
  }
}
customElements.define("x-console-pane", ConsolePane);

export class CommandButton extends ConsoleElement {
  static properties = { disabled: { type: Boolean, reflect: true }, pressed: { type: Boolean, reflect: true } };
  disabled = false;
  pressed = false;
  static styles = [consoleTokens, css`
    :host { display: inline-block; }
    button {
      width: 100%; min-height: 18px; padding: 1px 6px; color: var(--console-fg, #ebdbb2);
      background: linear-gradient(#45413f, #302d2b); border: 1px solid var(--console-button-border, #a89984);
      border-radius: 4px; box-shadow: inset 0 1px rgb(255 255 255 / 0.1), 0 1px 2px rgb(0 0 0 / 0.45);
      cursor: pointer;
    }
    button:hover:not(:disabled) { background: linear-gradient(#504b48, #383431); border-color: var(--console-button-border-hover, #d5c4a1); box-shadow: inset 0 1px rgb(255 255 255 / 0.14), 0 2px 4px rgb(0 0 0 / 0.4); }
    button:active:not(:disabled), button[aria-pressed="true"]:not(:disabled) { transform: translateY(1px); box-shadow: inset 0 3px 4px rgb(0 0 0 / 0.52), inset 0 -1px rgb(255 255 255 / 0.12); }
    button:disabled { color: var(--console-muted, #a89984); cursor: not-allowed; opacity: 0.65; }
  `];
  render() { return html`<button part="button" ?disabled=${this.disabled} aria-pressed=${this.pressed ? "true" : "false"}><slot></slot></button>`; }
}
customElements.define("x-command-button", CommandButton);

export class ConsoleField extends ConsoleElement {
  static properties = { label: { type: String }, value: { type: String }, type: { type: String } };
  label = ""; value = ""; type = "text";
  static styles = [consoleTokens, css`
    label { display: grid; gap: 3px; color: var(--console-muted, #a89984); } input { width: 100%; min-height: 24px; padding: 2px 6px; color: inherit; background: var(--console-well, #181a1b); border: 1px solid #111; border-right-color: var(--console-line, #504945); border-bottom-color: var(--console-line, #504945); }
  `];
  render() { return html`<label>${this.label}<input .value=${this.value} type=${this.type} @input=${(event: InputEvent) => this.value = (event.target as HTMLInputElement).value}></label>`; }
}
customElements.define("x-console-field", ConsoleField);

export class DataGrid extends ConsoleElement {
  static properties = { columns: { attribute: false }, rows: { attribute: false }, empty: { type: String } };
  columns: GridColumn[] = []; rows: GridRow[] = []; empty = "NO RECORDS";
  static styles = [consoleTokens, css`
    :host { display: block; min-height: 0; overflow: auto; } table { width: 100%; border-collapse: collapse; table-layout: fixed; } th, td { padding: 4px 7px; text-align: left; border-right: 1px solid var(--console-line, #504945); border-bottom: 1px solid var(--console-line, #504945); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } th { position: sticky; top: 0; color: var(--console-accent, #fabd2f); background: #32302f; } .empty { padding: 18px; color: var(--console-muted, #a89984); text-align: center; }
  `];
  render() { return html`<table><thead><tr>${this.columns.map((column) => html`<th scope="col">${column.label}</th>`)}</tr></thead><tbody>${this.rows.length ? this.rows.map((row) => html`<tr>${this.columns.map((column) => html`<td>${row[column.key] ?? ""}</td>`)}</tr>`) : html`<tr><td class="empty" colspan=${this.columns.length || 1}>${this.empty}</td></tr>`}</tbody></table>`; }
}
customElements.define("x-data-grid", DataGrid);

export class StatusIndicator extends ConsoleElement {
  static properties = { label: { type: String }, tone: { type: String } };
  declare label: string;
  declare tone: ConsoleTone;
  constructor() {
    super();
    this.label = "";
    this.tone = "green";
  }
  static styles = [consoleTokens, css`
    :host { display: inline-flex; align-items: center; gap: 5px; } i { width: 8px; height: 8px; border: 1px solid #0c0d0d; background: var(--indicator, #b8bb26); box-shadow: 0 0 4px var(--indicator, #b8bb26); } span { color: var(--console-muted, #a89984); }
  `];
  render() { const colors: Record<ConsoleTone, string> = { blue: "#83a598", green: "#b8bb26", orange: "#fe8019", purple: "#d3869b", neutral: "#928374" }; return html`<i style=${`--indicator:${colors[this.tone]}`}></i><span role="status">${this.label}</span>`; }
}
customElements.define("x-status-indicator", StatusIndicator);

export class EmptyState extends ConsoleElement {
  static properties = { heading: { type: String }, detail: { type: String } };
  heading = "NO RECORDS"; detail = "";
  static styles = [consoleTokens, css`
    :host { display: grid; min-height: 100px; place-content: center; gap: 4px; padding: 16px; text-align: center; color: var(--console-muted, #a89984); } strong { color: var(--console-fg, #ebdbb2); } p { margin: 0; }
  `];
  render() { return html`<strong>${this.heading}</strong>${this.detail ? html`<p>${this.detail}</p>` : nothing}`; }
}
customElements.define("x-empty-state", EmptyState);

export class EventFeed extends ConsoleElement {
  static properties = { events: { attribute: false } };
  events: FeedEvent[] = [];
  static styles = [consoleTokens, css`
    :host { display: block; } article { display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; padding: 6px; border-bottom: 1px solid var(--console-line, #504945); } strong { color: var(--console-fg, #ebdbb2); } p, time { margin: 0; color: var(--console-muted, #a89984); } time { grid-column: 2; grid-row: 1; } p { grid-column: 1 / -1; }
  `];
  render() { return html`<section role="feed" aria-label="Event feed">${this.events.map((event) => html`<article><strong>${event.title}</strong>${event.time ? html`<time>${event.time}</time>` : nothing}${event.detail ? html`<p>${event.detail}</p>` : nothing}</article>`)}</section>`; }
}
customElements.define("x-event-feed", EventFeed);
