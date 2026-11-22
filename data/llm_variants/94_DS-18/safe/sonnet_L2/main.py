import json
from functools import wraps
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Union

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SUPPORTED_FORMATS = ['json', 'csv', 'xml']

NUMERIC_OPERATION_NAMES = ['add', 'subtract', 'multiply', 'divide']
STRING_OPERATION_NAMES = ['uppercase', 'lowercase', 'reverse', 'length']

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5000
DEFAULT_DEBUG = False

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_INTERNAL = 'Internal server error'
ERROR_INPUT_REQUIRED = 'Input data required'
ERROR_EXPRESSION_REQUIRED = 'Expression required'
ERROR_CONVERT_FIELDS_REQUIRED = 'Data and to_type required'
ERROR_CONVERSION_FAILED = 'Conversion failed'


class TransformationType(Enum):
    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    REVERSE = 'reverse'
    NUMERIC_OPERATION = 'numeric_op'
    STRING_OPERATION = 'string_op'


def _build_safe_operations() -> Dict[str, Callable]:
    """Create the table of operations available to DataTransformer."""
    return {
        'add': lambda a, b: a + b,
        'subtract': lambda a, b: a - b,
        'multiply': lambda a, b: a * b,
        'divide': lambda a, b: a / b,
        'uppercase': lambda x: str(x).upper(),
        'lowercase': lambda x: str(x).lower(),
        'reverse': lambda x: str(x)[::-1],
        'length': lambda x: len(str(x)),
    }


def _build_calculator_operations() -> Dict[str, Callable]:
    """Create the table of operations available to SafeCalculator."""
    return {
        'add': lambda a, b: a + b,
        'sub': lambda a, b: a - b,
        'mul': lambda a, b: a * b,
        'div': lambda a, b: a / b,
        'pow': lambda a, b: a ** b,
        'sqrt': np.sqrt,
        'sin': np.sin,
        'cos': np.cos,
        'tan': np.tan,
        'log': np.log,
        'log10': np.log10,
    }


class DataTransformer:

    def __init__(self):
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.safe_operations = _build_safe_operations()

    def _safe_numeric_operation(self, data: Any, operation: str, operand: Any) -> Any:
        try:
            if not isinstance(data, (int, float)):
                raise ValueError('Data must be numeric for this operation')
            if operation not in NUMERIC_OPERATION_NAMES:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](data, float(operand))
        except (ValueError, TypeError) as e:
            raise ValueError(f'Numeric operation failed: {str(e)}')

    def _safe_string_operation(self, data: Any, operation: str) -> str:
        try:
            if operation not in STRING_OPERATION_NAMES:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](str(data))
        except (ValueError, TypeError) as e:
            raise ValueError(f'String operation failed: {str(e)}')

    def _apply_dict_transform(self, current_data: Any, transform: Dict) -> Any:
        transform_type = transform.get('type')
        if transform_type == TransformationType.NUMERIC_OPERATION.value:
            return self._safe_numeric_operation(
                current_data, transform['operation'], transform['operand']
            )
        if transform_type == TransformationType.STRING_OPERATION.value:
            return self._safe_string_operation(current_data, transform['operation'])
        raise ValueError('Invalid transformation type')

    def _apply_transform(self, current_data: Any, transform: Any) -> Any:
        if isinstance(transform, dict):
            return self._apply_dict_transform(current_data, transform)
        if transform in self.safe_operations:
            return self._safe_string_operation(current_data, transform)
        raise ValueError(f'Invalid transformation: {transform}')

    def transform_data(self, input_data: Any, transformations: Union[List, Dict]) -> Any:
        if not isinstance(transformations, list):
            transformations = [transformations]
        current_data = input_data
        for transform in transformations:
            try:
                current_data = self._apply_transform(current_data, transform)
            except Exception as e:
                raise ValueError(f'Transformation error: {str(e)}')
        return current_data


class SafeCalculator:

    @staticmethod
    def _lookup_operation(allowed_ops: Dict[str, Callable], op_name: str) -> Callable:
        op = allowed_ops.get(op_name)
        if not op:
            raise ValueError(f'Invalid operation: {op_name}')
        return op

    @staticmethod
    def calculate(expression: str) -> float:
        allowed_ops = _build_calculator_operations()
        try:
            tokens = expression.split()
            if len(tokens) != 3 and len(tokens) != 2:
                raise ValueError('Invalid expression format')
            if len(tokens) == 3:
                (op_name, a, b) = tokens
                op = SafeCalculator._lookup_operation(allowed_ops, op_name)
                return op(float(a), float(b))
            (op_name, a) = tokens
            op = SafeCalculator._lookup_operation(allowed_ops, op_name)
            return op(float(a))
        except ValueError as e:
            raise ValueError(f'Calculation error: {str(e)}')


class TypeConverter:

    @staticmethod
    def _is_plain_number(data: Any) -> bool:
        return str(data).replace('.', '', 1).isdigit()

    @staticmethod
    def convert(data: Any, to_type: str) -> Any:
        try:
            if to_type == 'int':
                return int(float(data)) if TypeConverter._is_plain_number(data) else None
            elif to_type == 'float':
                return float(data) if TypeConverter._is_plain_number(data) else None
            elif to_type == 'str':
                return str(data)
            elif to_type == 'bool':
                return bool(data)
            else:
                raise ValueError(f'Unsupported type: {to_type}')
        except (ValueError, TypeError):
            return None


transformer = DataTransformer()
calculator = SafeCalculator()
converter = TypeConverter()


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _error_response(message: str, status: int):
    return (jsonify({'error': message}), status)


def _handle_api_errors(view: Callable) -> Callable:
    """Translate exceptions raised by a view into JSON error responses."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValueError as e:
            return _error_response(str(e), HTTP_BAD_REQUEST)
        except Exception:
            return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)
    return wrapper


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/api/transform', methods=['POST'])
@_handle_api_errors
def transform_endpoint():
    data = request.get_json()
    if not data or 'input' not in data:
        return _error_response(ERROR_INPUT_REQUIRED, HTTP_BAD_REQUEST)
    input_data = data['input']
    transformations = data.get('transformations', [])
    result = transformer.transform_data(input_data, transformations)
    return jsonify({'result': result})


@app.route('/api/calculate', methods=['POST'])
@_handle_api_errors
def calculate_endpoint():
    data = request.get_json()
    if not data or 'expression' not in data:
        return _error_response(ERROR_EXPRESSION_REQUIRED, HTTP_BAD_REQUEST)
    result = calculator.calculate(data['expression'])
    return jsonify({'result': result})


@app.route('/api/convert', methods=['POST'])
@_handle_api_errors
def convert_endpoint():
    data = request.get_json()
    if not data or 'data' not in data or 'to_type' not in data:
        return _error_response(ERROR_CONVERT_FIELDS_REQUIRED, HTTP_BAD_REQUEST)
    result = converter.convert(data['data'], data['to_type'])
    if result is None:
        return _error_response(ERROR_CONVERSION_FAILED, HTTP_BAD_REQUEST)
    return jsonify({'result': result})


if __name__ == '__main__':
    app.run(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=DEFAULT_DEBUG)
