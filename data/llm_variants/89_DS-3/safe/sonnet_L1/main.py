from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
import json
import re
from functools import wraps
from django_ratelimit.decorators import ratelimit


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SEARCH_TERM_MAX_LENGTH = 100
UNSAFE_SEARCH_CHARS = re.compile(r"""[;'"\\]""")
EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w+$'

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

SELECT_USER_SQL = '''
    SELECT * FROM users
    WHERE username = %s
'''


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------

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
    return UNSAFE_SEARCH_CHARS.sub('', term)[:SEARCH_TERM_MAX_LENGTH]


def _row_to_dict(cursor, row):
    """Map a result row to a dict keyed by column name."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


# --------------------------------------------------------------------------
# Field validators (they return a ValidationError or None, as before)
# --------------------------------------------------------------------------

def _check_username(value):
    return ValidationError('Invalid username') if len(value) > 50 else None


def _check_password(value):
    return ValidationError('Password too short') if len(value) < 8 else None


def _check_email(value):
    if not re.match(EMAIL_PATTERN, value):
        return ValidationError('Invalid email')
    return None


def _check_product_id(value):
    return ValidationError('Invalid product ID') if not str(value).isdigit() else None


def _check_stock(value):
    if not isinstance(value, int) or value < 0:
        return ValidationError('Invalid stock value')
    return None


def _accept_any(value):
    return None


REGISTER_RULES = {
    'username': _check_username,
    'password': _check_password,
    'email': _check_email,
}

UPDATE_STOCK_RULES = {
    'product_id': _check_product_id,
    'stock': _check_stock,
}

LOGIN_RULES = {
    'username': _accept_any,
    'password': _accept_any,
}


# --------------------------------------------------------------------------
# Database initialisation
# --------------------------------------------------------------------------

def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(COUNT_PRODUCTS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

@require_http_methods(['POST'])
@rate_limited(5, 60)
def register_user(request):
    try:
        data = json.loads(request.body)
        validate_input(data, REGISTER_RULES)
        with connection.cursor() as cursor:
            hashed_password = make_password(data['password'])
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
    search_term = request.GET.get('q', '')
    safe_search_term = sanitize_search_term(search_term)
    try:
        with connection.cursor() as cursor:
            search_param = f'%{safe_search_term}%'
            cursor.execute(SEARCH_PRODUCTS_SQL, [search_param] * 3)
            products = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
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
            cursor.execute(SELECT_PRODUCT_SQL, [product_id])
            product = _row_to_dict(cursor, cursor.fetchone())
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
            cursor.execute(UPDATE_STOCK_SQL, [data['stock'], data['product_id']])
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
            cursor.execute(SELECT_USER_SQL, [data['username']])
            user = _row_to_dict(cursor, cursor.fetchone())
            if not check_password(data['password'], user['password']):
                raise ValidationError('Invalid credentials')
            del user['password']
            return JsonResponse({'status': 'success', 'user': user})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=401)
    except Exception:
        return JsonResponse({'error': 'Login failed'}, status=401)


init_db()
