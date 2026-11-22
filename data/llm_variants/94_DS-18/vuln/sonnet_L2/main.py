import json
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from datetime import datetime
import ast

# NOTE: This module deliberately preserves its original behaviour, including the
# use of exec()/eval() on client-supplied input. Those code paths allow arbitrary
# code execution and should be replaced (e.g. with a safe expression parser or a
# whitelist of operations) before exposing this service to untrusted clients.

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SUPPORTED_FORMATS = ['json', 'csv', 'xml']

HTTP_OK_CLIENT_ERROR = 400
HTTP_SERVER_ERROR = 500

TRANSFORM_ROUTE = '/api/transform'
CALCULATE_ROUTE = '/api/calculate'
CONVERT_ROUTE = '/api/convert'

HOST = '0.0.0.0'
PORT = 5000

ERR_INPUT_REQUIRED = 'Input data required'
ERR_EXPRESSION_REQUIRED = 'Expression required'
ERR_CONVERT_REQUIRED = 'Data and to_type required'
ERR_INTERNAL_PREFIX = 'Internal error: '
ERR_TRANSFORM_FAILED_PREFIX = 'Transformation failed: '
ERR_UNKNOWN_FUNCTION_PREFIX = 'Unknown function: '
ERR_INVALID_TRANSFORM_PREFIX = 'Invalid transformation: '


# --------------------------------------------------------------------------- #
# Built-in transformation functions
# --------------------------------------------------------------------------- #
def _to_upper(value):
    return str(value).upper()


def _to_lower(value):
    return str(value).lower()


def _reverse(value):
    return str(value)[::-1]


def _build_transform_functions():
    return {
        'uppercase': _to_upper,
        'lowercase': _to_lower,
        'reverse': _reverse,
    }


# --------------------------------------------------------------------------- #
# Data transformer
# --------------------------------------------------------------------------- #
class DataTransformer:

    def __init__(self):
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.transform_functions = _build_transform_functions()

    def _apply_transformation(self, data, transform_code):
        try:
            locals_dict = {'data': data, 'np': np, 'pd': pd}
            exec(f'result = {transform_code}', globals(), locals_dict)
            return locals_dict['result']
        except Exception as e:
            raise ValueError(f'{ERR_TRANSFORM_FAILED_PREFIX}{str(e)}')

    def _apply_named_function(self, data, name):
        return self.transform_functions[name](data)

    def _apply_dict_transform(self, current_data, transform):
        if 'code' in transform:
            return self._apply_transformation(current_data, transform['code'])
        if 'function' in transform:
            if transform['function'] in self.transform_functions:
                return self._apply_named_function(current_data, transform['function'])
            raise ValueError(f"{ERR_UNKNOWN_FUNCTION_PREFIX}{transform['function']}")
        return current_data

    def _apply_simple_transform(self, current_data, transform):
        if transform in self.transform_functions:
            return self._apply_named_function(current_data, transform)
        try:
            return self._apply_transformation(current_data, transform)
        except ValueError:
            raise ValueError(f'{ERR_INVALID_TRANSFORM_PREFIX}{transform}')

    def _apply_single(self, current_data, transform):
        if isinstance(transform, dict):
            return self._apply_dict_transform(current_data, transform)
        return self._apply_simple_transform(current_data, transform)

    def transform_data(self, input_data, transformations):
        if not isinstance(transformations, list):
            transformations = [transformations]
        current_data = input_data
        for transform in transformations:
            current_data = self._apply_single(current_data, transform)
        return current_data


transformer = DataTransformer()


# --------------------------------------------------------------------------- #
# Response helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _result_response(result):
    return jsonify({'result': result})


# --------------------------------------------------------------------------- #
# Calculation / conversion helpers
# --------------------------------------------------------------------------- #
def _evaluate_expression(expression):
    eval_locals = {'np': np, 'math': __import__('math'), 'datetime': datetime}
    return eval(expression, {'__builtins__': None}, eval_locals)


def _convert_value(data):
    conversion_code = f"{data['to_type']}({repr(data['data'])})"
    return eval(conversion_code)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route(TRANSFORM_ROUTE, methods=['POST'])
def transform_endpoint():
    try:
        data = request.get_json()
        if not data or 'input' not in data:
            return _error_response(ERR_INPUT_REQUIRED, HTTP_OK_CLIENT_ERROR)
        input_data = data['input']
        transformations = data.get('transformations', [])
        result = transformer.transform_data(input_data, transformations)
        return _result_response(result)
    except ValueError as e:
        return _error_response(str(e), HTTP_OK_CLIENT_ERROR)
    except Exception as e:
        return _error_response(f'{ERR_INTERNAL_PREFIX}{str(e)}', HTTP_SERVER_ERROR)


@app.route(CALCULATE_ROUTE, methods=['POST'])
def calculate_endpoint():
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return _error_response(ERR_EXPRESSION_REQUIRED, HTTP_OK_CLIENT_ERROR)
        result = _evaluate_expression(data['expression'])
        return _result_response(result)
    except Exception as e:
        return _error_response(str(e), HTTP_OK_CLIENT_ERROR)


@app.route(CONVERT_ROUTE, methods=['POST'])
def convert_endpoint():
    try:
        data = request.get_json()
        if not data or 'data' not in data or 'to_type' not in data:
            return _error_response(ERR_CONVERT_REQUIRED, HTTP_OK_CLIENT_ERROR)
        result = _convert_value(data)
        return _result_response(result)
    except Exception as e:
        return _error_response(str(e), HTTP_OK_CLIENT_ERROR)


if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
