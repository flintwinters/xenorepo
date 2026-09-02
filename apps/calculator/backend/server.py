"""Server-authoritative arithmetic exposed through Calculator's MonoForm action."""

from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict

from monotools.runtime.http import enforce_same_origin
from monotools.runtime.application import create_application
from monotools.runtime.monoform import monoform_operation


Operator = Literal["add", "subtract", "multiply", "divide"]


class Calculation(BaseModel):
    """A complete stateless calculation request."""

    model_config = ConfigDict(allow_inf_nan=False)

    left_operand: float
    operator: Operator
    right_operand: float


class CalculationResult(BaseModel):
    expression: str
    result: float


def calculate(value: Calculation) -> CalculationResult:
    """Evaluate one finite four-function calculation or reject division by zero."""
    if value.operator == "divide" and value.right_operand == 0:
        raise HTTPException(status_code=422, detail=[{
            "type": "value_error",
            "loc": ["body", "right_operand"],
            "msg": "Division by zero is undefined.",
            "input": value.right_operand,
        }])
    operations = {
        "add": value.left_operand + value.right_operand,
        "subtract": value.left_operand - value.right_operand,
        "multiply": value.left_operand * value.right_operand,
        "divide": value.left_operand / value.right_operand,
    }
    result = operations[value.operator]
    if not (-float("inf") < result < float("inf")):
        raise HTTPException(status_code=422, detail="Result must be finite.")
    symbols = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷"}
    return CalculationResult(
        expression=f"{value.left_operand:g} {symbols[value.operator]} {value.right_operand:g}",
        result=result,
    )


app = create_application("calculator")


@app.post("/api/calculate", response_model=CalculationResult, operation_id="calculate",
    openapi_extra=monoform_operation(kind="action", entity="calculation",
        title="Calculate", submit_label="CALCULATE"))
async def calculate_endpoint(value: Calculation, request: Request) -> CalculationResult:
    enforce_same_origin(request, lambda message: HTTPException(status_code=403, detail=message))
    return calculate(value)
