import { LitElement, css, html } from "lit";
import "../../../packages/lit-ui/src/index.js";
import {
  backspace, chooseOperator, equals, initialState, inputDecimal, inputDigit, percent,
  toggleSign, type BinaryOperator, type CalculatorState,
} from "./model.js";

const operators = new Set<BinaryOperator>(["+", "−", "×", "÷"]);

class CalculatorApp extends LitElement {
  static properties = { state: { attribute: false } };
  declare state: CalculatorState;

  constructor() {
    super();
    this.state = initialState();
  }

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("keydown", this.onKeydown);
  }

  disconnectedCallback(): void {
    window.removeEventListener("keydown", this.onKeydown);
    super.disconnectedCallback();
  }

  private apply(label: string): void {
    if (/^\d$/.test(label)) this.state = inputDigit(this.state, label);
    else if (operators.has(label as BinaryOperator)) this.state = chooseOperator(this.state, label as BinaryOperator);
    else if (label === ".") this.state = inputDecimal(this.state);
    else if (label === "=") this.state = equals(this.state);
    else if (label === "±") this.state = toggleSign(this.state);
    else if (label === "%") this.state = percent(this.state);
    else if (label === "⌫") this.state = backspace(this.state);
    else if (label === "C") this.state = initialState();
  }

  private onKeydown = (event: KeyboardEvent): void => {
    const mapped: Record<string, string> = {
      Enter: "=", "=": "=", Escape: "C", Backspace: "⌫", "/": "÷", "*": "×", "-": "−",
    };
    const action = mapped[event.key] ?? event.key;
    if (!/^\d$/.test(action) && !operators.has(action as BinaryOperator)
      && ![".", "=", "%", "⌫", "C"].includes(action)) return;
    event.preventDefault();
    this.apply(action);
  };

  private key(label: string, className = ""): unknown {
    const spoken: Record<string, string> = {
      "÷": "Divide", "×": "Multiply", "−": "Subtract", "+": "Add", "=": "Equals",
      "±": "Change sign", "%": "Percent", "⌫": "Backspace", "C": "Clear",
    };
    return html`<x-command-button class=${className} label=${spoken[label] ?? label}
      ?pressed=${this.state.operator === label && this.state.replaceDisplay}
      @click=${() => this.apply(label)}>${label}</x-command-button>`;
  }

  static styles = css`
    :host { display:block; height:100%; color:#ebdbb2; font:12px/1.35 "Courier New",monospace; background:#1d2021; }
    * { box-sizing:border-box; }
    x-console-shell { height:100%; }
    .brand { color:#fabd2f; font-weight:bold; letter-spacing:.08em; }
    .context,.hint { color:#a89984; }
    .mode { margin-left:auto; color:#8ec07c; }
    .workspace { display:grid; place-items:center; min-height:0; padding:clamp(14px,4vw,48px); background:radial-gradient(circle at 50% 35%,#32302f,#1d2021 66%); }
    x-console-pane { width:min(420px,100%); min-height:0; border:1px solid #111; box-shadow:0 14px 34px rgb(0 0 0/.45); }
    .calculator { display:grid; gap:10px; padding:12px; background:#282828; }
    .readout { display:grid; align-content:end; min-height:112px; padding:12px 14px; overflow:hidden; text-align:right; background:#181a1b; border:1px solid #111; box-shadow:inset 2px 2px 7px #090a0a; }
    .expression { min-height:22px; color:#a89984; font-size:14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    output { color:#ebdbb2; font-size:clamp(38px,10vw,58px); line-height:1.05; letter-spacing:-.06em; overflow:hidden; text-overflow:ellipsis; }
    output.error { color:#fb4934; letter-spacing:0; }
    .keys { display:grid; grid-template-columns:repeat(4,1fr); gap:7px; }
    x-command-button { height:52px; font-size:18px; --console-button-border:#504945; }
    x-command-button.function { color:#fabd2f; }
    x-command-button.operator { color:#8ec07c; --console-button-border:#5f7f75; }
    x-command-button.equals { color:#1d2021; --console-fg:#1d2021; --console-button-border:#d5d87a; }
    x-command-button.equals::part(button) { font-weight:bold; background:linear-gradient(#d5d87a,#98971a); }
    x-command-button.zero { grid-column:span 2; }
    .status { justify-content:space-between; }
    @media(max-width:520px) {
      .workspace { place-items:stretch; padding:0; }
      x-console-pane { width:100%; height:100%; border:0; }
      .calculator { min-height:100%; grid-template-rows:minmax(132px,1fr) auto; padding:10px; }
      x-command-button { height:clamp(54px,12dvh,72px); font-size:21px; }
      .context,.hint { display:none; }
    }
  `;

  render() {
    return html`<x-console-shell>
      <x-utility-rail slot="header"><span class="brand">CALCULATOR</span><span class="context">ARITHMETIC / DESK</span><span class="mode">READY</span></x-utility-rail>
      <section class="workspace">
        <x-console-pane title="CALCULATION" index="01" tone="green">
          <div class="calculator">
            <div class="readout" aria-live="polite">
              <div class="expression">${this.state.expression || "\u00a0"}</div>
              <output class=${this.state.error ? "error" : ""} aria-label="Display">${this.state.display}</output>
            </div>
            <div class="keys">
              ${this.key("C", "function")}${this.key("±", "function")}${this.key("%", "function")}${this.key("÷", "operator")}
              ${this.key("7")}${this.key("8")}${this.key("9")}${this.key("×", "operator")}
              ${this.key("4")}${this.key("5")}${this.key("6")}${this.key("−", "operator")}
              ${this.key("1")}${this.key("2")}${this.key("3")}${this.key("+", "operator")}
              ${this.key("0", "zero")}${this.key(".")}${this.key("=", "equals")}
            </div>
          </div>
        </x-console-pane>
      </section>
      <x-status-rail slot="footer" class="status"><span>4-FUNCTION</span><span class="hint">KEYBOARD ENABLED · ESC CLEAR</span></x-status-rail>
    </x-console-shell>`;
  }
}

if (!customElements.get("x-calculator-app")) customElements.define("x-calculator-app", CalculatorApp);

export function mount(root: HTMLElement): void {
  root.replaceChildren(document.createElement("x-calculator-app"));
}
