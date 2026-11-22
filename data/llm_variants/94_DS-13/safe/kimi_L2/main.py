"""Product catalogue API.

A small Flask service that exposes endpoints to list, search and filter an
in-memory collection of products.
"""

import json
from enum import Enum
from operator import eq, ge, gt, le, lt, ne
from typing import Any, Callable, Dict, List, Tuple

from flask import Flask, Response, jsonify, request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class ProductField:
    """Names of the attributes stored on a product record."""

    ID = 'id'
    NAME = 'name'
    PRICE = 'price'
    CATEGORY = 'category'


class Routes:
    """URL paths exposed by the service."""

    LIST_PRODUCTS = '/api/products'
    FILTER_PRODUCTS = '/api/products/filter'
    SEARCH_PRODUCTS = '/api/products/search'


# Keys that must be present in the body of a filter request.
FILTER_REQUIRED_KEYS = ('field', 'operator', 'value')

# Client facing error messages.
ERR_INVALID_FILTER = 'Invalid filter format'
ERR_SEARCH_QUERY_REQUIRED = 'Search query required'

# HTTP status codes used by the API.
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

app = Flask(__name__)

products = [
    {
        ProductField.ID: 1,
        ProductField.NAME: 'Laptop',
        ProductField.PRICE: 999.99,
        ProductField.CATEGORY: 'electronics',
    },
    {
        ProductField.ID: 2,
        ProductField.NAME: 'Smartphone',
        ProductField.PRICE: 699.99,
        ProductField.CATEGORY: 'electronics',
    },
    {
        ProductField.ID: 3,
        ProductField.NAME: 'Desk Chair',
        ProductField.PRICE: 199.99,
        ProductField.CATEGORY: 'furniture',
    },
]


# ---------------------------------------------------------------------------
# Filtering primitives
# ---------------------------------------------------------------------------

class Operator(Enum):
    """Comparison operators supported by the filter endpoint."""

    EQUAL = '=='
    NOT_EQUAL = '!='
    GREATER = '>'
    GREATER_EQUAL = '>='
    LESS = '<'
    LESS_EQUAL = '<='
    CONTAINS = 'contains'
    STARTS_WITH = 'startswith'
    ENDS_WITH = 'endswith'


def _contains(value1: Any, value2: Any) -> bool:
    return str(value2) in str(value1)


def _starts_with(value1: Any, value2: Any) -> bool:
    return str(value1).startswith(str(value2))


def _ends_with(value1: Any, value2: Any) -> bool:
    return str(value1).endswith(str(value2))


_COMPARATORS: Dict[Operator, Callable[[Any, Any], bool]] = {
    Operator.EQUAL: eq,
    Operator.NOT_EQUAL: ne,
    Operator.GREATER: gt,
    Operator.GREATER_EQUAL: ge,
    Operator.LESS: lt,
    Operator.LESS_EQUAL: le,
    Operator.CONTAINS: _contains,
    Operator.STARTS_WITH: _starts_with,
    Operator.ENDS_WITH: _ends_with,
}


def safe_compare(value1: Any, operator: Operator, value2: Any) -> bool:
    """Compare ``value1`` and ``value2`` using ``operator``.

    Returns ``False`` for unknown operators and for comparisons that are not
    meaningful for the given values (``TypeError``/``ValueError``).
    """
    try:
        comparator = _COMPARATORS.get(operator)
        if comparator is None:
            return False
        return comparator(value1, value2)
    except (TypeError, ValueError):
        return False


def _matches_filter(product: Dict, field: str, op: Operator, value: Any) -> bool:
    return field in product and safe_compare(product[field], op, value)


def safe_filter_products(products: List[Dict], field: str, operator: str, value: Any) -> List[Dict]:
    """Return the products whose ``field`` matches ``operator``/``value``.

    Returns an empty list when ``operator`` is not a valid ``Operator``.
    """
    try:
        op = Operator(operator)
    except ValueError:
        return []
    return [p for p in products if _matches_filter(p, field, op, value)]


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _error_response(message: str, status: int) -> Tuple[Response, int]:
    return jsonify({'error': message}), status


def _results_response(filtered: List[Dict]) -> Response:
    return jsonify({'count': len(filtered), 'results': filtered})


def _valid_operators() -> List[str]:
    return [op.value for op in Operator]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(Routes.FILTER_PRODUCTS, methods=['POST'])
def filter_products():
    """Filter products by an arbitrary field, operator and value."""
    try:
        data = request.get_json()
        if not data or not all(k in data for k in FILTER_REQUIRED_KEYS):
            return _error_response(ERR_INVALID_FILTER, HTTP_BAD_REQUEST)

        field = str(data['field'])
        operator = str(data['operator'])
        value = data['value']

        filtered = safe_filter_products(products, field, operator, value)
        return jsonify({
            'count': len(filtered),
            'results': filtered,
            'valid_operators': _valid_operators(),
        })
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


def _matches_query(product: Dict, query: str) -> bool:
    """Return True when ``query`` occurs in any product field but the id."""
    return any(
        query in str(value).lower()
        for key, value in product.items()
        if key != ProductField.ID
    )


@app.route(Routes.SEARCH_PRODUCTS, methods=['POST'])
def search_products():
    """Search products for a free-text query across all fields but the id."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return _error_response(ERR_SEARCH_QUERY_REQUIRED, HTTP_BAD_REQUEST)

        query = str(data['query']).lower()
        filtered = [p for p in products if _matches_query(p, query)]
        return _results_response(filtered)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


def _filter_by_category(items: List[Dict], category: str) -> List[Dict]:
    return [p for p in items if p[ProductField.CATEGORY] == category]


def _filter_by_min_price(items: List[Dict], min_price: float) -> List[Dict]:
    return [p for p in items if p[ProductField.PRICE] >= min_price]


def _filter_by_max_price(items: List[Dict], max_price: float) -> List[Dict]:
    return [p for p in items if p[ProductField.PRICE] <= max_price]


@app.route(Routes.LIST_PRODUCTS, methods=['GET'])
def list_products():
    """List products, optionally narrowed by category and price range."""
    category = request.args.get('category')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    filtered = products
    if category:
        filtered = _filter_by_category(filtered, category)
    if min_price is not None:
        filtered = _filter_by_min_price(filtered, min_price)
    if max_price is not None:
        filtered = _filter_by_max_price(filtered, max_price)
    return _results_response(filtered)


if __name__ == '__main__':
    app.run(debug=False)
