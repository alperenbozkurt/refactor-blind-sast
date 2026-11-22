from flask import Flask, request, jsonify
import json
from enum import Enum
from typing import List, Dict, Any

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]

FILTER_REQUIRED_KEYS = ('field', 'operator', 'value')


class Operator(Enum):
    EQUAL = '=='
    NOT_EQUAL = '!='
    GREATER = '>'
    GREATER_EQUAL = '>='
    LESS = '<'
    LESS_EQUAL = '<='
    CONTAINS = 'contains'
    STARTS_WITH = 'startswith'
    ENDS_WITH = 'endswith'


_COMPARATORS = {
    Operator.EQUAL: lambda a, b: a == b,
    Operator.NOT_EQUAL: lambda a, b: a != b,
    Operator.GREATER: lambda a, b: a > b,
    Operator.GREATER_EQUAL: lambda a, b: a >= b,
    Operator.LESS: lambda a, b: a < b,
    Operator.LESS_EQUAL: lambda a, b: a <= b,
    Operator.CONTAINS: lambda a, b: str(b) in str(a),
    Operator.STARTS_WITH: lambda a, b: str(a).startswith(str(b)),
    Operator.ENDS_WITH: lambda a, b: str(a).endswith(str(b)),
}


def safe_compare(value1: Any, operator: Operator, value2: Any) -> bool:
    comparator = _COMPARATORS.get(operator)
    if comparator is None:
        return False
    try:
        return comparator(value1, value2)
    except (TypeError, ValueError):
        return False


def safe_filter_products(products: List[Dict], field: str, operator: str, value: Any) -> List[Dict]:
    try:
        op = Operator(operator)
    except ValueError:
        return []
    return [
        product for product in products
        if field in product and safe_compare(product[field], op, value)
    ]


def _error_response(message: str, status: int):
    return jsonify({'error': message}), status


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not data or not all(key in data for key in FILTER_REQUIRED_KEYS):
            return _error_response('Invalid filter format', 400)

        field = str(data['field'])
        operator = str(data['operator'])
        value = data['value']

        filtered = safe_filter_products(products, field, operator, value)
        return jsonify({
            'count': len(filtered),
            'results': filtered,
            'valid_operators': [op.value for op in Operator],
        })
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products/search', methods=['POST'])
def search_products():
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return _error_response('Search query required', 400)

        query = str(data['query']).lower()
        filtered = [
            product for product in products
            if any(
                query in str(value).lower()
                for key, value in product.items()
                if key != 'id'
            )
        ]
        return jsonify({'count': len(filtered), 'results': filtered})
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products', methods=['GET'])
def list_products():
    category = request.args.get('category')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    filtered = products
    if category:
        filtered = [p for p in filtered if p['category'] == category]
    if min_price is not None:
        filtered = [p for p in filtered if p['price'] >= min_price]
    if max_price is not None:
        filtered = [p for p in filtered if p['price'] <= max_price]

    return jsonify({'count': len(filtered), 'results': filtered})


if __name__ == '__main__':
    app.run(debug=False)
