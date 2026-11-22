import json
from functools import wraps

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

CREATE_PRODUCTS_SQL = '''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        stock INTEGER,
        category TEXT
    )
'''

CREATE_USERS_SQL = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT
    )
'''

INSERT_PRODUCT_SQL = '''
    INSERT INTO products (name, description, price, stock, category)
    VALUES (%s, %s, %s, %s, %s)
'''

SEED_PRODUCTS = [
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
]

SEARCH_PRODUCTS_SQL = '''
    SELECT * FROM products
    WHERE name LIKE %s
    OR description LIKE %s
    OR category LIKE %s
    ORDER BY price DESC
'''


def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_SQL)
        cursor.execute(CREATE_USERS_SQL)
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


def _allow_method(method):
    """Return 405 JSON error unless the request uses the given HTTP method."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != method:
                return JsonResponse({'error': 'Invalid method'}, status=405)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def _error(message, status):
    return JsonResponse({'error': message}, status=status)


def _column_names(cursor):
    return [col[0] for col in cursor.description]


def _fetch_one_dict(cursor):
    return dict(zip(_column_names(cursor), cursor.fetchone()))


def _fetch_all_dicts(cursor):
    columns = _column_names(cursor)
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@csrf_exempt
@_allow_method('POST')
def register_user(request):
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO users (username, password, email) VALUES (%s, %s, %s)',
                [data['username'], data['password'], data['email']],
            )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return _error(str(e), 400)


@csrf_exempt
@_allow_method('GET')
def search_products(request):
    search_term = request.GET.get('q', '')
    pattern = f'%{search_term}%'
    try:
        with connection.cursor() as cursor:
            cursor.execute(SEARCH_PRODUCTS_SQL, [pattern, pattern, pattern])
            return JsonResponse({'products': _fetch_all_dicts(cursor)})
    except Exception as e:
        return _error(str(e), 500)


@csrf_exempt
@_allow_method('GET')
def get_product(request, product_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM products WHERE id = %s', [product_id])
            return JsonResponse(_fetch_one_dict(cursor))
    except Exception as e:
        return _error(str(e), 404)


@csrf_exempt
@_allow_method('POST')
def update_stock(request):
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE products SET stock = %s WHERE id = %s',
                [data['stock'], data['product_id']],
            )
            return JsonResponse({'status': 'success'})
    except Exception as e:
        return _error(str(e), 400)


@_allow_method('POST')
def user_login(request):
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT * FROM users WHERE username = %s AND password = %s',
                [data['username'], data['password']],
            )
            user = _fetch_one_dict(cursor)
            return JsonResponse({'status': 'success', 'user': user})
    except Exception:
        return _error('Invalid credentials', 401)


init_db()
