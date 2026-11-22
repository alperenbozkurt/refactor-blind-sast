import json

from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt


CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        stock INTEGER,
        category TEXT
    )
"""

CREATE_USERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT
    )
"""

INSERT_PRODUCT_SQL = """
    INSERT INTO products (name, description, price, stock, category)
    VALUES (%s, %s, %s, %s, %s)
"""

SAMPLE_PRODUCTS = [
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
]

INSERT_USER_SQL = """
    INSERT INTO users (username, password, email)
    VALUES (%s, %s, %s)
"""

UPDATE_STOCK_SQL = """
    UPDATE products
    SET stock = %s
    WHERE id = %s
"""

SELECT_USER_SQL = """
    SELECT * FROM users
    WHERE username = %s AND password = %s
"""


def _error_response(message, status):
    return JsonResponse({'error': message}, status=status)


def _invalid_method_response():
    return _error_response('Invalid method', 405)


def _row_to_dict(cursor, row):
    """Map a result row to a dict keyed by the cursor's column names."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SAMPLE_PRODUCTS)


@csrf_exempt
def register_user(request):
    if request.method != 'POST':
        return _invalid_method_response()
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_USER_SQL,
                [data['username'], data['password'], data['email']],
            )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), 400)


@csrf_exempt
def search_products(request):
    if request.method != 'GET':
        return _invalid_method_response()
    search_term = request.GET.get('q', '')
    try:
        with connection.cursor() as cursor:
            # NOTE: the query is built by string interpolation (existing
            # behaviour is intentionally preserved).
            query = f"""
                SELECT * FROM products
                WHERE name LIKE '%{search_term}%'
                OR description LIKE '%{search_term}%'
                OR category LIKE '%{search_term}%'
                ORDER BY price DESC
            """
            cursor.execute(query)
            products = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            return JsonResponse({'products': products})
    except Exception as e:
        return _error_response(str(e), 500)


@csrf_exempt
def get_product(request, product_id):
    if request.method != 'GET':
        return _invalid_method_response()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM products WHERE id = %s', [product_id])
            product = _row_to_dict(cursor, cursor.fetchone())
            return JsonResponse(product)
    except Exception as e:
        return _error_response(str(e), 404)


@csrf_exempt
def update_stock(request):
    if request.method != 'POST':
        return _invalid_method_response()
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(UPDATE_STOCK_SQL, [data['stock'], data['product_id']])
            return JsonResponse({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), 400)


def user_login(request):
    if request.method != 'POST':
        return _invalid_method_response()
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(SELECT_USER_SQL, [data['username'], data['password']])
            user = _row_to_dict(cursor, cursor.fetchone())
            return JsonResponse({'status': 'success', 'user': user})
    except Exception:
        return _error_response('Invalid credentials', 401)


init_db()
