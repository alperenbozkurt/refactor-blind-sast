"""Product filtering API.

A small Flask service exposing HTTP endpoints for filtering an in-memory
product catalog. Refactored for clarity and modularity while preserving the
original public interface (module-level names, function signatures, routes
and command-line behaviour).
"""

import json  # noqa: F401  -- retained as part of the original module interface
import re  # noqa: F401  -- retained as part of the original module interface
from dataclasses import dataclass

from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Settings for the built-in Flask development server."""

    debug: bool = True


SERVER_CONFIG = ServerConfig()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

DEFAULT_PRODUCTS = (
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILTER_ROUTE = '/api/products/filter'
DYNAMIC_FILTER_ROUTE = '/api/products/dynamic_filter'
SAFE_FILTER_ROUTE = '/api/products/safe_filter'
POST_METHOD = 'POST'

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

FILTER_KEY = 'filter'
FIELD_KEY = 'field'
OPERATOR_KEY = 'operator'
VALUE_KEY = 'value'
ERROR_KEY = 'error'
COUNT_KEY = 'count'
RESULTS_KEY = 'results'

DYNAMIC_FILTER_REQUIRED_KEYS = (FIELD_KEY, OPERATOR_KEY, VALUE_KEY)

FILTER_REQUIRED_MESSAGE = 'Filter condition required'
INVALID_FILTER_FORMAT_MESSAGE = 'Invalid filter format'

CONDITION_TEMPLATE = "item['{field}'] {operator} {value}"
ITEM_VARIABLE = 'item'


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
products = [dict(product) for product in DEFAULT_PRODUCTS]


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def _evaluate_condition(condition: str, item: dict):
    """Evaluate ``condition`` with ``item`` bound to the given product."""
    return eval(condition, {ITEM_VARIABLE: item})


def _filter_with_condition(items, condition: str) -> list:
    """Return every item for which ``condition`` evaluates truthy."""
    return [item for item in items if _evaluate_condition(condition, item)]


def _build_condition(field, operator, value) -> str:
    """Assemble a raw filter expression from field, operator and value."""
    return CONDITION_TEMPLATE.format(field=field, operator=operator, value=value)


def safe_filter(products, condition):
    """Return the products matching ``condition`` (public API, unchanged)."""
    return _filter_with_condition(products, condition)


# ---------------------------------------------------------------------------
# Request/response helpers
# ---------------------------------------------------------------------------

def _get_request_data():
    """Return the parsed JSON body of the current request."""
    return request.get_json()


def _has_required_keys(data: dict, keys) -> bool:
    """Return True when ``data`` contains every key in ``keys``."""
    return all(key in data for key in keys)


def _error_response(message: str, status_code: int):
    """Build a ``(JSON response, status code)`` tuple describing an error."""
    return (jsonify({ERROR_KEY: message}), status_code)


def _results_response(filtered: list):
    """Build the standard ``count``/``results`` JSON response."""
    return jsonify({COUNT_KEY: len(filtered), RESULTS_KEY: filtered})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(FILTER_ROUTE, methods=[POST_METHOD])
def filter_products():
    try:
        data = _get_request_data()
        if not data or FILTER_KEY not in data:
            return _error_response(FILTER_REQUIRED_MESSAGE, HTTP_BAD_REQUEST)
        filtered = _filter_with_condition(products, data[FILTER_KEY])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route(DYNAMIC_FILTER_ROUTE, methods=[POST_METHOD])
def dynamic_filter():
    try:
        data = _get_request_data()
        if not data or not _has_required_keys(data, DYNAMIC_FILTER_REQUIRED_KEYS):
            return _error_response(INVALID_FILTER_FORMAT_MESSAGE, HTTP_BAD_REQUEST)
        condition = _build_condition(
            data[FIELD_KEY], data[OPERATOR_KEY], data[VALUE_KEY]
        )
        filtered = _filter_with_condition(products, condition)
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route(SAFE_FILTER_ROUTE, methods=[POST_METHOD])
def safe_filter_endpoint():
    try:
        data = _get_request_data()
        if not data or FILTER_KEY not in data:
            return _error_response(FILTER_REQUIRED_MESSAGE, HTTP_BAD_REQUEST)
        filtered = safe_filter(products, data[FILTER_KEY])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Flask development server."""
    app.run(debug=SERVER_CONFIG.debug)


if __name__ == '__main__':
    main()
