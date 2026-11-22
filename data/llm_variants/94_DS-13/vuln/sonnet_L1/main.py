from flask import Flask, request, jsonify
import json
import re

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]

DYNAMIC_FILTER_FIELDS = ['field', 'operator', 'value']


def _apply_condition(items, condition):
    """Return the items for which the evaluated condition is truthy.

    The condition is evaluated with ``eval`` and exposes each product as
    ``item`` (behaviour intentionally unchanged).
    """
    return [p for p in items if eval(condition, {'item': p})]


def _results_response(filtered):
    return jsonify({'count': len(filtered), 'results': filtered})


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _missing_filter_response():
    return _error_response('Filter condition required', 400)


def safe_filter(products, condition):
    return _apply_condition(products, condition)


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _missing_filter_response()
        filtered = _apply_condition(products, data['filter'])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/dynamic_filter', methods=['POST'])
def dynamic_filter():
    try:
        data = request.get_json()
        if not data or not all((k in data for k in DYNAMIC_FILTER_FIELDS)):
            return _error_response('Invalid filter format', 400)
        field = data['field']
        operator = data['operator']
        value = data['value']
        condition = f"item['{field}'] {operator} {value}"
        filtered = _apply_condition(products, condition)
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/safe_filter', methods=['POST'])
def safe_filter_endpoint():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _missing_filter_response()
        filtered = safe_filter(products, data['filter'])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


if __name__ == '__main__':
    app.run(debug=True)
