const operations = {
    "+": (left, right) => left + right,
    "−": (left, right) => left - right,
    "×": (left, right) => left * right,
    "÷": (left, right) => left / right,
};
export class Calculator {
    displayValue = "0";
    accumulator = null;
    pendingOperator = null;
    replaceDisplay = false;
    inputDigit(digit) {
        if (this.replaceDisplay || this.displayValue === "0") {
            this.displayValue = digit;
            this.replaceDisplay = false;
        }
        else if (this.displayValue.length < 14) {
            this.displayValue += digit;
        }
    }
    inputDecimal() {
        if (this.replaceDisplay) {
            this.displayValue = "0.";
            this.replaceDisplay = false;
        }
        else if (!this.displayValue.includes(".")) {
            this.displayValue += ".";
        }
    }
    chooseOperator(operator) {
        if (this.pendingOperator && !this.replaceDisplay)
            this.calculate();
        this.accumulator = Number(this.displayValue);
        this.pendingOperator = operator;
        this.replaceDisplay = true;
    }
    calculate() {
        if (this.accumulator === null || this.pendingOperator === null)
            return;
        const result = operations[this.pendingOperator](this.accumulator, Number(this.displayValue));
        this.displayValue = Number.isFinite(result) ? String(Number(result.toPrecision(12))) : "Error";
        this.accumulator = null;
        this.pendingOperator = null;
        this.replaceDisplay = true;
    }
    toggleSign() {
        if (this.displayValue !== "0")
            this.displayValue = String(-Number(this.displayValue));
    }
    percent() {
        this.displayValue = String(Number(this.displayValue) / 100);
    }
    clear() {
        this.displayValue = "0";
        this.accumulator = null;
        this.pendingOperator = null;
        this.replaceDisplay = false;
    }
    display() {
        return this.displayValue;
    }
}
function attachCalculator() {
    const calculator = new Calculator();
    const display = document.querySelector("[data-display]");
    const render = () => {
        if (display)
            display.textContent = calculator.display();
    };
    document.querySelector(".keys")?.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button)
            return;
        const { action, value } = button.dataset;
        if (action === "digit" && value)
            calculator.inputDigit(value);
        if (action === "decimal")
            calculator.inputDecimal();
        if (action === "operator" && value)
            calculator.chooseOperator(value);
        if (action === "equals")
            calculator.calculate();
        if (action === "sign")
            calculator.toggleSign();
        if (action === "percent")
            calculator.percent();
        if (action === "clear")
            calculator.clear();
        render();
    });
}
if (typeof document !== "undefined")
    attachCalculator();
