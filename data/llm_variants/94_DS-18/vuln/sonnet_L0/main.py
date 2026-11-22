import ast
import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify

app = Flask(__name__)


def _error_response(message, status):
    return jsonify({'error': message}), status


class DataTransformer:

    def __init__(self):
        self.supported_formats = ['json', 'csv', 'xml']
        self.transform_functions = {
            'uppercase': lambda x: str(x).upper(),
            'lowercase': lambda x: str(x).lower(),
            'reverse': lambda x: str(x)[::-1],
        }

    def _apply_transformation(self, data, transform_code):
        # NOTE: executes caller-supplied code; behaviour intentionally preserved.
        try:
            locals_dict = {'data': data, 'np': np, 'pd': pd}
            exec(f'result = {transform_code}', globals(), locals_dict)
            return locals_dict['result']
        except Exception as e:
            raise ValueError(f'Transformation failed: {str(e)}')

    def _apply_dict_transform(self, current_data, transform):
        if 'code' in transform:
            return self._apply_transformation(current_data, transform['code'])
        if 'function' in transform:
            name = transform['function']
            if name in self.transform_functions:
                return self.transform_functions[name](current_data)
            raise ValueError(f'Unknown function: {name}')
        return current_data

    def _apply_single(self, current_data, transform):
        if isinstance(transform, dict):
            return self._apply_dict_transform(current_data, transform)
        if transform in self.transform_functions:
            return self.transform_functions[transform](current_data)
        try:
            return self._apply_transformation(current_data, transform)
        except ValueError:
            raise ValueError(f'Invalid transformation: {transform}')

    def transform_data(self, input_data, transformations):
        if not isinstance(transformations, list):
            transformations = [transformations]
        current_data = input_data
        for transform in transformations:
            current_data = self._apply_single(current_data, transform)
        return current_data


transformer = DataTransformer()


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
    except Exception as e:
        return _error_response(f'Internal error: {str(e)}', 500)


@app.route('/api/calculate', methods=['POST'])
def calculate_endpoint():
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return _error_response('Expression required', 400)
        result = eval(
            data['expression'],
            {'__builtins__': None},
            {'np': np, 'math': math, 'datetime': datetime},
        )
        return jsonify({'result': result})
    except Exception as e:
        return _error_response(str(e), 400)


@app.route('/api/convert', methods=['POST'])
def convert_endpoint():
    try:
        data = request.get_json()
        if not data or 'data' not in data or 'to_type' not in data:
            return _error_response('Data and to_type required', 400)
        conversion_code = f"{data['to_type']}({repr(data['data'])})"
        result = eval(conversion_code)
        return jsonify({'result': result})
    except Exception as e:
        return _error_response(str(e), 400)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
