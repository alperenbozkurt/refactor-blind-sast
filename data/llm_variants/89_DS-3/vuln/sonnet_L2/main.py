from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
import json


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

METHOD_GET = 'GET'
METHOD_POST = 'POST'

STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_NOT_FOUND = 404
STATUS_METHOD_NOT_ALLOWED = 405
STATUS_SERVER_ERROR = 500

ERROR_INVALID_METHOD = 'Invalid method'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'

CREATE_PRODUCTS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        stock INTEGER,
        category TEXT
    )
'''

CREATE_USERS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT
    )
'''

COUNT_PRODUCTS_SQL = 'SELECT COUNT(*) FROM products'

INSERT_PRODUCT_SQL = '''
    INSERT INTO products (name, description, price, stock, category)
    VALUES (%s, %s, %s, %s, %s)
'''

SEED_PRODUCTS = [
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
]

INSERT_USER_SQL = '''
    INSERT INTO users (username, password, email)
    VALUES (%s, %s, %s)
'''

# The search term is passed as a bound parameter (never interpolated into the
# SQL text); the LIKE wildcard semantics for ordinary input are unchanged.
SEARCH_PRODUCTS_SQL = '''
    SELECT * FROM products
    WHERE name LIKE %s
    OR description LIKE %s
    OR category LIKE %s
    ORDER BY price DESC
'''

SELECT_PRODUCT_SQL = 'SELECT * FROM products WHERE id = %s'

UPDATE_STOCK_SQL = '''
    UPDATE products
    SET stock = %s
    WHERE id = %s
'''

SELECT_USER_CREDENTIALS_SQL = '''
    SELECT * FROM users
    WHERE username = %s AND password = %s
'''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invalid_method_response():
    return JsonResponse({'error': ERROR_INVALID_METHOD}, status=STATUS_METHOD_NOT_ALLOWED)


def _error_response(error, status):
    return JsonResponse({'error': str(error)}, status=status)


def _parse_json_body(request):
    return json.loads(request.body)


def _column_names(cursor):
    return [col[0] for col in cursor.description]


def _row_to_dict(cursor, row):
    return dict(zip(_column_names(cursor), row))


def _like_pattern(term):
    return f'%{term}%'


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def _create_tables(cursor):
    cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
    cursor.execute(CREATE_USERS_TABLE_SQL)


def _seed_products_if_empty(cursor):
    cursor.execute(COUNT_PRODUCTS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


def init_db():
    with connection.cursor() as cursor:
        _create_tables(cursor)
        _seed_products_if_empty(cursor)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@csrf_exempt
def register_user(request):
    if request.method == METHOD_POST:
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_USER_SQL,
                    [data['username'], data['password'], data['email']],
                )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return _error_response(e, STATUS_BAD_REQUEST)
    return _invalid_method_response()


@csrf_exempt
def search_products(request):
    if request.method == METHOD_GET:
        search_term = request.GET.get('q', '')
        try:
            with connection.cursor() as cursor:
                pattern = _like_pattern(search_term)
                cursor.execute(SEARCH_PRODUCTS_SQL, [pattern, pattern, pattern])
                columns = _column_names(cursor)
                products = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return JsonResponse({'products': products})
        except Exception as e:
            return _error_response(e, STATUS_SERVER_ERROR)
    return _invalid_method_response()


@csrf_exempt
def get_product(request, product_id):
    if request.method == METHOD_GET:
        try:
            with connection.cursor() as cursor:
                cursor.execute(SELECT_PRODUCT_SQL, [product_id])
                product = _row_to_dict(cursor, cursor.fetchone())
                return JsonResponse(product)
        except Exception as e:
            return _error_response(e, STATUS_NOT_FOUND)
    return _invalid_method_response()


@csrf_exempt
def update_stock(request):
    if request.method == METHOD_POST:
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(UPDATE_STOCK_SQL, [data['stock'], data['product_id']])
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return _error_response(e, STATUS_BAD_REQUEST)
    return _invalid_method_response()


def user_login(request):
    if request.method == METHOD_POST:
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(
                    SELECT_USER_CREDENTIALS_SQL,
                    [data['username'], data['password']],
                )
                user = _row_to_dict(cursor, cursor.fetchone())
                return JsonResponse({'status': 'success', 'user': user})
        except Exception:
            return JsonResponse(
                {'error': ERROR_INVALID_CREDENTIALS}, status=STATUS_UNAUTHORIZED
            )
    return _invalid_method_response()


init_db()
