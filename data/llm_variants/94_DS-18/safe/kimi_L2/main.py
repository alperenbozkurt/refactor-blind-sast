import json
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

app = Flask(__name__)


class TransformationType(Enum):
    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    REVERSE = 'reverse'
    NUMERIC_OPERATION = 'numeric_op'
    STRING_OPERATION = 'string_op'


_DEFAULT_SUPPORTED_FORMATS = ('json', 'csv', 'xml')
_NUMERIC_OPERATION_NAMES = ['add', 'subtract', 'multiply', 'divide']
_STRING_OPERATION_NAMES = ['uppercase', 'lowercase', 'reverse', 'length']

_NUMERIC_TRANSFORMATION_TYPE = TransformationType.NUMERIC_OPERATION.value
_STRING_TRANSFORMATION_TYPE = TransformationType.STRING_OPERATION.value

_CALCULATOR_OPERATIONS = {
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

_ERROR_INPUT_DATA_REQUIRED = 'Input data required'
_ERROR_EXPRESSION_REQUIRED = 'Expression required'
_ERROR_DATA_AND_TO_TYPE_REQUIRED = 'Data and to_type required'
_ERROR_CONVERSION_FAILED = 'Conversion failed'
_ERROR_INTERNAL_SERVER = 'Internal server error'

_SERVER_HOST = '0.0.0.0'
_SERVER_PORT = 5000
_SERVER_DEBUG = False


class DataTransformer:

    def __init__(self):
        self.supported_formats = list(_DEFAULT_SUPPORTED_FORMATS)
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
            if operation not in _NUMERIC_OPERATION_NAMES:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](data, float(operand))
        except (ValueError, TypeError) as e:
            raise ValueError(f'Numeric operation failed: {str(e)}')

    def _safe_string_operation(self, data: Any, operation: str) -> str:
        try:
            if operation not in _STRING_OPERATION_NAMES:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](str(data))
        except (ValueError, TypeError) as e:
            raise ValueError(f'String operation failed: {str(e)}')

    def _apply_dict_transformation(self, current_data: Any, transform: Dict) -> Any:
        transformation_type = transform.get('type')
        if transformation_type == _NUMERIC_TRANSFORMATION_TYPE:
            return self._safe_numeric_operation(
                current_data,
                transform['operation'],
                transform['operand'],
            )
        if transformation_type == _STRING_TRANSFORMATION_TYPE:
            return self._safe_string_operation(current_data, transform['operation'])
        raise ValueError('Invalid transformation type')

    def _apply_transformation(self, current_data: Any, transform: Any) -> Any:
        if isinstance(transform, dict):
            return self._apply_dict_transformation(current_data, transform)
        if transform in self.safe_operations:
            return self._safe_string_operation(current_data, transform)
        raise ValueError(f'Invalid transformation: {transform}')

    def transform_data(self, input_data: Any, transformations: Union[List, Dict]) -> Any:
        if not isinstance(transformations, list):
            transformations = [transformations]
        current_data = input_data
        for transform in transformations:
            try:
                current_data = self._apply_transformation(current_data, transform)
            except Exception as e:
                raise ValueError(f'Transformation error: {str(e)}')
        return current_data


class SafeCalculator:

    @staticmethod
    def calculate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) != 3 and len(tokens) != 2:
                raise ValueError('Invalid expression format')
            op_name = tokens[0]
            op = _CALCULATOR_OPERATIONS.get(op_name)
            if not op:
                raise ValueError(f'Invalid operation: {op_name}')
            arguments = [float(token) for token in tokens[1:]]
            return op(*arguments)
        except ValueError as e:
            raise ValueError(f'Calculation error: {str(e)}')


def _has_numeric_representation(data: Any) -> bool:
    return str(data).replace('.', '', 1).isdigit()


class TypeConverter:

    @staticmethod
    def convert(data: Any, to_type: str) -> Any:
        try:
            if to_type == 'int':
                return int(float(data)) if _has_numeric_representation(data) else None
            elif to_type == 'float':
                return float(data) if _has_numeric_representation(data) else None
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


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _result_response(result):
    return jsonify({'result': result})


@app.route('/api/transform', methods=['POST'])
def transform_endpoint():
    try:
        data = request.get_json()
        if not data or 'input' not in data:
            return _error_response(_ERROR_INPUT_DATA_REQUIRED, 400)
        input_data = data['input']
        transformations = data.get('transformations', [])
        result = transformer.transform_data(input_data, transformations)
        return _result_response(result)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(_ERROR_INTERNAL_SERVER, 500)


@app.route('/api/calculate', methods=['POST'])
def calculate_endpoint():
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return _error_response(_ERROR_EXPRESSION_REQUIRED, 400)
        result = calculator.calculate(data['expression'])
        return _result_response(result)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(_ERROR_INTERNAL_SERVER, 500)


@app.route('/api/convert', methods=['POST'])
def convert_endpoint():
    try:
        data = request.get_json()
        if not data or 'data' not in data or 'to_type' not in data:
            return _error_response(_ERROR_DATA_AND_TO_TYPE_REQUIRED, 400)
        result = converter.convert(data['data'], data['to_type'])
        if result is None:
            return _error_response(_ERROR_CONVERSION_FAILED, 400)
        return _result_response(result)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(_ERROR_INTERNAL_SERVER, 500)


if __name__ == '__main__':
    app.run(host=_SERVER_HOST, port=_SERVER_PORT, debug=_SERVER_DEBUG)
