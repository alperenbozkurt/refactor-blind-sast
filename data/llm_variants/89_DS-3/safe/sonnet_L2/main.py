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


# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

# Rate limits expressed as (max_calls, period_in_seconds)
REGISTER_RATE_LIMIT = (5, 60)
SEARCH_RATE_LIMIT = (60, 60)
PRODUCT_RATE_LIMIT = (120, 60)
STOCK_RATE_LIMIT = (30, 60)
LOGIN_RATE_LIMIT = (5, 60)

MAX_SEARCH_TERM_LENGTH = 100
MAX_USERNAME_LENGTH = 50
MIN_PASSWORD_LENGTH = 8

REQUIRED_FIELD_MESSAGE = 'This field is required'

SEARCH_SANITIZE_PATTERN = re.compile('[;\\\'"\\\\]')
EMAIL_PATTERN = '^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'

# SQL statements
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

SEED_PRODUCTS = [
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def rate_limited(max_calls, period):
    return ratelimit(key='ip', rate=f'{max_calls}/{period}s')


def validate_input(data, rules):
    errors = {}
    for (field, validator) in rules.items():
        if field not in data:
            errors[field] = REQUIRED_FIELD_MESSAGE
        else:
            try:
                validator(data[field])
            except ValidationError as e:
                errors[field] = str(e)
    if errors:
        raise ValidationError(errors)


def sanitize_search_term(term):
    if not isinstance(term, str):
        return ''
    return SEARCH_SANITIZE_PATTERN.sub('', term)[:MAX_SEARCH_TERM_LENGTH]


def _error_response(message, status):
    return JsonResponse({'error': message}, status=status)


def _column_names(cursor):
    return [col[0] for col in cursor.description]


def _fetch_all_dicts(cursor):
    columns = _column_names(cursor)
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_one_dict(cursor):
    columns = _column_names(cursor)
    return dict(zip(columns, cursor.fetchone()))


def _is_digit_id(value):
    return str(value).isdigit()


# ---------------------------------------------------------------------------
# Field validators (behaviour preserved: they return the error rather than
# raising it, exactly as the original inline lambdas did)
# ---------------------------------------------------------------------------

def _validate_username(value):
    return ValidationError('Invalid username') if len(value) > MAX_USERNAME_LENGTH else None


def _validate_password(value):
    return ValidationError('Password too short') if len(value) < MIN_PASSWORD_LENGTH else None


def _validate_email(value):
    return ValidationError('Invalid email') if not re.match(EMAIL_PATTERN, value) else None


def _validate_product_id(value):
    return ValidationError('Invalid product ID') if not _is_digit_id(value) else None


def _validate_stock(value):
    return ValidationError('Invalid stock value') if not isinstance(value, int) or value < 0 else None


def _accept_any(value):
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
    'username': _accept_any,
    'password': _accept_any,
}


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(COUNT_PRODUCTS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@require_http_methods(['POST'])
@rate_limited(*REGISTER_RATE_LIMIT)
def register_user(request):
    try:
        data = json.loads(request.body)
        validate_input(data, REGISTER_RULES)
        with connection.cursor() as cursor:
            hashed_password = make_password(data['password'])
            cursor.execute(INSERT_USER_SQL, [data['username'], hashed_password, data['email']])
        return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return _error_response(e.message_dict, 400)
    except Exception as e:
        return _error_response('Registration failed', 400)


@require_http_methods(['GET'])
@rate_limited(*SEARCH_RATE_LIMIT)
def search_products(request):
    search_term = request.GET.get('q', '')
    safe_search_term = sanitize_search_term(search_term)
    try:
        with connection.cursor() as cursor:
            search_param = f'%{safe_search_term}%'
            cursor.execute(SEARCH_PRODUCTS_SQL, [search_param, search_param, search_param])
            products = _fetch_all_dicts(cursor)
            return JsonResponse({'products': products})
    except Exception as e:
        return _error_response('Search failed', 500)


@require_http_methods(['GET'])
@rate_limited(*PRODUCT_RATE_LIMIT)
def get_product(request, product_id):
    try:
        if not _is_digit_id(product_id):
            raise ValidationError('Invalid product ID')
        with connection.cursor() as cursor:
            cursor.execute(SELECT_PRODUCT_SQL, [product_id])
            product = _fetch_one_dict(cursor)
            return JsonResponse(product)
    except Exception as e:
        return _error_response('Product not found', 404)


@require_http_methods(['POST'])
@rate_limited(*STOCK_RATE_LIMIT)
def update_stock(request):
    try:
        data = json.loads(request.body)
        validate_input(data, UPDATE_STOCK_RULES)
        with connection.cursor() as cursor:
            cursor.execute(UPDATE_STOCK_SQL, [data['stock'], data['product_id']])
            return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return _error_response(e.message_dict, 400)
    except Exception as e:
        return _error_response('Update failed', 400)


@require_http_methods(['POST'])
@rate_limited(*LOGIN_RATE_LIMIT)
def user_login(request):
    try:
        data = json.loads(request.body)
        validate_input(data, LOGIN_RULES)
        with connection.cursor() as cursor:
            cursor.execute(SELECT_USER_SQL, [data['username']])
            user = _fetch_one_dict(cursor)
            if not check_password(data['password'], user['password']):
                raise ValidationError('Invalid credentials')
            del user['password']
            return JsonResponse({'status': 'success', 'user': user})
    except ValidationError as e:
        return _error_response(str(e), 401)
    except Exception as e:
        return _error_response('Login failed', 401)


init_db()
