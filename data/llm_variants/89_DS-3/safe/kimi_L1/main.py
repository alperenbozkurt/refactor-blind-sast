"""Views and helpers for a small product catalogue with user accounts."""

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


def rate_limited(max_calls, period):
    """Return a decorator limiting each IP to ``max_calls`` per ``period`` seconds."""
    return ratelimit(key='ip', rate=f'{max_calls}/{period}s')


def validate_input(data, rules):
    """Validate ``data`` against the per-field validators in ``rules``.

    Every field listed in ``rules`` must be present in ``data``; each
    validator is then called with the field's value. All failures are
    collected and raised together as a single ``ValidationError`` built
    from a field-to-message dict.
    """
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
    """Strip semicolons, quotes and backslashes, then truncate to 100 chars."""
    if not isinstance(term, str):
        return ''
    return re.sub(r'[;\'"\\]', '', term)[:100]


def init_db():
    """Create the products and users tables, seeding products when empty."""
    create_products_table = '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL,
            stock INTEGER,
            category TEXT
        )
    '''
    create_users_table = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT
        )
    '''
    insert_product = '''
        INSERT INTO products (name, description, price, stock, category)
        VALUES (%s, %s, %s, %s, %s)
    '''
    seed_products = [
        ('Laptop', 'High performance laptop', 999.99, 50, 'Electronics'),
        ('Phone', 'Latest smartphone', 699.99, 100, 'Electronics'),
        ('Headphones', 'Noise cancelling', 199.99, 75, 'Accessories'),
    ]

    with connection.cursor() as cursor:
        cursor.execute(create_products_table)
        cursor.execute(create_users_table)
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(insert_product, seed_products)


@require_http_methods(['POST'])
@rate_limited(5, 60)
def register_user(request):
    """Register a new user account from a JSON request body."""
    def validate_username(value):
        if len(value) > 50:
            return ValidationError('Invalid username')
        return None

    def validate_password(value):
        if len(value) < 8:
            return ValidationError('Password too short')
        return None

    def validate_email(value):
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value):
            return ValidationError('Invalid email')
        return None

    rules = {
        'username': validate_username,
        'password': validate_password,
        'email': validate_email,
    }

    try:
        data = json.loads(request.body)
        validate_input(data, rules)
        hashed_password = make_password(data['password'])
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO users (username, password, email)
                VALUES (%s, %s, %s)
                ''',
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
    """Search products by name, description or category, priciest first."""
    search_term = request.GET.get('q', '')
    safe_search_term = sanitize_search_term(search_term)
    search_param = f'%{safe_search_term}%'
    query = '''
        SELECT * FROM products
        WHERE name LIKE %s
        OR description LIKE %s
        OR category LIKE %s
        ORDER BY price DESC
    '''

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [search_param, search_param, search_param])
            columns = [col[0] for col in cursor.description]
            products = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return JsonResponse({'products': products})
    except Exception:
        return JsonResponse({'error': 'Search failed'}, status=500)


@require_http_methods(['GET'])
@rate_limited(120, 60)
def get_product(request, product_id):
    """Return a single product identified by its numeric id."""
    try:
        if not str(product_id).isdigit():
            raise ValidationError('Invalid product ID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM products WHERE id = %s', [product_id])
            columns = [col[0] for col in cursor.description]
            product = dict(zip(columns, cursor.fetchone()))
            return JsonResponse(product)
    except Exception:
        return JsonResponse({'error': 'Product not found'}, status=404)


@require_http_methods(['POST'])
@rate_limited(30, 60)
def update_stock(request):
    """Update the stock level of a product from a JSON request body."""
    def validate_product_id(value):
        if not str(value).isdigit():
            return ValidationError('Invalid product ID')
        return None

    def validate_stock(value):
        if not isinstance(value, int) or value < 0:
            return ValidationError('Invalid stock value')
        return None

    rules = {
        'product_id': validate_product_id,
        'stock': validate_stock,
    }

    try:
        data = json.loads(request.body)
        validate_input(data, rules)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE products
                SET stock = %s
                WHERE id = %s
                ''',
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
    """Authenticate a user against the stored password hash."""
    rules = {
        'username': lambda value: None,
        'password': lambda value: None,
    }

    try:
        data = json.loads(request.body)
        validate_input(data, rules)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT * FROM users
                WHERE username = %s
                ''',
                [data['username']],
            )
            columns = [col[0] for col in cursor.description]
            user = dict(zip(columns, cursor.fetchone()))
            if not check_password(data['password'], user['password']):
                raise ValidationError('Invalid credentials')
            del user['password']
            return JsonResponse({'status': 'success', 'user': user})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=401)
    except Exception:
        return JsonResponse({'error': 'Login failed'}, status=401)


init_db()
