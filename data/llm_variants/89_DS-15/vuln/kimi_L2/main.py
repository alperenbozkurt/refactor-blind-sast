"""Product catalog and order API views.

The module keeps a thin HTTP layer: each view validates the request method,
parses the payload and delegates persistence work to small data-access
helpers.  SQL statements, response payloads and default values are
centralised as named constants so they can be maintained in one place.
"""

import json

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

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
# SQL statements
# ---------------------------------------------------------------------------

CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category TEXT NOT NULL
    )
"""

CREATE_USERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin BOOLEAN NOT NULL
    )
"""

CREATE_ORDERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
"""

COUNT_PRODUCTS_SQL = 'SELECT COUNT(*) FROM products'
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

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

SEARCH_PRODUCTS_SQL_TEMPLATE = (
    "SELECT * FROM products WHERE name LIKE '%{search_term}%'"
    " OR category LIKE '%{search_term}%'"
)

SELECT_USER_ORDERS_SQL = (
    'SELECT o.id, p.name, p.price, o.quantity '
    'FROM orders o JOIN products p ON o.product_id = p.id '
    'WHERE o.user_id = %s'
)

# ---------------------------------------------------------------------------
# HTTP and response constants
# ---------------------------------------------------------------------------

HTTP_GET = 'GET'
HTTP_POST = 'POST'

STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'

MESSAGE_INVALID_CREDENTIALS = 'Invalid credentials'
MESSAGE_METHOD_NOT_ALLOWED = 'Method not allowed'
MESSAGE_ORDER_CREATED = 'Order created'

HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_METHOD_NOT_ALLOWED = 405

DEFAULT_SEARCH_TERM = ''
DEFAULT_ORDER_QUANTITY = 1


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _json_error(message, status):
    """Build a consistent error JSON response."""
    return JsonResponse({'status': STATUS_ERROR, 'message': message}, status=status)


def _method_not_allowed_response():
    """Return the standard 405 response used by every view."""
    return _json_error(MESSAGE_METHOD_NOT_ALLOWED, HTTP_STATUS_METHOD_NOT_ALLOWED)


def _parse_json_body(request):
    """Decode the JSON request body."""
    return json.loads(request.body)


# ---------------------------------------------------------------------------
# Row serializers
# ---------------------------------------------------------------------------

def _product_row_to_dict(row):
    return {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}


def _order_row_to_dict(row):
    return {
        'order_id': row[0],
        'product_name': row[1],
        'price': row[2],
        'quantity': row[3],
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _create_tables(cursor):
    cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute(CREATE_ORDERS_TABLE_SQL)


def _table_is_empty(cursor, count_sql):
    return not cursor.execute(count_sql).fetchone()[0]


def _product_insert_params(product):
    return [product['id'], product['name'], product['price'], product['category']]


def _user_insert_params(user):
    return [user['id'], user['username'], user['password'], user['is_admin']]


def _seed_products(cursor):
    if _table_is_empty(cursor, COUNT_PRODUCTS_SQL):
        for product in products:
            cursor.execute(INSERT_PRODUCT_SQL, _product_insert_params(product))


def _seed_users(cursor):
    if _table_is_empty(cursor, COUNT_USERS_SQL):
        for user in users:
            cursor.execute(INSERT_USER_SQL, _user_insert_params(user))


def _fetch_user_by_credentials(username, password):
    with connection.cursor() as cursor:
        cursor.execute(SELECT_USER_BY_CREDENTIALS_SQL, [username, password])
        return cursor.fetchone()


def _fetch_products_matching(search_term):
    with connection.cursor() as cursor:
        query = SEARCH_PRODUCTS_SQL_TEMPLATE.format(search_term=search_term)
        cursor.execute(query)
        return cursor.fetchall()


def _insert_order(user_id, product_id, quantity):
    with connection.cursor() as cursor:
        cursor.execute(INSERT_ORDER_SQL, [user_id, product_id, quantity])


def _fetch_orders_for_user(user_id):
    with connection.cursor() as cursor:
        cursor.execute(SELECT_USER_ORDERS_SQL, [user_id])
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db():
    with connection.cursor() as cursor:
        _create_tables(cursor)
        _seed_products(cursor)
        _seed_users(cursor)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@csrf_exempt
def user_login(request):
    if request.method != HTTP_POST:
        return _method_not_allowed_response()
    data = _parse_json_body(request)
    user = _fetch_user_by_credentials(data.get('username'), data.get('password'))
    if user:
        return JsonResponse({
            'status': STATUS_SUCCESS,
            'user_id': user[0],
            'is_admin': user[3],
        })
    return _json_error(MESSAGE_INVALID_CREDENTIALS, HTTP_STATUS_UNAUTHORIZED)


@csrf_exempt
def search_products(request):
    if request.method != HTTP_GET:
        return _method_not_allowed_response()
    search_term = request.GET.get('q', DEFAULT_SEARCH_TERM)
    products_list = [
        _product_row_to_dict(row)
        for row in _fetch_products_matching(search_term)
    ]
    return JsonResponse({'products': products_list})


@csrf_exempt
def create_order(request):
    if request.method != HTTP_POST:
        return _method_not_allowed_response()
    data = _parse_json_body(request)
    _insert_order(
        data.get('user_id'),
        data.get('product_id'),
        data.get('quantity', DEFAULT_ORDER_QUANTITY),
    )
    return JsonResponse({'status': STATUS_SUCCESS, 'message': MESSAGE_ORDER_CREATED})


@csrf_exempt
def get_user_orders(request, user_id):
    if request.method != HTTP_GET:
        return _method_not_allowed_response()
    orders_list = [
        _order_row_to_dict(row)
        for row in _fetch_orders_for_user(user_id)
    ]
    return JsonResponse({'orders': orders_list})


init_db()
