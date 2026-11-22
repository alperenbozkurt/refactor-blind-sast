from flask import Flask, request, jsonify
import json
from enum import Enum
from typing import List, Dict, Any, Callable

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

FILTER_REQUIRED_KEYS = ['field', 'operator', 'value']
SEARCH_EXCLUDED_FIELDS = ('id',)

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_INVALID_FILTER = 'Invalid filter format'
ERROR_SEARCH_QUERY_REQUIRED = 'Search query required'

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

products = [{'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'}, {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'}, {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'}]


# --------------------------------------------------------------------------- #
# Comparison logic
# --------------------------------------------------------------------------- #

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
        return [p for p in products if field in p and safe_compare(p[field], op, value)]
    except ValueError:
        return []


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _error_response(message: str, status: int):
    return (jsonify({'error': message}), status)


def _is_valid_filter_payload(data: Any) -> bool:
    return bool(data) and all((k in data for k in FILTER_REQUIRED_KEYS))


def _valid_operator_values() -> List[str]:
    return [op.value for op in Operator]


def _matches_query(product: Dict, query: str) -> bool:
    return any((query in str(v).lower()
                for (k, v) in product.items()
                if k not in SEARCH_EXCLUDED_FIELDS))


def _results_payload(items: List[Dict]) -> Dict[str, Any]:
    return {'count': len(items), 'results': items}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not _is_valid_filter_payload(data):
            return _error_response(ERROR_INVALID_FILTER, HTTP_BAD_REQUEST)
        field = str(data['field'])
        operator = str(data['operator'])
        value = data['value']
        filtered = safe_filter_products(products, field, operator, value)
        payload = _results_payload(filtered)
        payload['valid_operators'] = _valid_operator_values()
        return jsonify(payload)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route('/api/products/search', methods=['POST'])
def search_products():
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return _error_response(ERROR_SEARCH_QUERY_REQUIRED, HTTP_BAD_REQUEST)
        query = str(data['query']).lower()
        filtered = [p for p in products if _matches_query(p, query)]
        return jsonify(_results_payload(filtered))
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


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
    return jsonify(_results_payload(filtered))


if __name__ == '__main__':
    app.run(debug=False)
