import { LitElement, css, html, nothing, type CSSResultGroup } from "lit";
import { consoleTokens, chrome } from "./styles.js";

export { consoleControls, consoleTable } from "./styles.js";

type ConsoleTone = "blue" | "green" | "orange" | "purple" | "neutral";

const tone = (value: ConsoleTone) =>
  ({
    blue: ["#83a598", "#5f7f75", "#b7cfca", "#354a44"],
    green: ["#b8bb26", "#98971a", "#d5d87a", "#57580e"],
    orange: ["#fe8019", "#d65d0e", "#ffaf66", "#7a3307"],
    purple: ["#d3869b", "#b16286", "#edb8c5", "#65364c"],
    neutral: ["#665c54", "#3c3836", "#928374", "#282828"],
  })[value];

class ConsoleElement extends LitElement {
  static styles: CSSResultGroup = consoleTokens;
}

class ConsoleShell extends ConsoleElement {
  static styles = [
    consoleTokens,
    css`
      :host {
        display: grid;
        min-height: 100%;
        grid-template-rows: auto minmax(0, 1fr) auto;
        background: var(--console-bg, #1d2021);
      }
      main {
        display: grid;
        min-height: 0;
        overflow: auto;
        background: var(--console-panel, #282828);
      }
    `,
  ];
  render() {
    return html`<header><slot name="header"></slot></header>
      <main><slot></slot></main>
      <footer><slot name="footer"></slot></footer>`;
  }
}
customElements.define("x-console-shell", ConsoleShell);

class UtilityRail extends ConsoleElement {
  static styles = [
    consoleTokens,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        padding: 1px 6px;
        background: linear-gradient(#3c3836, #282828);
        border-bottom: 1px solid #101112;
        overflow: hidden;
        white-space: nowrap;
      }
    `,
  ];
  render() {
    return html`<slot></slot>`;
  }
}
customElements.define("x-utility-rail", UtilityRail);

class StatusRail extends UtilityRail {}
customElements.define("x-status-rail", StatusRail);

class ConsolePane extends ConsoleElement {
  static properties = { title: { type: String }, tone: { type: String } };
  declare title: string;
  declare tone: ConsoleTone;
  constructor() {
    super();
    this.title = "";
    this.tone = "blue";
  }
  static styles = [
    consoleTokens,
    chrome,
    css`
      :host {
        display: grid;
        min-height: 0;
        grid-template-rows: auto minmax(0, 1fr);
        overflow: hidden;
        background: var(--console-panel, #282828);
      }
      slot[name="title-end"] {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-left: auto;
      }
      .body {
        min-height: 0;
        overflow: auto;
      }
    `,
  ];
  render() {
    const [light, dark, rim, shadow] = tone(this.tone);
    const style = [
      `--console-tone-light:${light}`,
      `--console-tone-dark:${dark}`,
      `--console-tone-rim:${rim}`,
      `--console-tone-shadow:${shadow}`,
    ].join(";");
    return html`<div class="chrome" style=${style}><span>${this.title}</span><slot name="title-end"></slot></div>
      <div class="body"><slot></slot></div>`;
  }
}
customElements.define("x-console-pane", ConsolePane);

class CommandButton extends ConsoleElement {
  static properties = {
    disabled: { type: Boolean, reflect: true },
    pressed: { type: Boolean, reflect: true },
    label: { type: String },
    title: { type: String },
    appearance: { type: String, reflect: true },
  };
  declare disabled: boolean;
  declare pressed: boolean;
  declare label: string;
  declare appearance: string;
  constructor() {
    super();
    this.disabled = false;
    this.pressed = false;
    this.label = "";
    this.appearance = "default";
  }
  static styles = [
    consoleTokens,
    css`
      :host {
        display: inline-block;
      }
      button {
        width: 100%;
        min-height: 18px;
        padding: 1px 6px;
        color: var(--console-fg, #ebdbb2);
        background: var(--console-button-background, linear-gradient(#4a4643, #35312f));
        border: 1px solid var(--console-button-border, #c6b58f);
        border-radius: 4px;
        box-shadow:
          inset 0 1px rgb(255 255 255 / 0.1),
          0 1px 2px rgb(0 0 0 / 0.45);
        cursor: pointer;
      }
      button:hover:not(:disabled) {
        background: var(--console-button-hover-background, linear-gradient(#55504d, #3d3936));
        border-color: var(--console-button-border-hover, #f0dfb8);
        box-shadow:
          inset 0 1px rgb(255 255 255 / 0.14),
          0 2px 4px rgb(0 0 0 / 0.4);
      }
      button:active:not(:disabled),
      button[aria-pressed="true"]:not(:disabled) {
        transform: translateY(1px);
        background: var(--console-button-pressed-background, linear-gradient(#242220, #181716));
        box-shadow:
          inset 0 3px 4px rgb(0 0 0 / 0.65),
          inset 0 -1px rgb(255 255 255 / 0.08);
      }
      button:disabled {
        color: var(--console-muted, #a89984);
        cursor: not-allowed;
        opacity: 0.65;
      }
      :host([appearance="subtle"]) button {
        min-height: 0;
        padding: 0 2px;
        color: var(--console-muted, #a89984);
        background: transparent;
        border: 0;
        border-radius: 0;
        box-shadow: none;
        text-decoration: underline;
        text-underline-offset: 2px;
        text-shadow: 0 1px 1px rgb(0 0 0 / 0.8);
        cursor: pointer;
      }
      :host([appearance="subtle"]) button:hover:not(:disabled) {
        color: var(--console-fg, #ebdbb2);
        background: transparent;
        border: 0;
        box-shadow: none;
        text-shadow:
          0 1px 1px #000,
          0 0 3px rgb(235 219 178 / 0.25);
      }
      :host([appearance="subtle"]) button:active:not(:disabled) {
        transform: translateY(1px);
        box-shadow: none;
      }
    `,
  ];
  render() {
    return html`<button
      part="button"
      ?disabled=${this.disabled}
      aria-pressed=${this.pressed ? "true" : "false"}
      aria-label=${this.label || nothing}
      title=${this.title || nothing}
    >
      <slot></slot>
    </button>`;
  }
}
customElements.define("x-command-button", CommandButton);
