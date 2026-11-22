import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

app = Flask(__name__)


class TransformationType(Enum):
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    REVERSE = "reverse"
    NUMERIC_OPERATION = "numeric_op"
    STRING_OPERATION = "string_op"


class DataTransformer:
    """Applies a pipeline of whitelisted transformations to input data."""

    NUMERIC_OPERATIONS = ("add", "subtract", "multiply", "divide")
    STRING_OPERATIONS = ("uppercase", "lowercase", "reverse", "length")

    def __init__(self):
        self.supported_formats = ["json", "csv", "xml"]
        self.safe_operations = {
            "add": lambda a, b: a + b,
            "subtract": lambda a, b: a - b,
            "multiply": lambda a, b: a * b,
            "divide": lambda a, b: a / b,
            "uppercase": lambda x: str(x).upper(),
            "lowercase": lambda x: str(x).lower(),
            "reverse": lambda x: str(x)[::-1],
            "length": lambda x: len(str(x)),
        }

    def _safe_numeric_operation(self, data: Any, operation: str, operand: Any) -> Any:
        try:
            if not isinstance(data, (int, float)):
                raise ValueError("Data must be numeric for this operation")
            if operation not in self.NUMERIC_OPERATIONS:
                raise ValueError(f"Invalid operation: {operation}")
            return self.safe_operations[operation](data, float(operand))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Numeric operation failed: {str(e)}")

    def _safe_string_operation(self, data: Any, operation: str) -> str:
        try:
            if operation not in self.STRING_OPERATIONS:
                raise ValueError(f"Invalid operation: {operation}")
            return self.safe_operations[operation](str(data))
        except (ValueError, TypeError) as e:
            raise ValueError(f"String operation failed: {str(e)}")

    def transform_data(self, input_data: Any, transformations: Union[List, Dict]) -> Any:
        if not isinstance(transformations, list):
            transformations = [transformations]
        current_data = input_data
        for transform in transformations:
            current_data = self._apply_transformation(current_data, transform)
        return current_data

    def _apply_transformation(self, current_data: Any, transform: Any) -> Any:
        try:
            if isinstance(transform, dict):
                return self._apply_dict_transformation(current_data, transform)
            if transform in self.safe_operations:
                return self._safe_string_operation(current_data, transform)
            raise ValueError(f"Invalid transformation: {transform}")
        except Exception as e:
            raise ValueError(f"Transformation error: {str(e)}")

    def _apply_dict_transformation(self, current_data: Any, transform: Dict) -> Any:
        transform_type = transform.get("type")
        if transform_type == TransformationType.NUMERIC_OPERATION.value:
            return self._safe_numeric_operation(
                current_data, transform["operation"], transform["operand"]
            )
        if transform_type == TransformationType.STRING_OPERATION.value:
            return self._safe_string_operation(current_data, transform["operation"])
        raise ValueError("Invalid transformation type")


class SafeCalculator:
    """Evaluates simple whitelisted arithmetic expressions."""

    _OPERATIONS = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
        "pow": lambda a, b: a ** b,
        "sqrt": np.sqrt,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "log": np.log,
        "log10": np.log10,
    }

    @staticmethod
    def calculate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) not in (2, 3):
                raise ValueError("Invalid expression format")
            op_name = tokens[0]
            op = SafeCalculator._OPERATIONS.get(op_name)
            if not op:
                raise ValueError(f"Invalid operation: {op_name}")
            return op(*[float(token) for token in tokens[1:]])
        except ValueError as e:
            raise ValueError(f"Calculation error: {str(e)}")


class TypeConverter:
    """Converts values between basic Python types."""

    @staticmethod
    def convert(data: Any, to_type: str) -> Any:
        try:
            if to_type == "int":
                return int(float(data)) if TypeConverter._is_numeric(data) else None
            if to_type == "float":
                return float(data) if TypeConverter._is_numeric(data) else None
            if to_type == "str":
                return str(data)
            if to_type == "bool":
                return bool(data)
            raise ValueError(f"Unsupported type: {to_type}")
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_numeric(data: Any) -> bool:
        return str(data).replace(".", "", 1).isdigit()


transformer = DataTransformer()
calculator = SafeCalculator()
converter = TypeConverter()


def _extract_json_payload(required_keys, error_message):
    data = request.get_json()
    if not data or any(key not in data for key in required_keys):
        return None, (jsonify({"error": error_message}), 400)
    return data, None


@app.route("/api/transform", methods=["POST"])
def transform_endpoint():
    try:
        data, error = _extract_json_payload(("input",), "Input data required")
        if error is not None:
            return error
        result = transformer.transform_data(
            data["input"], data.get("transformations", [])
        )
        return jsonify({"result": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/calculate", methods=["POST"])
def calculate_endpoint():
    try:
        data, error = _extract_json_payload(("expression",), "Expression required")
        if error is not None:
            return error
        result = calculator.calculate(data["expression"])
        return jsonify({"result": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/convert", methods=["POST"])
def convert_endpoint():
    try:
        data, error = _extract_json_payload(
            ("data", "to_type"), "Data and to_type required"
        )
        if error is not None:
            return error
        result = converter.convert(data["data"], data["to_type"])
        if result is None:
            return jsonify({"error": "Conversion failed"}), 400
        return jsonify({"result": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
