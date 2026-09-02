export type Operator = "add" | "subtract" | "multiply" | "divide";

export interface CalculatorState {
  display: string;
  accumulator: number | null;
  pending: Operator | null;
  replaceDisplay: boolean;
  error: boolean;
}

export const initialState = (): CalculatorState => ({
  display: "0", accumulator: null, pending: null, replaceDisplay: false, error: false,
});

const maximumDigits = 12;

function formatted(value: number): string | null {
  if (!Number.isFinite(value)) return null;
  const direct = String(Number(value.toPrecision(maximumDigits)));
  return direct.length <= 16 ? direct : value.toExponential(9).replace(/\.0+(?=e)/, "");
}

function evaluate(left: number, right: number, operator: Operator): number | null {
  const operations: Record<Operator, () => number> = {
    add: () => left + right,
    subtract: () => left - right,
    multiply: () => left * right,
    divide: () => right === 0 ? Number.NaN : left / right,
  };
  const result = operations[operator]();
  return Number.isFinite(result) ? result : null;
}

function failed(): CalculatorState {
  return { display: "Error", accumulator: null, pending: null, replaceDisplay: true, error: true };
}

export function enterDigit(state: CalculatorState, digit: string): CalculatorState {
  if (!/^\d$/.test(digit)) return state;
  if (state.error) return { ...initialState(), display: digit };
  if (state.replaceDisplay) return { ...state, display: digit, replaceDisplay: false };
  const digits = state.display.replace(/[-.]/g, "").length;
  if (digits >= maximumDigits) return state;
  return { ...state, display: state.display === "0" ? digit : state.display + digit };
}

export function enterDecimal(state: CalculatorState): CalculatorState {
  if (state.error) return { ...initialState(), display: "0." };
  if (state.replaceDisplay) return { ...state, display: "0.", replaceDisplay: false };
  if (state.display.includes(".")) return state;
  return { ...state, display: `${state.display}.` };
}

export function chooseOperator(state: CalculatorState, operator: Operator): CalculatorState {
  if (state.error) return state;
  const current = Number(state.display);
  if (state.pending !== null && state.accumulator !== null && !state.replaceDisplay) {
    const result = evaluate(state.accumulator, current, state.pending);
    if (result === null) return failed();
    const display = formatted(result);
    if (display === null) return failed();
    return { display, accumulator: result, pending: operator, replaceDisplay: true, error: false };
  }
  return { ...state, accumulator: current, pending: operator, replaceDisplay: true };
}

export function equals(state: CalculatorState): CalculatorState {
  if (state.error || state.pending === null || state.accumulator === null || state.replaceDisplay)
    return state;
  const result = evaluate(state.accumulator, Number(state.display), state.pending);
  if (result === null) return failed();
  const display = formatted(result);
  return display === null ? failed() : {
    display, accumulator: null, pending: null, replaceDisplay: true, error: false,
  };
}

export function toggleSign(state: CalculatorState): CalculatorState {
  if (state.error || state.display === "0") return state;
  return { ...state, display: state.display.startsWith("-") ? state.display.slice(1) : `-${state.display}` };
}

export function percent(state: CalculatorState): CalculatorState {
  if (state.error) return state;
  const display = formatted(Number(state.display) / 100);
  return display === null ? failed() : { ...state, display };
}
