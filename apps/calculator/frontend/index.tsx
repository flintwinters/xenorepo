import { Component, render } from "preact";
import { CommandButton, ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import {
  backspace, chooseOperator, equals, initialState, inputDecimal, inputDigit, percent, toggleSign,
  type BinaryOperator, type CalculatorState,
} from "./model.js";
import "./styles.css";

const operators = new Set<BinaryOperator>(["+", "−", "×", "÷"]);
const storageKey = "calc98-state-v1";
type CalculationMode = "standard" | "scientific";
interface AppState { calculator: CalculatorState; mode: CalculationMode; ledger: string[]; }

function restoredState(): AppState {
  const fallback = { calculator: initialState(), mode: "standard" as const, ledger: [] };
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null") as Partial<AppState> | null;
    if (!saved || typeof saved.calculator?.display !== "string" || !Array.isArray(saved.ledger)) return fallback;
    return {
      calculator: saved.calculator,
      mode: saved.mode === "scientific" ? "scientific" : "standard",
      ledger: saved.ledger.filter((entry): entry is string => typeof entry === "string").slice(0, 20),
    };
  } catch {
    localStorage.removeItem(storageKey);
    return fallback;
  }
}

class Calculator extends Component<Record<string, never>, AppState> {
  override state = restoredState();

  override componentDidMount(): void { window.addEventListener("keydown", this.onKeydown); }
  override componentWillUnmount(): void { window.removeEventListener("keydown", this.onKeydown); }

  private commit(next: AppState): void {
    this.setState(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  }

  private nextState(label: string): CalculatorState {
    const state = this.state.calculator;
    if (/^\d$/.test(label)) return inputDigit(state, label);
    if (operators.has(label as BinaryOperator)) return chooseOperator(state, label as BinaryOperator);
    const actions: Record<string, () => CalculatorState> = {
      ".": () => inputDecimal(state), "=": () => equals(state), "±": () => toggleSign(state),
      "%": () => percent(state), "⌫": () => backspace(state), C: initialState,
    };
    return actions[label]?.() ?? state;
  }

  private apply = (label: string): void => {
    const calculator = this.nextState(label);
    let ledger = this.state.ledger;
    if (label === "=" && calculator !== this.state.calculator && !calculator.error)
      ledger = [`${calculator.expression} ${calculator.display}`, ...ledger].slice(0, 20);
    this.commit({ ...this.state, calculator, ledger });
  };

  private scientific = (action: string): void => {
    const value = Number(this.state.calculator.display);
    const operations: Record<string, () => number> = {
      sin: () => Math.sin(value), cos: () => Math.cos(value), tan: () => Math.tan(value),
      ln: () => Math.log(value), log: () => Math.log10(value), square: () => value ** 2, pi: () => Math.PI,
    };
    const operation = operations[action];
    if (!operation) return;
    const result = operation();
    const display = Number.isFinite(result) ? String(Number.parseFloat(result.toPrecision(12))) : "Error";
    const calculator = { ...initialState(), display, replaceDisplay: true, error: display === "Error",
      expression: `${action}(${this.state.calculator.display}) =` };
    const ledger = calculator.error ? this.state.ledger
      : [`${calculator.expression} ${display}`, ...this.state.ledger].slice(0, 20);
    this.commit({ ...this.state, calculator, ledger });
  };

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

  private key(label: string, className = "") {
    const spoken: Record<string, string> = {
      "÷": "Divide", "×": "Multiply", "−": "Subtract", "+": "Add", "=": "Equals",
      "±": "Change sign", "%": "Percent", "⌫": "Backspace", C: "Clear",
    };
    return <CommandButton class={`calc-key ${className}`} aria-label={spoken[label] ?? label}
      pressed={this.state.calculator.operator === label && this.state.calculator.replaceDisplay}
      onClick={() => this.apply(label)}>{label}</CommandButton>;
  }

  override render() {
    const { calculator, mode, ledger } = this.state;
    const header = <UtilityRail><span class="brand">CALCULATOR</span>
      <span class="context">ARITHMETIC / DESK</span><span class="mode">READY</span></UtilityRail>;
    const footer = <StatusRail class="status"><span>4-FUNCTION</span>
      <span class="hint">KEYBOARD ENABLED · ESC CLEAR</span></StatusRail>;
    return <ConsoleShell class="calculator-shell" header={header} footer={footer}>
      <section class="workspace">
        <ConsolePane class="calculator-pane display-pane" title="CALCULATION" tone="green">
          <div class="calculator"><div class="readout" aria-live="polite">
            <div class="expression">{calculator.expression || "\u00a0"}</div>
            <output class={calculator.error ? "error" : ""} aria-label="Display">{calculator.display}</output>
          </div></div>
        </ConsolePane>
        <ConsolePane class="calculator-pane keypad-pane" title="KEYPAD"><div class="calculator"><div class="keys">
          {this.key("C", "function")}{this.key("±", "function")}{this.key("%", "function")}{this.key("÷", "operator")}
          {this.key("7")}{this.key("8")}{this.key("9")}{this.key("×", "operator")}
          {this.key("4")}{this.key("5")}{this.key("6")}{this.key("−", "operator")}
          {this.key("1")}{this.key("2")}{this.key("3")}{this.key("+", "operator")}
          {this.key("0", "zero")}{this.key(".")}{this.key("=", "equals")}
        </div></div></ConsolePane>
        <section class="side">
          <ConsolePane title="MODES" tone="orange"><div class="tabs" role="tablist" aria-label="Calculation mode">
            {(["standard", "scientific"] as const).map((item) => <button role="tab"
              aria-selected={mode === item} data-mode={item}
              onClick={() => this.commit({ ...this.state, mode: item })}>{item.toUpperCase()}</button>)}
          </div>{mode === "scientific" && <div class="scientific-keys">
            {["sin", "cos", "tan", "ln", "log", "square", "pi"].map((action) =>
              <CommandButton class="calc-key scientific" aria-label={action}
                onClick={() => this.scientific(action)}>{action}</CommandButton>)}
          </div>}</ConsolePane>
          <ConsolePane title="HISTORY" tone="purple"><ol class="history">
            {ledger.map((entry) => <li>{entry}</li>)}
          </ol></ConsolePane>
        </section>
      </section>
    </ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<Calculator />, root); }
