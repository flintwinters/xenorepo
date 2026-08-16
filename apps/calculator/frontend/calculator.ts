type Operator = "+" | "−" | "×" | "÷";

const operations: Record<Operator, (left: number, right: number) => number> = {
  "+": (left, right) => left + right,
  "−": (left, right) => left - right,
  "×": (left, right) => left * right,
  "÷": (left, right) => left / right,
};

export class Calculator {
  private displayValue = "0";
  private accumulator: number | null = null;
  private pendingOperator: Operator | null = null;
  private replaceDisplay = false;

  inputDigit(digit: string): void {
    if (this.replaceDisplay || this.displayValue === "0") {
      this.displayValue = digit;
      this.replaceDisplay = false;
    } else if (this.displayValue.length < 14) {
      this.displayValue += digit;
    }
  }

  inputDecimal(): void {
    if (this.replaceDisplay) {
      this.displayValue = "0.";
      this.replaceDisplay = false;
    } else if (!this.displayValue.includes(".")) {
      this.displayValue += ".";
    }
  }

  chooseOperator(operator: Operator): void {
    if (this.pendingOperator && !this.replaceDisplay) this.calculate();
    this.accumulator = Number(this.displayValue);
    this.pendingOperator = operator;
    this.replaceDisplay = true;
  }

  calculate(): void {
    if (this.accumulator === null || this.pendingOperator === null) return;
    const result = operations[this.pendingOperator](this.accumulator, Number(this.displayValue));
    this.displayValue = Number.isFinite(result) ? String(Number(result.toPrecision(12))) : "Error";
    this.accumulator = null;
    this.pendingOperator = null;
    this.replaceDisplay = true;
  }

  toggleSign(): void {
    if (this.displayValue !== "0") this.displayValue = String(-Number(this.displayValue));
  }

  percent(): void {
    this.displayValue = String(Number(this.displayValue) / 100);
  }

  clear(): void {
    this.displayValue = "0";
    this.accumulator = null;
    this.pendingOperator = null;
    this.replaceDisplay = false;
  }

  display(): string {
    return this.displayValue;
  }
}

function attachCalculator(): void {
  const calculator = new Calculator();
  const display = document.querySelector<HTMLElement>("[data-display]");
  const render = (): void => {
    if (display) display.textContent = calculator.display();
  };
  document.querySelector<HTMLElement>(".keys")?.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("button");
    if (!button) return;
    const { action, value } = button.dataset;
    if (action === "digit" && value) calculator.inputDigit(value);
    if (action === "decimal") calculator.inputDecimal();
    if (action === "operator" && value) calculator.chooseOperator(value as Operator);
    if (action === "equals") calculator.calculate();
    if (action === "sign") calculator.toggleSign();
    if (action === "percent") calculator.percent();
    if (action === "clear") calculator.clear();
    render();
  });
}

if (typeof document !== "undefined") attachCalculator();
