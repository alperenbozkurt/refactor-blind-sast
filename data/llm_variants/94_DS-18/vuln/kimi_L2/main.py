"""JSON web service for transforming, calculating and converting data."""

# Kept for backwards compatibility: both names are part of the module
# namespace that evaluated expressions (see /api/convert) can reach.
import ast
import json
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerConfig:
    """Network binding used when running the built-in server."""

    host: str = '0.0.0.0'
    port: int = 5000


SERVER_CONFIG = ServerConfig()

# HTTP details.
HTTP_POST = 'POST'
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

# Route paths.
ROUTE_TRANSFORM = '/api/transform'
ROUTE_CALCULATE = '/api/calculate'
ROUTE_CONVERT = '/api/convert'

# Payload field names.
FIELD_INPUT = 'input'
FIELD_TRANSFORMATIONS = 'transformations'
FIELD_EXPRESSION = 'expression'
FIELD_DATA = 'data'
FIELD_TO_TYPE = 'to_type'
FIELD_CODE = 'code'
FIELD_FUNCTION = 'function'
FIELD_RESULT = 'result'
FIELD_ERROR = 'error'

# Named transformations.
TRANSFORM_UPPERCASE = 'uppercase'
TRANSFORM_LOWERCASE = 'lowercase'
TRANSFORM_REVERSE = 'reverse'

# Advertised input/output formats.
SUPPORTED_FORMATS = ('json', 'csv', 'xml')

# Error messages.
ERROR_INPUT_REQUIRED = 'Input data required'
ERROR_EXPRESSION_REQUIRED = 'Expression required'
ERROR_DATA_AND_TO_TYPE_REQUIRED = 'Data and to_type required'


# ---------------------------------------------------------------------------
# Transformation primitives
# ---------------------------------------------------------------------------


def _to_uppercase(value):
    return str(value).upper()


def _to_lowercase(value):
    return str(value).lower()


def _reverse(value):
    return str(value)[::-1]


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _result_response(result):
    """Return the JSON body produced for a successful request."""
    return jsonify({FIELD_RESULT: result})


def _error_response(message, status_code):
    """Return the ``(body, status)`` tuple produced for a failed request."""
    return (jsonify({FIELD_ERROR: message}), status_code)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------


def _expression_namespace():
    """Local namespace available to ``/api/calculate`` expressions."""
    import math

    return {'np': np, 'math': math, 'datetime': datetime}


def _evaluate_expression(expression):
    """Evaluate ``expression`` with builtins disabled."""
    return eval(expression, {'__builtins__': None}, _expression_namespace())


def _conversion_code(to_type, value):
    """Build the ``to_type(value)`` snippet run by ``/api/convert``."""
    return f'{to_type}({value!r})'


app = Flask(__name__)


class DataTransformer:
    """Apply named functions or code snippets to input data."""

    def __init__(self):
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.transform_functions = self._default_transform_functions()

    @staticmethod
    def _default_transform_functions():
        return {
            TRANSFORM_UPPERCASE: _to_uppercase,
            TRANSFORM_LOWERCASE: _to_lowercase,
            TRANSFORM_REVERSE: _reverse,
        }

    @staticmethod
    def _execution_namespace(data):
        """Local namespace available to transformation code snippets."""
        return {'data': data, 'np': np, 'pd': pd}

    @staticmethod
    def _as_list(transformations):
        if isinstance(transformations, list):
            return transformations
        return [transformations]

    def _apply_transformation(self, data, transform_code):
        try:
            locals_dict = self._execution_namespace(data)
            exec(f'result = {transform_code}', globals(), locals_dict)
            return locals_dict['result']
        except Exception as e:
            raise ValueError(f'Transformation failed: {str(e)}')

    def _apply_dict_transformation(self, current_data, transform):
        if FIELD_CODE in transform:
            return self._apply_transformation(current_data, transform[FIELD_CODE])
        if FIELD_FUNCTION in transform:
            function_name = transform[FIELD_FUNCTION]
            if function_name not in self.transform_functions:
                raise ValueError(f'Unknown function: {function_name}')
            return self.transform_functions[function_name](current_data)
        return current_data

    def _apply_single_transformation(self, current_data, transform):
        if isinstance(transform, dict):
            return self._apply_dict_transformation(current_data, transform)
        if transform in self.transform_functions:
            return self.transform_functions[transform](current_data)
        try:
            return self._apply_transformation(current_data, transform)
        except ValueError:
            raise ValueError(f'Invalid transformation: {transform}')

    def transform_data(self, input_data, transformations):
        current_data = input_data
        for transform in self._as_list(transformations):
            current_data = self._apply_single_transformation(current_data, transform)
        return current_data


transformer = DataTransformer()


@app.route(ROUTE_TRANSFORM, methods=[HTTP_POST])
def transform_endpoint():
    try:
        data = request.get_json()
        if not data or FIELD_INPUT not in data:
            return _error_response(ERROR_INPUT_REQUIRED, HTTP_BAD_REQUEST)
        input_data = data[FIELD_INPUT]
        transformations = data.get(FIELD_TRANSFORMATIONS, [])
        result = transformer.transform_data(input_data, transformations)
        return _result_response(result)
    except ValueError as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)
    except Exception as e:
        return _error_response(
            f'Internal error: {str(e)}', HTTP_INTERNAL_SERVER_ERROR
        )


@app.route(ROUTE_CALCULATE, methods=[HTTP_POST])
def calculate_endpoint():
    try:
        data = request.get_json()
        if not data or FIELD_EXPRESSION not in data:
            return _error_response(ERROR_EXPRESSION_REQUIRED, HTTP_BAD_REQUEST)
        result = _evaluate_expression(data[FIELD_EXPRESSION])
        return _result_response(result)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


@app.route(ROUTE_CONVERT, methods=[HTTP_POST])
def convert_endpoint():
    try:
        data = request.get_json()
        if not data or FIELD_DATA not in data or FIELD_TO_TYPE not in data:
            return _error_response(
                ERROR_DATA_AND_TO_TYPE_REQUIRED, HTTP_BAD_REQUEST
            )
        conversion_code = _conversion_code(data[FIELD_TO_TYPE], data[FIELD_DATA])
        result = eval(conversion_code)
        return _result_response(result)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


if __name__ == '__main__':
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port)
