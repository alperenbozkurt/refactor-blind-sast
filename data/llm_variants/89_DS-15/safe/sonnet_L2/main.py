import json

from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HTTP_METHOD_GET = 'GET'
HTTP_METHOD_POST = 'POST'

STATUS_UNAUTHORIZED = 401
STATUS_METHOD_NOT_ALLOWED = 405

DEFAULT_ORDER_QUANTITY = 1

CREATE_PRODUCTS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS products (\n                id INTEGER PRIMARY KEY,\n                name TEXT NOT NULL,\n                price REAL NOT NULL,\n                category TEXT NOT NULL\n            )\n        '
CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY,\n                username TEXT UNIQUE NOT NULL,\n                password TEXT NOT NULL,\n                is_admin BOOLEAN NOT NULL\n            )\n        '
CREATE_ORDERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS orders (\n                id INTEGER PRIMARY KEY,\n                user_id INTEGER NOT NULL,\n                product_id INTEGER NOT NULL,\n                quantity INTEGER NOT NULL,\n                FOREIGN KEY (user_id) REFERENCES users(id),\n                FOREIGN KEY (product_id) REFERENCES products(id)\n            )\n        '
SCHEMA_STATEMENTS = (
    CREATE_PRODUCTS_TABLE_SQL,
    CREATE_USERS_TABLE_SQL,
    CREATE_ORDERS_TABLE_SQL,
)

COUNT_PRODUCTS_SQL = 'SELECT COUNT(*) FROM products'
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_PRODUCT_SQL = 'INSERT INTO products (id, name, price, category) VALUES (%s, %s, %s, %s)'
INSERT_USER_SQL = 'INSERT INTO users (id, username, password, is_admin) VALUES (%s, %s, %s, %s)'
SELECT_USER_BY_CREDENTIALS_SQL = 'SELECT * FROM users WHERE username = %s AND password = %s'
SEARCH_PRODUCTS_SQL = 'SELECT * FROM products WHERE name LIKE %s OR category LIKE %s'
INSERT_ORDER_SQL = 'INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)'
SELECT_USER_ORDERS_SQL = 'SELECT o.id, p.name, p.price, o.quantity \n                   FROM orders o JOIN products p ON o.product_id = p.id \n                   WHERE o.user_id = %s'

# ---------------------------------------------------------------------------
# Seed data (module-level names preserved)
# ---------------------------------------------------------------------------
products = [{'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'Electronics'}, {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'Electronics'}, {'id': 3, 'name': 'Headphones', 'price': 149.99, 'category': 'Electronics'}, {'id': 4, 'name': 'T-shirt', 'price': 19.99, 'category': 'Clothing'}]
users = [{'id': 1, 'username': 'admin', 'password': 'admin123', 'is_admin': True}, {'id': 2, 'username': 'user1', 'password': 'password1', 'is_admin': False}]
orders = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _method_not_allowed():
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=STATUS_METHOD_NOT_ALLOWED)


def _table_is_empty(cursor, count_sql):
    return not cursor.execute(count_sql).fetchone()[0]


def _seed_products(cursor):
    for product in products:
        cursor.execute(INSERT_PRODUCT_SQL, [product['id'], product['name'], product['price'], product['category']])


def _seed_users(cursor):
    for user in users:
        cursor.execute(INSERT_USER_SQL, [user['id'], user['username'], user['password'], user['is_admin']])


def _product_row_to_dict(row):
    return {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}


def _order_row_to_dict(row):
    return {'order_id': row[0], 'product_name': row[1], 'price': row[2], 'quantity': row[3]}


def _like_pattern(term):
    return f'%{term}%'


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------
def init_db():
    with connection.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        if _table_is_empty(cursor, COUNT_PRODUCTS_SQL):
            _seed_products(cursor)
        if _table_is_empty(cursor, COUNT_USERS_SQL):
            _seed_users(cursor)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@csrf_exempt
def user_login(request):
    if request.method == HTTP_METHOD_POST:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        with connection.cursor() as cursor:
            cursor.execute(SELECT_USER_BY_CREDENTIALS_SQL, [username, password])
            user = cursor.fetchone()
            if user:
                return JsonResponse({'status': 'success', 'user_id': user[0], 'is_admin': user[3]})
        return JsonResponse({'status': 'error', 'message': 'Invalid credentials'}, status=STATUS_UNAUTHORIZED)
    return _method_not_allowed()


@csrf_exempt
def search_products(request):
    if request.method == HTTP_METHOD_GET:
        search_term = request.GET.get('q', '')
        with connection.cursor() as cursor:
            search_pattern = _like_pattern(search_term)
            cursor.execute(SEARCH_PRODUCTS_SQL, [search_pattern, search_pattern])
            results = cursor.fetchall()
            products_list = [_product_row_to_dict(row) for row in results]
            return JsonResponse({'products': products_list})
    return _method_not_allowed()


@csrf_exempt
def create_order(request):
    if request.method == HTTP_METHOD_POST:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', DEFAULT_ORDER_QUANTITY)
        with connection.cursor() as cursor:
            cursor.execute(INSERT_ORDER_SQL, [user_id, product_id, quantity])
            return JsonResponse({'status': 'success', 'message': 'Order created'})
    return _method_not_allowed()


@csrf_exempt
def get_user_orders(request, user_id):
    if request.method == HTTP_METHOD_GET:
        with connection.cursor() as cursor:
            cursor.execute(SELECT_USER_ORDERS_SQL, [user_id])
            rows = cursor.fetchall()
            orders_list = [_order_row_to_dict(row) for row in rows]
            return JsonResponse({'orders': orders_list})
    return _method_not_allowed()


init_db()
