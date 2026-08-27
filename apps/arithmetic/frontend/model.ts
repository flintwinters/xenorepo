export type BinaryOperator = "+" | "−" | "×" | "÷";

export interface CalculatorState {
  display: string;
  accumulator: number | null;
  operator: BinaryOperator | null;
  replaceDisplay: boolean;
  expression: string;
  error: boolean;
}

export const initialState = (): CalculatorState => ({
  display: "0",
  accumulator: null,
  operator: null,
  replaceDisplay: false,
  expression: "",
  error: false,
});

const formatted = (value: number): string => {
  if (!Number.isFinite(value)) return "Error";
  const rounded = Number.parseFloat(value.toPrecision(12));
  return String(Object.is(rounded, -0) ? 0 : rounded);
};

const calculate = (left: number, operator: BinaryOperator, right: number): number => {
  if (operator === "+") return left + right;
  if (operator === "−") return left - right;
  if (operator === "×") return left * right;
  return right === 0 ? Number.NaN : left / right;
};

export const inputDigit = (state: CalculatorState, digit: string): CalculatorState => {
  const reset = state.error ? initialState() : state;
  if (reset.replaceDisplay) return { ...reset, display: digit, replaceDisplay: false };
  if (reset.display === "0") return { ...reset, display: digit };
  if (reset.display === "-0") return { ...reset, display: `-${digit}` };
  if (reset.display.replace("-", "").replace(".", "").length >= 12) return reset;
  return { ...reset, display: reset.display + digit };
};

export const inputDecimal = (state: CalculatorState): CalculatorState => {
  const reset = state.error ? initialState() : state;
  if (reset.replaceDisplay) return { ...reset, display: "0.", replaceDisplay: false };
  return reset.display.includes(".") ? reset : { ...reset, display: `${reset.display}.` };
};

export const chooseOperator = (state: CalculatorState, next: BinaryOperator): CalculatorState => {
  if (state.error) return state;
  const current = Number(state.display);
  if (state.operator && state.replaceDisplay) {
    return { ...state, operator: next, expression: `${formatted(state.accumulator ?? current)} ${next}` };
  }
  const result = state.accumulator !== null && state.operator
    ? calculate(state.accumulator, state.operator, current)
    : current;
  const display = formatted(result);
  if (display === "Error") return { ...initialState(), display, error: true, replaceDisplay: true };
  return { display, accumulator: result, operator: next, replaceDisplay: true,
    expression: `${display} ${next}`, error: false };
};

export const equals = (state: CalculatorState): CalculatorState => {
  if (state.error || state.accumulator === null || state.operator === null) return state;
  const right = Number(state.display);
  const result = formatted(calculate(state.accumulator, state.operator, right));
  if (result === "Error") return { ...initialState(), display: result, error: true, replaceDisplay: true };
  return { display: result, accumulator: null, operator: null, replaceDisplay: true,
    expression: `${formatted(state.accumulator)} ${state.operator} ${formatted(right)} =`, error: false };
};

export const toggleSign = (state: CalculatorState): CalculatorState => {
  if (state.error || state.display === "0") return state;
  return { ...state, display: state.display.startsWith("-") ? state.display.slice(1) : `-${state.display}` };
};

export const percent = (state: CalculatorState): CalculatorState => {
  if (state.error) return state;
  return { ...state, display: formatted(Number(state.display) / 100) };
};

export const backspace = (state: CalculatorState): CalculatorState => {
  if (state.error || state.replaceDisplay) return state;
  const shortened = state.display.slice(0, -1);
  return { ...state, display: shortened === "" || shortened === "-" ? "0" : shortened };
};
