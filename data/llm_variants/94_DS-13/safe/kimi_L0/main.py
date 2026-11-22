import json
from enum import Enum
from typing import Any, Callable, Dict, List

from flask import Flask, jsonify, request

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]


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


_COMPARATORS: Dict[Operator, Callable[[Any, Any], bool]] = {
    Operator.EQUAL: lambda value1, value2: value1 == value2,
    Operator.NOT_EQUAL: lambda value1, value2: value1 != value2,
    Operator.GREATER: lambda value1, value2: value1 > value2,
    Operator.GREATER_EQUAL: lambda value1, value2: value1 >= value2,
    Operator.LESS: lambda value1, value2: value1 < value2,
    Operator.LESS_EQUAL: lambda value1, value2: value1 <= value2,
    Operator.CONTAINS: lambda value1, value2: str(value2) in str(value1),
    Operator.STARTS_WITH: lambda value1, value2: str(value1).startswith(str(value2)),
    Operator.ENDS_WITH: lambda value1, value2: str(value1).endswith(str(value2)),
}

_REQUIRED_FILTER_KEYS = ('field', 'operator', 'value')


def safe_compare(value1: Any, operator: Operator, value2: Any) -> bool:
    try:
        comparator = _COMPARATORS.get(operator)
        if comparator is None:
            return False
        return comparator(value1, value2)
    except (TypeError, ValueError):
        return False


def safe_filter_products(products: List[Dict], field: str, operator: str, value: Any) -> List[Dict]:
    try:
        op = Operator(operator)
    except ValueError:
        return []
    return [p for p in products if field in p and safe_compare(p[field], op, value)]


def _products_response(filtered: List[Dict], **extra: Any):
    return jsonify({'count': len(filtered), 'results': filtered, **extra})


def _error_response(message: str, status: int):
    return jsonify({'error': message}), status


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in _REQUIRED_FILTER_KEYS):
            return _error_response('Invalid filter format', 400)
        field = str(data['field'])
        operator = str(data['operator'])
        value = data['value']
        filtered = safe_filter_products(products, field, operator, value)
        return _products_response(filtered, valid_operators=[op.value for op in Operator])
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
            p
            for p in products
            if any(query in str(v).lower() for k, v in p.items() if k != 'id')
        ]
        return _products_response(filtered)
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
    return _products_response(filtered)


if __name__ == '__main__':
    app.run(debug=False)
