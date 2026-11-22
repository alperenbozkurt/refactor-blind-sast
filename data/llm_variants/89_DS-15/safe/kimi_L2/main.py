"""JSON API views for a simple product catalog with order management.

The public interface of this module (the ``products``, ``users`` and
``orders`` collections, ``init_db`` and the four view functions) is kept
intact, while the implementation is organised into named constants, small
helper functions and repository classes that group the SQL per table.

The database schema is created and seeded at import time via ``init_db()``.
"""

import json

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404  # noqa: F401  (kept for compatibility)
from django.views.decorators.csrf import csrf_exempt

# ---------------------------------------------------------------------------
# HTTP / API constants
# ---------------------------------------------------------------------------

HTTP_METHOD_GET = 'GET'
HTTP_METHOD_POST = 'POST'

HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_METHOD_NOT_ALLOWED = 405

STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'

MESSAGE_INVALID_CREDENTIALS = 'Invalid credentials'
MESSAGE_METHOD_NOT_ALLOWED = 'Method not allowed'
MESSAGE_ORDER_CREATED = 'Order created'

DEFAULT_SEARCH_TERM = ''
DEFAULT_ORDER_QUANTITY = 1

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

PRODUCTS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT NOT NULL
)
"""

USERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL
)
"""

ORDERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
)
"""

INSERT_PRODUCT_SQL = (
    'INSERT INTO products (id, name, price, category) VALUES (%s, %s, %s, %s)'
)
INSERT_USER_SQL = (
    'INSERT INTO users (id, username, password, is_admin) VALUES (%s, %s, %s, %s)'
)
INSERT_ORDER_SQL = (
    'INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)'
)

SELECT_USER_BY_CREDENTIALS_SQL = (
    'SELECT * FROM users WHERE username = %s AND password = %s'
)
SEARCH_PRODUCTS_SQL = (
    'SELECT * FROM products WHERE name LIKE %s OR category LIKE %s'
)
SELECT_USER_ORDERS_SQL = """
SELECT o.id, p.name, p.price, o.quantity
FROM orders o JOIN products p ON o.product_id = p.id
WHERE o.user_id = %s
"""

COUNT_ROWS_SQL_TEMPLATE = 'SELECT COUNT(*) FROM {table_name}'

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'Electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'Electronics'},
    {'id': 3, 'name': 'Headphones', 'price': 149.99, 'category': 'Electronics'},
    {'id': 4, 'name': 'T-shirt', 'price': 19.99, 'category': 'Clothing'},
]

users = [
    {'id': 1, 'username': 'admin', 'password': 'admin123', 'is_admin': True},
    {'id': 2, 'username': 'user1', 'password': 'password1', 'is_admin': False},
]

orders = []

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _parse_json_body(request):
    """Decode the JSON body of the given request."""
    return json.loads(request.body)


def _error_response(message, status):
    return JsonResponse({'status': STATUS_ERROR, 'message': message}, status=status)


def _method_not_allowed_response():
    return _error_response(MESSAGE_METHOD_NOT_ALLOWED, HTTP_STATUS_METHOD_NOT_ALLOWED)


def _product_to_dict(row):
    return {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}


def _user_order_to_dict(row):
    return {'order_id': row[0], 'product_name': row[1], 'price': row[2], 'quantity': row[3]}


def _product_insert_params(product):
    return [product['id'], product['name'], product['price'], product['category']]


def _user_insert_params(user):
    return [user['id'], user['username'], user['password'], user['is_admin']]


def _table_is_empty(cursor, table_name):
    cursor.execute(COUNT_ROWS_SQL_TEMPLATE.format(table_name=table_name))
    return not cursor.fetchone()[0]


def _seed_if_empty(cursor, table_name, rows, insert_sql, to_insert_params):
    """Insert ``rows`` into ``table_name`` only when the table has no data."""
    if not _table_is_empty(cursor, table_name):
        return
    for row in rows:
        cursor.execute(insert_sql, to_insert_params(row))


# ---------------------------------------------------------------------------
# Repositories (group the SQL per table)
# ---------------------------------------------------------------------------


class ProductRepository:
    """Data access for the ``products`` table."""

    TABLE_NAME = 'products'

    @classmethod
    def create_table(cls, cursor):
        cursor.execute(PRODUCTS_TABLE_DDL)

    @classmethod
    def seed(cls, cursor, seed_rows):
        _seed_if_empty(cursor, cls.TABLE_NAME, seed_rows, INSERT_PRODUCT_SQL, _product_insert_params)

    @staticmethod
    def search(cursor, search_term):
        search_pattern = f'%{search_term}%'
        cursor.execute(SEARCH_PRODUCTS_SQL, [search_pattern, search_pattern])
        return [_product_to_dict(row) for row in cursor.fetchall()]


class UserRepository:
    """Data access for the ``users`` table."""

    TABLE_NAME = 'users'

    @classmethod
    def create_table(cls, cursor):
        cursor.execute(USERS_TABLE_DDL)

    @classmethod
    def seed(cls, cursor, seed_rows):
        _seed_if_empty(cursor, cls.TABLE_NAME, seed_rows, INSERT_USER_SQL, _user_insert_params)

    @staticmethod
    def find_by_credentials(cursor, username, password):
        cursor.execute(SELECT_USER_BY_CREDENTIALS_SQL, [username, password])
        return cursor.fetchone()


class OrderRepository:
    """Data access for the ``orders`` table."""

    TABLE_NAME = 'orders'

    @classmethod
    def create_table(cls, cursor):
        cursor.execute(ORDERS_TABLE_DDL)

    @staticmethod
    def create(cursor, user_id, product_id, quantity):
        cursor.execute(INSERT_ORDER_SQL, [user_id, product_id, quantity])

    @staticmethod
    def list_for_user(cursor, user_id):
        cursor.execute(SELECT_USER_ORDERS_SQL, [user_id])
        return [_user_order_to_dict(row) for row in cursor.fetchall()]


_REPOSITORIES = (ProductRepository, UserRepository, OrderRepository)


def init_db():
    """Create the schema (if needed) and seed the products and users tables."""
    with connection.cursor() as cursor:
        for repository in _REPOSITORIES:
            repository.create_table(cursor)
        ProductRepository.seed(cursor, products)
        UserRepository.seed(cursor, users)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@csrf_exempt
def user_login(request):
    if request.method != HTTP_METHOD_POST:
        return _method_not_allowed_response()

    credentials = _parse_json_body(request)
    with connection.cursor() as cursor:
        user = UserRepository.find_by_credentials(
            cursor,
            username=credentials.get('username'),
            password=credentials.get('password'),
        )
        if user:
            return JsonResponse({'status': STATUS_SUCCESS, 'user_id': user[0], 'is_admin': user[3]})
    return _error_response(MESSAGE_INVALID_CREDENTIALS, HTTP_STATUS_UNAUTHORIZED)


@csrf_exempt
def search_products(request):
    if request.method != HTTP_METHOD_GET:
        return _method_not_allowed_response()

    search_term = request.GET.get('q', DEFAULT_SEARCH_TERM)
    with connection.cursor() as cursor:
        products_list = ProductRepository.search(cursor, search_term)
    return JsonResponse({'products': products_list})


@csrf_exempt
def create_order(request):
    if request.method != HTTP_METHOD_POST:
        return _method_not_allowed_response()

    order_data = _parse_json_body(request)
    with connection.cursor() as cursor:
        OrderRepository.create(
            cursor,
            user_id=order_data.get('user_id'),
            product_id=order_data.get('product_id'),
            quantity=order_data.get('quantity', DEFAULT_ORDER_QUANTITY),
        )
    return JsonResponse({'status': STATUS_SUCCESS, 'message': MESSAGE_ORDER_CREATED})


@csrf_exempt
def get_user_orders(request, user_id):
    if request.method != HTTP_METHOD_GET:
        return _method_not_allowed_response()

    with connection.cursor() as cursor:
        orders_list = OrderRepository.list_for_user(cursor, user_id)
    return JsonResponse({'orders': orders_list})


init_db()
