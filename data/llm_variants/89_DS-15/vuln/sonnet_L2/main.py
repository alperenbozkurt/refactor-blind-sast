import json

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

HTTP_GET = 'GET'
HTTP_POST = 'POST'

STATUS_OK = 200
STATUS_UNAUTHORIZED = 401
STATUS_METHOD_NOT_ALLOWED = 405

DEFAULT_ORDER_QUANTITY = 1

# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #

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

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #

CREATE_PRODUCTS_TABLE_SQL = '''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT NOT NULL
            )
        '''

CREATE_USERS_TABLE_SQL = '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL
            )
        '''

CREATE_ORDERS_TABLE_SQL = '''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        '''

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

# The search term is passed as a bound parameter (not interpolated into the
# SQL text) so that user input can never alter the structure of the query.
SEARCH_PRODUCTS_SQL = (
    'SELECT * FROM products WHERE name LIKE %s OR category LIKE %s'
)

SELECT_USER_ORDERS_SQL = (
    'SELECT o.id, p.name, p.price, o.quantity \n'
    '                   FROM orders o JOIN products p ON o.product_id = p.id \n'
    '                   WHERE o.user_id = %s'
)

SCHEMA_STATEMENTS = (
    CREATE_PRODUCTS_TABLE_SQL,
    CREATE_USERS_TABLE_SQL,
    CREATE_ORDERS_TABLE_SQL,
)


# --------------------------------------------------------------------------- #
# Response helpers
# --------------------------------------------------------------------------- #

def _method_not_allowed():
    return JsonResponse(
        {'status': 'error', 'message': 'Method not allowed'},
        status=STATUS_METHOD_NOT_ALLOWED,
    )


def _invalid_credentials():
    return JsonResponse(
        {'status': 'error', 'message': 'Invalid credentials'},
        status=STATUS_UNAUTHORIZED,
    )


# --------------------------------------------------------------------------- #
# Row serializers
# --------------------------------------------------------------------------- #

def _product_row_to_dict(row):
    return {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}


def _order_row_to_dict(row):
    return {
        'order_id': row[0],
        'product_name': row[1],
        'price': row[2],
        'quantity': row[3],
    }


# --------------------------------------------------------------------------- #
# Database initialisation
# --------------------------------------------------------------------------- #

def _create_schema(cursor):
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _table_is_empty(cursor, count_sql):
    return not cursor.execute(count_sql).fetchone()[0]


def _seed_products(cursor):
    if _table_is_empty(cursor, COUNT_PRODUCTS_SQL):
        for product in products:
            cursor.execute(
                INSERT_PRODUCT_SQL,
                [product['id'], product['name'], product['price'], product['category']],
            )


def _seed_users(cursor):
    if _table_is_empty(cursor, COUNT_USERS_SQL):
        for user in users:
            cursor.execute(
                INSERT_USER_SQL,
                [user['id'], user['username'], user['password'], user['is_admin']],
            )


def init_db():
    with connection.cursor() as cursor:
        _create_schema(cursor)
        _seed_products(cursor)
        _seed_users(cursor)


# --------------------------------------------------------------------------- #
# Data access helpers
# --------------------------------------------------------------------------- #

def _find_user(cursor, username, password):
    cursor.execute(SELECT_USER_BY_CREDENTIALS_SQL, [username, password])
    return cursor.fetchone()


def _find_products(cursor, search_term):
    pattern = f'%{search_term}%'
    cursor.execute(SEARCH_PRODUCTS_SQL, [pattern, pattern])
    return cursor.fetchall()


def _insert_order(cursor, user_id, product_id, quantity):
    cursor.execute(INSERT_ORDER_SQL, [user_id, product_id, quantity])


def _find_orders_for_user(cursor, user_id):
    cursor.execute(SELECT_USER_ORDERS_SQL, [user_id])
    return cursor.fetchall()


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

@csrf_exempt
def user_login(request):
    if request.method == HTTP_POST:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        with connection.cursor() as cursor:
            user = _find_user(cursor, username, password)
            if user:
                return JsonResponse(
                    {'status': 'success', 'user_id': user[0], 'is_admin': user[3]}
                )
        return _invalid_credentials()
    return _method_not_allowed()


@csrf_exempt
def search_products(request):
    if request.method == HTTP_GET:
        search_term = request.GET.get('q', '')
        with connection.cursor() as cursor:
            results = _find_products(cursor, search_term)
            products_list = [_product_row_to_dict(row) for row in results]
            return JsonResponse({'products': products_list})
    return _method_not_allowed()


@csrf_exempt
def create_order(request):
    if request.method == HTTP_POST:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', DEFAULT_ORDER_QUANTITY)
        with connection.cursor() as cursor:
            _insert_order(cursor, user_id, product_id, quantity)
            return JsonResponse({'status': 'success', 'message': 'Order created'})
    return _method_not_allowed()


@csrf_exempt
def get_user_orders(request, user_id):
    if request.method == HTTP_GET:
        with connection.cursor() as cursor:
            rows = _find_orders_for_user(cursor, user_id)
            orders_list = [_order_row_to_dict(row) for row in rows]
            return JsonResponse({'orders': orders_list})
    return _method_not_allowed()


init_db()
