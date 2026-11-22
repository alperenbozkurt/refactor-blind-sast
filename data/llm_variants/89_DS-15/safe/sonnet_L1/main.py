from functools import wraps

from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json

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


CREATE_PRODUCTS_TABLE = '''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category TEXT NOT NULL
    )
'''

CREATE_USERS_TABLE = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin BOOLEAN NOT NULL
    )
'''

CREATE_ORDERS_TABLE = '''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
'''

INSERT_PRODUCT = (
    'INSERT INTO products (id, name, price, category) VALUES (%s, %s, %s, %s)'
)
INSERT_USER = (
    'INSERT INTO users (id, username, password, is_admin) VALUES (%s, %s, %s, %s)'
)
INSERT_ORDER = (
    'INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)'
)

SELECT_USER_BY_CREDENTIALS = (
    'SELECT * FROM users WHERE username = %s AND password = %s'
)
SELECT_PRODUCTS_BY_TERM = (
    'SELECT * FROM products WHERE name LIKE %s OR category LIKE %s'
)
SELECT_ORDERS_BY_USER = (
    'SELECT o.id, p.name, p.price, o.quantity '
    'FROM orders o JOIN products p ON o.product_id = p.id '
    'WHERE o.user_id = %s'
)


def _table_is_empty(cursor, table):
    """Return True if the given (trusted, hard-coded) table has no rows."""
    return not cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]


def init_db():
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE)
        cursor.execute(CREATE_USERS_TABLE)
        cursor.execute(CREATE_ORDERS_TABLE)

        if _table_is_empty(cursor, 'products'):
            for product in products:
                cursor.execute(INSERT_PRODUCT, [
                    product['id'],
                    product['name'],
                    product['price'],
                    product['category'],
                ])

        if _table_is_empty(cursor, 'users'):
            for user in users:
                cursor.execute(INSERT_USER, [
                    user['id'],
                    user['username'],
                    user['password'],
                    user['is_admin'],
                ])


def _method_not_allowed():
    return JsonResponse(
        {'status': 'error', 'message': 'Method not allowed'}, status=405
    )


def _require_method(method):
    """Reject requests whose HTTP method is not exactly `method` with a 405."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != method:
                return _method_not_allowed()
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


@csrf_exempt
@_require_method('POST')
def user_login(request):
    data = json.loads(request.body)
    username = data.get('username')
    password = data.get('password')

    with connection.cursor() as cursor:
        cursor.execute(SELECT_USER_BY_CREDENTIALS, [username, password])
        user = cursor.fetchone()
        if user:
            return JsonResponse({
                'status': 'success',
                'user_id': user[0],
                'is_admin': user[3],
            })

    return JsonResponse(
        {'status': 'error', 'message': 'Invalid credentials'}, status=401
    )


@csrf_exempt
@_require_method('GET')
def search_products(request):
    search_term = request.GET.get('q', '')
    search_pattern = f'%{search_term}%'

    with connection.cursor() as cursor:
        cursor.execute(SELECT_PRODUCTS_BY_TERM, [search_pattern, search_pattern])
        rows = cursor.fetchall()

    products_list = [
        {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}
        for row in rows
    ]
    return JsonResponse({'products': products_list})


@csrf_exempt
@_require_method('POST')
def create_order(request):
    data = json.loads(request.body)
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    with connection.cursor() as cursor:
        cursor.execute(INSERT_ORDER, [user_id, product_id, quantity])
        return JsonResponse({'status': 'success', 'message': 'Order created'})


@csrf_exempt
@_require_method('GET')
def get_user_orders(request, user_id):
    with connection.cursor() as cursor:
        cursor.execute(SELECT_ORDERS_BY_USER, [user_id])
        rows = cursor.fetchall()

    orders_list = [
        {
            'order_id': row[0],
            'product_name': row[1],
            'price': row[2],
            'quantity': row[3],
        }
        for row in rows
    ]
    return JsonResponse({'orders': orders_list})


init_db()
