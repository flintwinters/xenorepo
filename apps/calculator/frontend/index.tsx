import { render } from "preact";
import { useState } from "preact/hooks";
import {
  CommandButton, ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail,
} from "@xenorepo/ui";
import {
  chooseOperator, enterDecimal, enterDigit, equals, initialState, percent, toggleSign,
  type CalculatorState, type Operator,
} from "./calculator.js";
import "./styles.css";

const operatorLabels: Record<Operator, string> = {
  add: "+", subtract: "−", multiply: "×", divide: "÷",
};

interface KeyDefinition {
  label: string;
  name: string;
  kind?: "operator" | "equals" | "utility";
  action: (state: CalculatorState) => CalculatorState;
}

const keys: KeyDefinition[] = [
  { label: "AC", name: "All clear", kind: "utility", action: initialState },
  { label: "+/−", name: "Change sign", kind: "utility", action: toggleSign },
  { label: "%", name: "Percent", kind: "utility", action: percent },
  { label: "÷", name: "Divide", kind: "operator", action: (state) => chooseOperator(state, "divide") },
  ...["7", "8", "9"].map((digit) => ({
    label: digit, name: digit, action: (state: CalculatorState) => enterDigit(state, digit),
  })),
  { label: "×", name: "Multiply", kind: "operator", action: (state) => chooseOperator(state, "multiply") },
  ...["4", "5", "6"].map((digit) => ({
    label: digit, name: digit, action: (state: CalculatorState) => enterDigit(state, digit),
  })),
  { label: "−", name: "Subtract", kind: "operator", action: (state) => chooseOperator(state, "subtract") },
  ...["1", "2", "3"].map((digit) => ({
    label: digit, name: digit, action: (state: CalculatorState) => enterDigit(state, digit),
  })),
  { label: "+", name: "Add", kind: "operator", action: (state) => chooseOperator(state, "add") },
  { label: "0", name: "0", action: (state) => enterDigit(state, "0") },
  { label: ".", name: "Decimal point", action: enterDecimal },
  { label: "=", name: "Equals", kind: "equals", action: equals },
];

function Application() {
  const [state, setState] = useState(initialState);
  const operation = state.pending === null ? "" : operatorLabels[state.pending];
  const header = <UtilityRail><strong>CALCULATOR</strong><span>BUTTON INPUT</span></UtilityRail>;
  const footer = <StatusRail><span>STATELESS</span><span>4-FUNCTION ARITHMETIC</span></StatusRail>;
  return <ConsoleShell class="calculator-shell" header={header} footer={footer}>
    <ConsoleWorkspace class="calculator-workspace">
      <ConsolePane class="calculator-pane" title="CALCULATION" tone="green">
        <section class="calculator" aria-label="Basic calculator">
          <div class={`display ${state.error ? "error" : ""}`} aria-live="polite" aria-atomic="true">
            <span class="operation" aria-label={operation ? `Pending operation ${operation}` : "No pending operation"}>
              {operation || "\u00a0"}
            </span>
            <output aria-label="Calculator display">{state.display}</output>
          </div>
          <div class="keypad">
            {keys.map((key) => <CommandButton type="button" class={`key ${key.kind ?? "digit"}`}
              aria-label={key.name} pressed={key.kind === "operator" && operation === key.label}
              onClick={() => setState((current) => key.action(current))}>{key.label}</CommandButton>)}
          </div>
        </section>
      </ConsolePane>
    </ConsoleWorkspace>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
