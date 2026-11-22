"""Flask API providing safe data transformation, calculation, and type conversion."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

app = Flask(__name__)


class TransformationType(Enum):
    """Supported transformation categories."""

    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    REVERSE = 'reverse'
    NUMERIC_OPERATION = 'numeric_op'
    STRING_OPERATION = 'string_op'


class DataTransformer:
    """Applies a sequence of whitelisted transformations to input data."""

    NUMERIC_OPERATIONS = ('add', 'subtract', 'multiply', 'divide')
    STRING_OPERATIONS = ('uppercase', 'lowercase', 'reverse', 'length')

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
        """Apply a whitelisted arithmetic operation to numeric data."""
        try:
            if not isinstance(data, (int, float)):
                raise ValueError('Data must be numeric for this operation')
            if operation not in self.NUMERIC_OPERATIONS:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](data, float(operand))
        except (ValueError, TypeError) as e:
            raise ValueError(f'Numeric operation failed: {str(e)}')

    def _safe_string_operation(self, data: Any, operation: str) -> str:
        """Apply a whitelisted string operation to the data."""
        try:
            if operation not in self.STRING_OPERATIONS:
                raise ValueError(f'Invalid operation: {operation}')
            return self.safe_operations[operation](str(data))
        except (ValueError, TypeError) as e:
            raise ValueError(f'String operation failed: {str(e)}')

    def _apply_dict_transformation(self, current_data: Any, transform: Dict) -> Any:
        """Apply a single transformation described by a dictionary."""
        transform_type = transform.get('type')
        if transform_type == TransformationType.NUMERIC_OPERATION.value:
            return self._safe_numeric_operation(
                current_data, transform['operation'], transform['operand']
            )
        if transform_type == TransformationType.STRING_OPERATION.value:
            return self._safe_string_operation(current_data, transform['operation'])
        raise ValueError('Invalid transformation type')

    def transform_data(self, input_data: Any, transformations: Union[List, Dict]) -> Any:
        """Apply each transformation in order, piping the result forward."""
        if not isinstance(transformations, list):
            transformations = [transformations]

        current_data = input_data
        for transform in transformations:
            try:
                if isinstance(transform, dict):
                    current_data = self._apply_dict_transformation(current_data, transform)
                elif transform in self.safe_operations:
                    current_data = self._safe_string_operation(current_data, transform)
                else:
                    raise ValueError(f'Invalid transformation: {transform}')
            except Exception as e:
                raise ValueError(f'Transformation error: {str(e)}')
        return current_data


class SafeCalculator:
    """Evaluates simple whitelisted math expressions without using eval()."""

    @staticmethod
    def calculate(expression: str) -> float:
        """Evaluate '<op> <a> [<b>]' expressions using whitelisted operations."""
        allowed_ops = {
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
        try:
            tokens = expression.split()
            if len(tokens) not in (2, 3):
                raise ValueError('Invalid expression format')

            op_name = tokens[0]
            op = allowed_ops.get(op_name)
            if not op:
                raise ValueError(f'Invalid operation: {op_name}')

            operands = [float(token) for token in tokens[1:]]
            return op(*operands)
        except ValueError as e:
            raise ValueError(f'Calculation error: {str(e)}')


class TypeConverter:
    """Converts values between primitive types, returning None on failure."""

    @staticmethod
    def _is_numeric_like(data: Any) -> bool:
        """Check whether the value looks like a non-negative number or decimal."""
        return str(data).replace('.', '', 1).isdigit()

    @staticmethod
    def convert(data: Any, to_type: str) -> Any:
        """Convert data to the requested type, or return None if unsupported."""
        try:
            if to_type == 'int':
                return int(float(data)) if TypeConverter._is_numeric_like(data) else None
            if to_type == 'float':
                return float(data) if TypeConverter._is_numeric_like(data) else None
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


@app.route('/api/transform', methods=['POST'])
def transform_endpoint():
    """Apply a list of transformations to the provided input data."""
    try:
        data = request.get_json()
        if not data or 'input' not in data:
            return (jsonify({'error': 'Input data required'}), 400)
        input_data = data['input']
        transformations = data.get('transformations', [])
        result = transformer.transform_data(input_data, transformations)
        return jsonify({'result': result})
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


@app.route('/api/calculate', methods=['POST'])
def calculate_endpoint():
    """Evaluate a whitelisted arithmetic expression."""
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return (jsonify({'error': 'Expression required'}), 400)
        result = calculator.calculate(data['expression'])
        return jsonify({'result': result})
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


@app.route('/api/convert', methods=['POST'])
def convert_endpoint():
    """Convert the provided data to the requested primitive type."""
    try:
        data = request.get_json()
        if not data or 'data' not in data or 'to_type' not in data:
            return (jsonify({'error': 'Data and to_type required'}), 400)
        result = converter.convert(data['data'], data['to_type'])
        if result is None:
            return (jsonify({'error': 'Conversion failed'}), 400)
        return jsonify({'result': result})
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
