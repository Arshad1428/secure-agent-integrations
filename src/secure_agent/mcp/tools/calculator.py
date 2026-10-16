import math
from typing import Literal


def calculate(
    operation: Literal[
        "add",
        "subtract",
        "multiply",
        "divide",
    ],
    a: float,
    b: float,
) -> dict:
    """Perform an arithmetic operation on two finite numbers."""

    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("Both numbers must be finite")

    if operation == "add":
        result = a + b

    elif operation == "subtract":
        result = a - b

    elif operation == "multiply":
        result = a * b

    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")

        result = a / b

    else:
        raise ValueError("Unsupported operation")

    if not math.isfinite(result):
        raise ValueError("Result exceeds numeric limits")

    return {"result": result}