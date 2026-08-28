import { LitElement, css, html } from "lit";
import "@xenorepo/lit-ui";
import {
  backspace,
  chooseOperator,
  equals,
  initialState,
  inputDecimal,
  inputDigit,
  percent,
  toggleSign,
  type BinaryOperator,
  type CalculatorState,
} from "./model.js";

const operators = new Set<BinaryOperator>(["+", "−", "×", "÷"]);
const storageKey = "calc98-state-v1";
type CalculationMode = "standard" | "scientific";
interface SavedState {
  state: CalculatorState;
  mode: CalculationMode;
  ledger: string[];
}

class CalculatorApp extends LitElement {
  static properties = { state: { attribute: false }, mode: { type: String }, ledger: { attribute: false } };
  declare state: CalculatorState;
  declare mode: CalculationMode;
  declare ledger: string[];

  constructor() {
    super();
    this.state = initialState();
    this.mode = "standard";
    this.ledger = [];
  }

  connectedCallback(): void {
    super.connectedCallback();
    this.restore();
    window.addEventListener("keydown", this.onKeydown);
  }

  disconnectedCallback(): void {
    window.removeEventListener("keydown", this.onKeydown);
    super.disconnectedCallback();
  }

  private apply(label: string): void {
    const prior = this.state;
    this.state = this.nextState(label);
    if (label === "=" && this.state !== prior && !this.state.error) {
      this.ledger = [...this.ledger];
      this.ledger.unshift(`${this.state.expression} ${this.state.display}`);
      this.ledger = this.ledger.slice(0, 20);
    }
    this.persist();
  }

  private nextState(label: string): CalculatorState {
    if (/^\d$/.test(label)) return inputDigit(this.state, label);
    if (operators.has(label as BinaryOperator)) return chooseOperator(this.state, label as BinaryOperator);
    const actions: Record<string, () => CalculatorState> = {
      ".": () => inputDecimal(this.state),
      "=": () => equals(this.state),
      "±": () => toggleSign(this.state),
      "%": () => percent(this.state),
      "⌫": () => backspace(this.state),
      C: initialState,
    };
    return actions[label]?.() ?? this.state;
  }

  private scientific(action: string): void {
    const value = Number(this.state.display);
    const operations: Record<string, () => number> = {
      sin: () => Math.sin(value),
      cos: () => Math.cos(value),
      tan: () => Math.tan(value),
      ln: () => Math.log(value),
      log: () => Math.log10(value),
      square: () => value ** 2,
      pi: () => Math.PI,
    };
    const result = operations[action]();
    const display = Number.isFinite(result) ? String(Number.parseFloat(result.toPrecision(12))) : "Error";
    this.state = {
      ...initialState(),
      display,
      replaceDisplay: true,
      error: display === "Error",
      expression: `${action}(${this.state.display}) =`,
    };
    if (!this.state.error) {
      this.ledger = [...this.ledger];
      this.ledger.unshift(`${this.state.expression} ${display}`);
      this.ledger = this.ledger.slice(0, 20);
    }
    this.persist();
  }

  private persist(): void {
    localStorage.setItem(storageKey, JSON.stringify({ state: this.state, mode: this.mode, ledger: this.ledger }));
  }

  private restore(): void {
    try {
      const state = JSON.parse(localStorage.getItem(storageKey) ?? "null") as SavedState | null;
      if (!state || typeof state.state?.display !== "string" || !Array.isArray(state.ledger)) return;
      const mode = state.mode ?? "standard";
      this.state = state.state;
      this.mode = mode;
      this.ledger = state.ledger.filter((entry): entry is string => typeof entry === "string").slice(0, 20);
    } catch {
      localStorage.removeItem(storageKey);
    }
  }

  private onKeydown = (event: KeyboardEvent): void => {
    const mapped: Record<string, string> = {
      Enter: "=",
      "=": "=",
      Escape: "C",
      Backspace: "⌫",
      "/": "÷",
      "*": "×",
      "-": "−",
    };
    const action = mapped[event.key] ?? event.key;
    if (!/^\d$/.test(action) && !operators.has(action as BinaryOperator) && ![".", "=", "%", "⌫", "C"].includes(action))
      return;
    event.preventDefault();
    this.apply(action);
  };

  private key(label: string, className = ""): unknown {
    const spoken: Record<string, string> = {
      "÷": "Divide",
      "×": "Multiply",
      "−": "Subtract",
      "+": "Add",
      "=": "Equals",
      "±": "Change sign",
      "%": "Percent",
      "⌫": "Backspace",
      C: "Clear",
    };
    return html`<x-command-button
      class="calc-key ${className}"
      label=${spoken[label] ?? label}
      ?pressed=${this.state.operator === label && this.state.replaceDisplay}
      @click=${() => this.apply(label)}
      >${label}</x-command-button
    >`;
  }

