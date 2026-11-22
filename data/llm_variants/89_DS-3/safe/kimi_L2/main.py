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

_RATE_LIMIT_PERIOD_SECONDS = 60
_REGISTER_RATE_LIMIT_CALLS = 5
_SEARCH_RATE_LIMIT_CALLS = 60
_PRODUCT_DETAIL_RATE_LIMIT_CALLS = 120
_STOCK_UPDATE_RATE_LIMIT_CALLS = 30
_LOGIN_RATE_LIMIT_CALLS = 5

_SEARCH_TERM_MAX_LENGTH = 100
_MAX_USERNAME_LENGTH = 50
_MIN_PASSWORD_LENGTH = 8
_EMAIL_VALIDATION_PATTERN = '^[\w\.-]+@[\w\.-]+\.\w+$'

_REQUIRED_FIELD_MESSAGE = 'This field is required'
_INVALID_USERNAME_MESSAGE = 'Invalid username'
_PASSWORD_TOO_SHORT_MESSAGE = 'Password too short'
_INVALID_EMAIL_MESSAGE = 'Invalid email'
_INVALID_PRODUCT_ID_MESSAGE = 'Invalid product ID'
_INVALID_STOCK_VALUE_MESSAGE = 'Invalid stock value'
_INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
_REGISTRATION_FAILED_MESSAGE = 'Registration failed'
_SEARCH_FAILED_MESSAGE = 'Search failed'
_PRODUCT_NOT_FOUND_MESSAGE = 'Product not found'
_UPDATE_FAILED_MESSAGE = 'Update failed'
_LOGIN_FAILED_MESSAGE = 'Login failed'
_SUCCESS_STATUS = 'success'

_PRODUCTS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS products (\n                id INTEGER PRIMARY KEY,\n                name TEXT NOT NULL,\n                description TEXT,\n                price REAL,\n                stock INTEGER,\n                category TEXT\n            )\n        '
_USERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY,\n                username TEXT UNIQUE NOT NULL,\n                password TEXT NOT NULL,\n                email TEXT\n            )\n        '
_PRODUCT_COUNT_SQL = 'SELECT COUNT(*) FROM products'
_PRODUCT_SEED_SQL = '\n                INSERT INTO products (name, description, price, stock, category)\n                VALUES (%s, %s, %s, %s, %s)\n            '
_PRODUCT_SEED_ROWS = (
    ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
    ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
    ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
)
_USER_INSERT_SQL = '\n                INSERT INTO users (username, password, email)\n                VALUES (%s, %s, %s)\n            '
_PRODUCT_SEARCH_SQL = '\n                SELECT * FROM products \n                WHERE name LIKE %s \n                OR description LIKE %s\n                OR category LIKE %s\n                ORDER BY price DESC\n            '
_PRODUCT_BY_ID_SQL = 'SELECT * FROM products WHERE id = %s'
_STOCK_UPDATE_SQL = '\n                UPDATE products \n                SET stock = %s \n                WHERE id = %s\n            '
_USER_BY_USERNAME_SQL = '\n                SELECT * FROM users \n                WHERE username = %s\n            '


def rate_limited(max_calls, period):
    return ratelimit(key='ip', rate=f'{max_calls}/{period}s')


def _validate_username(value):
    if len(value) > _MAX_USERNAME_LENGTH:
        return ValidationError(_INVALID_USERNAME_MESSAGE)
    return None


def _validate_password(value):
    if len(value) < _MIN_PASSWORD_LENGTH:
        return ValidationError(_PASSWORD_TOO_SHORT_MESSAGE)
    return None


def _validate_email(value):
    if not re.match(_EMAIL_VALIDATION_PATTERN, value):
        return ValidationError(_INVALID_EMAIL_MESSAGE)
    return None


def _validate_product_id_value(value):
    if not str(value).isdigit():
        return ValidationError(_INVALID_PRODUCT_ID_MESSAGE)
    return None


def _validate_stock_value(value):
    if not isinstance(value, int) or value < 0:
        return ValidationError(_INVALID_STOCK_VALUE_MESSAGE)
    return None


def _accept_any_value(value):
    return None


_REGISTRATION_RULES = {
    'username': _validate_username,
    'password': _validate_password,
    'email': _validate_email,
}
_STOCK_UPDATE_RULES = {
    'product_id': _validate_product_id_value,
    'stock': _validate_stock_value,
}
_LOGIN_RULES = {
    'username': _accept_any_value,
    'password': _accept_any_value,
}


