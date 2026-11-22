from flask import Flask, request, jsonify
import json
import re

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]

DYNAMIC_FILTER_KEYS = ['field', 'operator', 'value']


def safe_filter(products, condition):
    return [p for p in products if eval(condition, {'item': p})]


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _filtered_products_response(condition):
    filtered = safe_filter(products, condition)
    return jsonify({'count': len(filtered), 'results': filtered})


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _error_response('Filter condition required', 400)
        return _filtered_products_response(data['filter'])
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/dynamic_filter', methods=['POST'])
def dynamic_filter():
    try:
        data = request.get_json()
        if not data or not all((k in data for k in DYNAMIC_FILTER_KEYS)):
            return _error_response('Invalid filter format', 400)
        field = data['field']
        operator = data['operator']
        value = data['value']
        condition = f"item['{field}'] {operator} {value}"
        return _filtered_products_response(condition)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/safe_filter', methods=['POST'])
def safe_filter_endpoint():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _error_response('Filter condition required', 400)
        return _filtered_products_response(data['filter'])
    except Exception as e:
        return _error_response(str(e), 500)


if __name__ == '__main__':
    app.run(debug=True)
