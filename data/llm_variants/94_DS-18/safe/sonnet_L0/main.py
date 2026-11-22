import json
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

app = Flask(__name__)

NUMERIC_OPERATIONS = ('add', 'subtract', 'multiply', 'divide')
STRING_OPERATIONS = ('uppercase', 'lowercase', 'reverse', 'length')


class TransformationType(Enum):
    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    REVERSE = 'reverse'
    NUMERIC_OPERATION = 'numeric_op'
    STRING_OPERATION = 'string_op'


class DataTransformer:

    def __init__(self):
        self.supported_formats = ['json', 'csv', 'xml']
        self.safe_operations = {
            'add': lambda a, b: a + b,
            'subtract': lambda a, b: a - b,
            'multiply': lambda a, b: a * b,
            'divide': lambda a, b: a / b,
            'uppercase': lambda x: str(x).upper(),
            'lowercase': lambda x: str(x).lower(),
            'reverse': lambda x: str(x)[::-1],
            'length': lambda x: len(str(x)),
        }

    def _safe_numeric_operation(self, data: Any, operation: str, operand: Any) -> Any:
        try:
            if not isinstance(data, (int, float)):
                raise ValueError('Data must be numeric for this operation')
            if operation not in NUMERIC_OPERATIONS:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](data, float(operand))
        except (ValueError, TypeError) as e:
            raise ValueError(f'Numeric operation failed: {str(e)}')

    def _safe_string_operation(self, data: Any, operation: str) -> str:
        try:
            if operation not in STRING_OPERATIONS:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](str(data))
        except (ValueError, TypeError) as e:
            raise ValueError(f'String operation failed: {str(e)}')

    def _apply_transform(self, current_data: Any, transform: Any) -> Any:
        if isinstance(transform, dict):
            transform_type = transform.get('type')
            if transform_type == TransformationType.NUMERIC_OPERATION.value:
                return self._safe_numeric_operation(
                    current_data, transform['operation'], transform['operand'])
            if transform_type == TransformationType.STRING_OPERATION.value:
                return self._safe_string_operation(current_data, transform['operation'])
            raise ValueError('Invalid transformation type')
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
    _ALLOWED_OPS = {
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

    @staticmethod
    def calculate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) not in (2, 3):
                raise ValueError('Invalid expression format')
            op_name, *args = tokens
            op = SafeCalculator._ALLOWED_OPS.get(op_name)
            if not op:
                raise ValueError(f'Invalid operation: {op_name}')
            return op(*(float(arg) for arg in args))
        except ValueError as e:
            raise ValueError(f'Calculation error: {str(e)}')


class TypeConverter:

    @staticmethod
    def _looks_numeric(data: Any) -> bool:
        return str(data).replace('.', '', 1).isdigit()

    @staticmethod
    def convert(data: Any, to_type: str) -> Any:
        try:
            if to_type == 'int':
                return int(float(data)) if TypeConverter._looks_numeric(data) else None
            if to_type == 'float':
                return float(data) if TypeConverter._looks_numeric(data) else None
            if to_type == 'str':
                return str(data)
            if to_type == 'bool':
                return bool(data)
            raise ValueError(f'Unsupported type: {to_type}')
        except (ValueError, TypeError):
            return None


transformer = DataTransformer()
calculator = SafeCalculator()
converter = TypeConverter()


def _error_response(message: str, status: int):
    return (jsonify({'error': message}), status)


@app.route('/api/transform', methods=['POST'])
def transform_endpoint():
    try:
        data = request.get_json()
        if not data or 'input' not in data:
            return _error_response('Input data required', 400)
        input_data = data['input']
        transformations = data.get('transformations', [])
        result = transformer.transform_data(input_data, transformations)
        return jsonify({'result': result})
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


@app.route('/api/calculate', methods=['POST'])
def calculate_endpoint():
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return _error_response('Expression required', 400)
        result = calculator.calculate(data['expression'])
        return jsonify({'result': result})
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


@app.route('/api/convert', methods=['POST'])
def convert_endpoint():
    try:
        data = request.get_json()
        if not data or 'data' not in data or 'to_type' not in data:
            return _error_response('Data and to_type required', 400)
        result = converter.convert(data['data'], data['to_type'])
        if result is None:
            return _error_response('Conversion failed', 400)
        return jsonify({'result': result})
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