  static styles = css`
    :host {
      display: block;
      height: 100%;
      color: #ebdbb2;
      font:
        12px/1.35 "Courier New",
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
      letter-spacing: 0.08em;
    }
    .context,
    .hint {
      color: #a89984;
    }
    .mode {
      margin-left: auto;
      color: #8ec07c;
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(180px, 260px);
      grid-template-rows: auto minmax(0, 1fr);
      place-content: center;
      min-height: 0;
      padding: clamp(14px, 4vw, 48px);
      gap: 1px;
      background: radial-gradient(circle at 50% 35%, #32302f, #1d2021 66%);
    }
    x-console-pane {
      min-height: 0;
      border: 1px solid #111;
      box-shadow: 0 14px 34px rgb(0 0 0/0.45);
    }
    .display-pane {
      grid-column: 1/3;
    }
    .keypad-pane {
      grid-column: 1;
      grid-row: 2;
    }
    .side {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-height: 0;
    }
    .calculator {
      display: grid;
      gap: 10px;
      padding: 12px;
      background: #282828;
    }
    .readout {
      display: grid;
      align-content: end;
      min-height: 112px;
      padding: 12px 14px;
      overflow: hidden;
      text-align: right;
      background: #181a1b;
      border: 1px solid #111;
      box-shadow: inset 2px 2px 7px #090a0a;
    }
    .expression {
      min-height: 22px;
      color: #a89984;
      font-size: 14px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    output {
      color: #ebdbb2;
      font-size: clamp(38px, 10vw, 58px);
      line-height: 1.05;
      letter-spacing: -0.06em;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    output.error {
      color: #fb4934;
      letter-spacing: 0;
    }
    .keys {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 7px;
    }
    .tabs {
      display: flex;
      gap: 2px;
      padding: 5px;
      background: #181a1b;
    }
    .tabs button {
      flex: 1;
      padding: 5px;
      color: #a89984;
      font: inherit;
      background: #35312f;
      border: 1px solid #928374;
    }
    .tabs button[aria-selected="true"] {
      color: #fabd2f;
      background: #1f1e1d;
      border-color: #fabd2f;
    }
    .scientific-keys {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 5px;
      padding: 7px;
    }
    .history {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .history li {
      padding: 6px;
      border-bottom: 1px solid #504945;
      overflow-wrap: anywhere;
    }
    x-command-button {
      height: 52px;
      font-size: 18px;
      --console-button-border: #a89984;
    }
    x-command-button.function {
      color: #fabd2f;
    }
    x-command-button.operator {
      color: #8ec07c;
      --console-button-border: #83a598;
    }
    x-command-button.equals {
      color: #1d2021;
      --console-fg: #1d2021;
      --console-button-border: #d5d87a;
      --console-button-background: linear-gradient(#dadd82, #a7aa20);
      --console-button-hover-background: linear-gradient(#e4e78c, #b8bb26);
      --console-button-pressed-background: linear-gradient(#77790f, #4f5009);
    }
    x-command-button.equals::part(button) {
      font-weight: bold;
    }
    x-command-button.zero {
      grid-column: span 2;
    }
    .status {
      justify-content: space-between;
    }
    @media (max-width: 520px) {
      .workspace {
        display: block;
        padding: 0;
        overflow: auto;
      }
      x-console-pane {
        width: 100%;
        border: 0;
        box-shadow: none;
      }
      .calculator {
        min-height: 100%;
        grid-template-rows: minmax(132px, 1fr) auto;
        padding: 10px;
      }
      x-command-button {
        height: clamp(54px, 12dvh, 72px);
        font-size: 21px;
      }
      .context,
      .hint {
        display: none;
      }
    }
  `;

  render() {
    return html`<x-console-shell>
      <x-utility-rail slot="header"
        ><span class="brand">CALCULATOR</span><span class="context">ARITHMETIC / DESK</span
        ><span class="mode">READY</span></x-utility-rail
      >
      <section class="workspace">
        <x-console-pane class="display-pane" title="CALCULATION" tone="green">
          <div class="calculator">
            <div class="readout" aria-live="polite">
              <div class="expression">${this.state.expression || "\u00a0"}</div>
              <output class=${this.state.error ? "error" : ""} aria-label="Display">${this.state.display}</output>
            </div>
          </div>
        </x-console-pane>
        <x-console-pane class="keypad-pane" title="KEYPAD" tone="blue">
          <div class="calculator">
            <div class="keys">
              ${this.key("C", "function")}${this.key("±", "function")}${this.key("%", "function")}${this.key(
                "÷",
                "operator",
              )}
              ${this.key("7")}${this.key("8")}${this.key("9")}${this.key("×", "operator")}
              ${this.key("4")}${this.key("5")}${this.key("6")}${this.key("−", "operator")}
              ${this.key("1")}${this.key("2")}${this.key("3")}${this.key("+", "operator")}
              ${this.key("0", "zero")}${this.key(".")}${this.key("=", "equals")}
            </div>
          </div>
        </x-console-pane>
        <section class="side">
          <x-console-pane title="MODES" tone="orange">
            <div class="tabs" role="tablist" aria-label="Calculation mode">
              <button
                role="tab"
                aria-selected=${this.mode === "standard"}
                data-mode="standard"
                @click=${() => {
                  this.mode = "standard";
                  this.persist();
                }}
              >
                STANDARD
              </button>
              <button
                role="tab"
                aria-selected=${this.mode === "scientific"}
                @click=${() => {
                  this.mode = "scientific";
                  this.persist();
                }}
                data-mode="scientific"
              >
                SCIENTIFIC
              </button>
            </div>
            ${this.mode === "scientific"
              ? html`<div class="scientific-keys">
                  ${["sin", "cos", "tan", "ln", "log", "square", "pi"].map(
                    (action) =>
                      html` <x-command-button
                        class="calc-key scientific"
                        label=${action}
                        @click=${() => this.scientific(action)}
                        >${action}</x-command-button
                      >`,
                  )}
                </div>`
              : ""}
          </x-console-pane>
          <x-console-pane title="HISTORY" tone="purple">
            <ol class="history">
              ${this.ledger.map((entry) => html`<li>${entry}</li>`)}
            </ol>
          </x-console-pane>
        </section>
      </section>
      <x-status-rail slot="footer" class="status"
        ><span>4-FUNCTION</span><span class="hint">KEYBOARD ENABLED · ESC CLEAR</span></x-status-rail
      >
    </x-console-shell>`;
  }
}

if (!customElements.get("x-calculator-app")) customElements.define("x-calculator-app", CalculatorApp);

export function mount(root: HTMLElement): void {
  root.replaceChildren(document.createElement("x-calculator-app"));
}