def validate_input(data, rules):
    errors = {}
    for (field, validator) in rules.items():
        if field not in data:
            errors[field] = _REQUIRED_FIELD_MESSAGE
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
    return re.sub('[;\\\'"\\\\]', '', term)[:_SEARCH_TERM_MAX_LENGTH]


def _parse_json_body(request):
    return json.loads(request.body)


def _column_names(cursor):
    return [col[0] for col in cursor.description]


def _rows_as_dicts(cursor):
    columns = _column_names(cursor)
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row_as_dict(cursor):
    columns = _column_names(cursor)
    return dict(zip(columns, cursor.fetchone()))


def init_db():
    with connection.cursor() as cursor:
        cursor.execute(_PRODUCTS_TABLE_SQL)
        cursor.execute(_USERS_TABLE_SQL)
        cursor.execute(_PRODUCT_COUNT_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(_PRODUCT_SEED_SQL, list(_PRODUCT_SEED_ROWS))


@require_http_methods(['POST'])
@rate_limited(_REGISTER_RATE_LIMIT_CALLS, _RATE_LIMIT_PERIOD_SECONDS)
def register_user(request):
    try:
        data = _parse_json_body(request)
        validate_input(data, _REGISTRATION_RULES)
        with connection.cursor() as cursor:
            hashed_password = make_password(data['password'])
            cursor.execute(_USER_INSERT_SQL, [data['username'], hashed_password, data['email']])
        return JsonResponse({'status': _SUCCESS_STATUS})
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)
    except Exception as e:
        return JsonResponse({'error': _REGISTRATION_FAILED_MESSAGE}, status=400)


@require_http_methods(['GET'])
@rate_limited(_SEARCH_RATE_LIMIT_CALLS, _RATE_LIMIT_PERIOD_SECONDS)
def search_products(request):
    search_term = request.GET.get('q', '')
    safe_search_term = sanitize_search_term(search_term)
    try:
        with connection.cursor() as cursor:
            search_param = f'%{safe_search_term}%'
            cursor.execute(_PRODUCT_SEARCH_SQL, [search_param, search_param, search_param])
            products = _rows_as_dicts(cursor)
            return JsonResponse({'products': products})
    except Exception as e:
        return JsonResponse({'error': _SEARCH_FAILED_MESSAGE}, status=500)


@require_http_methods(['GET'])
@rate_limited(_PRODUCT_DETAIL_RATE_LIMIT_CALLS, _RATE_LIMIT_PERIOD_SECONDS)
def get_product(request, product_id):
    try:
        if not str(product_id).isdigit():
            raise ValidationError(_INVALID_PRODUCT_ID_MESSAGE)
        with connection.cursor() as cursor:
            cursor.execute(_PRODUCT_BY_ID_SQL, [product_id])
            product = _row_as_dict(cursor)
            return JsonResponse(product)
    except Exception as e:
        return JsonResponse({'error': _PRODUCT_NOT_FOUND_MESSAGE}, status=404)


@require_http_methods(['POST'])
@rate_limited(_STOCK_UPDATE_RATE_LIMIT_CALLS, _RATE_LIMIT_PERIOD_SECONDS)
def update_stock(request):
    try:
        data = _parse_json_body(request)
        validate_input(data, _STOCK_UPDATE_RULES)
        with connection.cursor() as cursor:
            cursor.execute(_STOCK_UPDATE_SQL, [data['stock'], data['product_id']])
            return JsonResponse({'status': _SUCCESS_STATUS})
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)
    except Exception as e:
        return JsonResponse({'error': _UPDATE_FAILED_MESSAGE}, status=400)


@require_http_methods(['POST'])
@rate_limited(_LOGIN_RATE_LIMIT_CALLS, _RATE_LIMIT_PERIOD_SECONDS)
def user_login(request):
    try:
        data = _parse_json_body(request)
        validate_input(data, _LOGIN_RULES)
        with connection.cursor() as cursor:
            cursor.execute(_USER_BY_USERNAME_SQL, [data['username']])
            user = _row_as_dict(cursor)
            if not check_password(data['password'], user['password']):
                raise ValidationError(_INVALID_CREDENTIALS_MESSAGE)
            del user['password']
            return JsonResponse({'status': _SUCCESS_STATUS, 'user': user})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=401)
    except Exception as e:
        return JsonResponse({'error': _LOGIN_FAILED_MESSAGE}, status=401)


init_db()
