from functools import wraps

from flask import Flask, request, jsonify
import json
import re

# ---------------------------------------------------------------------------
# SECURITY WARNING
# ---------------------------------------------------------------------------
# The filtering logic below passes client-supplied text to ``eval`` and the app
# runs with ``debug=True``. Both allow arbitrary code execution by anyone who
# can reach the service. The behaviour is preserved here only because this
# refactor must not change it. Do not deploy as-is: replace ``eval`` with a
# real expression parser or a structured filter (field/operator/value checked
# against an allow-list), and disable debug mode.
# ---------------------------------------------------------------------------

# --- Constants --------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_FILTER_REQUIRED = 'Filter condition required'
ERROR_INVALID_FILTER_FORMAT = 'Invalid filter format'

FILTER_KEY = 'filter'
DYNAMIC_FILTER_KEYS = ('field', 'operator', 'value')
EVAL_ITEM_NAME = 'item'

ROUTE_FILTER = '/api/products/filter'
ROUTE_DYNAMIC_FILTER = '/api/products/dynamic_filter'
ROUTE_SAFE_FILTER = '/api/products/safe_filter'
POST_METHODS = ['POST']


# --- Configuration ----------------------------------------------------------

class AppConfig:
    """Runtime configuration for the development server."""
    DEBUG = True


# --- Application and data ---------------------------------------------------

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]


# --- Filtering helpers ------------------------------------------------------

def _matches(condition, product):
    """Evaluate ``condition`` against a single product (see security warning)."""
    return eval(condition, {EVAL_ITEM_NAME: product})


def _apply_filter(items, condition):
    """Return the items for which ``condition`` evaluates truthy."""
    return [p for p in items if _matches(condition, p)]


def safe_filter(products, condition):
    return _apply_filter(products, condition)


def _build_dynamic_condition(field, operator, value):
    """Build a condition string from field/operator/value parts."""
    return f"item['{field}'] {operator} {value}"


# --- Request / response helpers ---------------------------------------------

def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _results_response(filtered):
    return jsonify({'count': len(filtered), 'results': filtered})


def _has_filter(data):
    return bool(data) and FILTER_KEY in data


def _has_dynamic_filter_fields(data):
    return bool(data) and all((k in data for k in DYNAMIC_FILTER_KEYS))


def _handle_errors(view):
    """Convert any unhandled exception in a view into a 500 JSON response."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except Exception as e:
            return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)
    return wrapper


# --- Routes -----------------------------------------------------------------

@app.route(ROUTE_FILTER, methods=POST_METHODS)
@_handle_errors
def filter_products():
    data = request.get_json()
    if not _has_filter(data):
        return _error_response(ERROR_FILTER_REQUIRED, HTTP_BAD_REQUEST)
    filtered = _apply_filter(products, data[FILTER_KEY])
    return _results_response(filtered)


@app.route(ROUTE_DYNAMIC_FILTER, methods=POST_METHODS)
@_handle_errors
def dynamic_filter():
    data = request.get_json()
    if not _has_dynamic_filter_fields(data):
        return _error_response(ERROR_INVALID_FILTER_FORMAT, HTTP_BAD_REQUEST)
    condition = _build_dynamic_condition(
        data['field'], data['operator'], data['value']
    )
    filtered = _apply_filter(products, condition)
    return _results_response(filtered)


@app.route(ROUTE_SAFE_FILTER, methods=POST_METHODS)
@_handle_errors
def safe_filter_endpoint():
    data = request.get_json()
    if not _has_filter(data):
        return _error_response(ERROR_FILTER_REQUIRED, HTTP_BAD_REQUEST)
    filtered = safe_filter(products, data[FILTER_KEY])
    return _results_response(filtered)


if __name__ == '__main__':
    app.run(debug=AppConfig.DEBUG)
