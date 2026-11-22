import json
from enum import Enum
from typing import Any, Dict, List

from flask import Flask, jsonify, request

app = Flask(__name__)

products: List[Dict[str, Any]] = [
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


_COMPARISONS = {
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


def safe_compare(value1: Any, operator: Operator, value2: Any) -> bool:
    """Compare two values with the given operator, returning False on bad input."""
    try:
        compare = _COMPARISONS.get(operator)
        if compare is None:
            return False
        return compare(value1, value2)
    except (TypeError, ValueError):
        return False


def safe_filter_products(products: List[Dict], field: str, operator: str, value: Any) -> List[Dict]:
    """Return the products matching the filter, or an empty list for an invalid operator."""
    try:
        op = Operator(operator)
        return [
            product
            for product in products
            if field in product and safe_compare(product[field], op, value)
        ]
    except ValueError:
        return []


def _error_response(message: str, status_code: int):
    """Build a JSON error response paired with an HTTP status code."""
    return jsonify({'error': message}), status_code


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    """Filter products by a field, comparison operator and value."""
    try:
        data = request.get_json()
        required_fields = ('field', 'operator', 'value')
        if not data or not all(key in data for key in required_fields):
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
    """Search for products whose non-id fields contain the query text."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return _error_response('Search query required', 400)

        query = str(data['query']).lower()
        filtered = [
            product
            for product in products
            if any(
                query in str(field_value).lower()
                for field_name, field_value in product.items()
                if field_name != 'id'
            )
        ]
        return jsonify({'count': len(filtered), 'results': filtered})
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/products', methods=['GET'])
def list_products():
    """List products, optionally narrowed by category and price range."""
    category = request.args.get('category')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    filtered = products
    if category:
        filtered = [product for product in filtered if product['category'] == category]
    if min_price is not None:
        filtered = [product for product in filtered if product['price'] >= min_price]
    if max_price is not None:
        filtered = [product for product in filtered if product['price'] <= max_price]

    return jsonify({'count': len(filtered), 'results': filtered})


if __name__ == '__main__':
    app.run(debug=False)
