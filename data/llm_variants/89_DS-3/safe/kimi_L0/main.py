import json
import re
from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from django_ratelimit.decorators import ratelimit

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

SEED_PRODUCTS = [
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
]

INSERT_USER_SQL = """
    INSERT INTO users (username, password, email)
    VALUES (%s, %s, %s)
"""

SEARCH_PRODUCTS_SQL = """
    SELECT * FROM products
    WHERE name LIKE %s
    OR description LIKE %s
    OR category LIKE %s
    ORDER BY price DESC
"""

SELECT_PRODUCT_BY_ID_SQL = 'SELECT * FROM products WHERE id = %s'

UPDATE_PRODUCT_STOCK_SQL = """
    UPDATE products
    SET stock = %s
    WHERE id = %s
"""

SELECT_USER_BY_USERNAME_SQL = """
    SELECT * FROM users
    WHERE username = %s
"""

EMAIL_PATTERN = re.compile(r'^[\w.-]+@[\w.-]+\.\w+$')
UNSAFE_SEARCH_CHARS_PATTERN = re.compile(r'[;\'"\\]')


def rate_limited(max_calls, period):
    return ratelimit(key='ip', rate=f'{max_calls}/{period}s')


def validate_input(data, rules):
    errors = {}
    for field, validator in rules.items():
        if field not in data:
            errors[field] = 'This field is required'
            continue
        try:
            validator(data[field])
        except ValidationError as e:
            errors[field] = str(e)
    if errors:
        raise ValidationError(errors)


def sanitize_search_term(term):
    if not isinstance(term, str):
        return ''
    return UNSAFE_SEARCH_CHARS_PATTERN.sub('', term)[:100]


def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


# These validators intentionally *return* ValidationError instances instead
# of raising them (mirroring the original lambdas). Since validate_input only
# records errors that are raised, this preserves the existing behaviour.
def _validate_username(value):
    if len(value) > 50:
        return ValidationError('Invalid username')
    return None


def _validate_password(value):
    if len(value) < 8:
        return ValidationError('Password too short')
    return None


def _validate_email(value):
    if not EMAIL_PATTERN.match(value):
        return ValidationError('Invalid email')
    return None


def _validate_product_id(value):
    if not str(value).isdigit():
        return ValidationError('Invalid product ID')
    return None


def _validate_stock(value):
    if not isinstance(value, int) or value < 0:
        return ValidationError('Invalid stock value')
    return None


def _validate_any(value):
    return None


REGISTER_RULES = {
    'username': _validate_username,
    'password': _validate_password,
    'email': _validate_email,
}

UPDATE_STOCK_RULES = {
    'product_id': _validate_product_id,
    'stock': _validate_stock,
}

LOGIN_RULES = {
    'username': _validate_any,
    'password': _validate_any,
}


def _fetch_all_as_dicts(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_one_as_dict(cursor):
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, cursor.fetchone()))


@require_http_methods(['POST'])
@rate_limited(5, 60)
def register_user(request):
    try:
        data = json.loads(request.body)
        validate_input(data, REGISTER_RULES)
        hashed_password = make_password(data['password'])
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_USER_SQL,
                [data['username'], hashed_password, data['email']],
            )
        return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)
    except Exception:
        return JsonResponse({'error': 'Registration failed'}, status=400)


@require_http_methods(['GET'])
@rate_limited(60, 60)
def search_products(request):
    safe_search_term = sanitize_search_term(request.GET.get('q', ''))
    search_param = f'%{safe_search_term}%'
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                SEARCH_PRODUCTS_SQL,
                [search_param, search_param, search_param],
            )
            products = _fetch_all_as_dicts(cursor)
        return JsonResponse({'products': products})
    except Exception:
        return JsonResponse({'error': 'Search failed'}, status=500)


@require_http_methods(['GET'])
@rate_limited(120, 60)
def get_product(request, product_id):
    try:
        if not str(product_id).isdigit():
            raise ValidationError('Invalid product ID')
        with connection.cursor() as cursor:
            cursor.execute(SELECT_PRODUCT_BY_ID_SQL, [product_id])
            product = _fetch_one_as_dict(cursor)
        return JsonResponse(product)
    except Exception:
        return JsonResponse({'error': 'Product not found'}, status=404)


@require_http_methods(['POST'])
@rate_limited(30, 60)
def update_stock(request):
    try:
        data = json.loads(request.body)
        validate_input(data, UPDATE_STOCK_RULES)
        with connection.cursor() as cursor:
            cursor.execute(
                UPDATE_PRODUCT_STOCK_SQL,
                [data['stock'], data['product_id']],
            )
        return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)
    except Exception:
        return JsonResponse({'error': 'Update failed'}, status=400)


@require_http_methods(['POST'])
@rate_limited(5, 60)
def user_login(request):
    try:
        data = json.loads(request.body)
        validate_input(data, LOGIN_RULES)
        with connection.cursor() as cursor:
            cursor.execute(SELECT_USER_BY_USERNAME_SQL, [data['username']])
            user = _fetch_one_as_dict(cursor)
        if not check_password(data['password'], user['password']):
            raise ValidationError('Invalid credentials')
        del user['password']
        return JsonResponse({'status': 'success', 'user': user})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=401)
    except Exception:
        return JsonResponse({'error': 'Login failed'}, status=401)


init_db()
