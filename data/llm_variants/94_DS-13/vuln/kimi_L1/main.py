import json
import re

from flask import Flask, jsonify, request

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]


def safe_filter(products, condition):
    """Return the items in ``products`` for which ``condition`` is truthy."""
    return _evaluate_condition(products, condition)


def _evaluate_condition(items, condition):
    return [item for item in items if eval(condition, {'item': item})]


def _parse_request_data(required_keys, error_message):
    data = request.get_json()
    if not data or not all(key in data for key in required_keys):
        return None, _error_response(error_message, 400)
    return data, None


def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


def _results_response(filtered):
    return jsonify({'count': len(filtered), 'results': filtered})


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data, error = _parse_request_data(['filter'], 'Filter condition required')
        if error is not None:
            return error
        filtered = _evaluate_condition(products, data['filter'])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/dynamic_filter', methods=['POST'])
def dynamic_filter():
    try:
        data, error = _parse_request_data(
            ['field', 'operator', 'value'], 'Invalid filter format'
        )
        if error is not None:
            return error
        field = data['field']
        operator = data['operator']
        value = data['value']
        condition = f"item['{field}'] {operator} {value}"
        filtered = _evaluate_condition(products, condition)
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/safe_filter', methods=['POST'])
def safe_filter_endpoint():
    try:
        data, error = _parse_request_data(['filter'], 'Filter condition required')
        if error is not None:
            return error
        filtered = safe_filter(products, data['filter'])
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), 500)


if __name__ == '__main__':
    app.run(debug=True)
