import json

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

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


def init_db():
    create_table_statements = (
        '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        ''',
    )

    with connection.cursor() as cursor:
        for statement in create_table_statements:
            cursor.execute(statement)
        _seed_products(cursor)
        _seed_users(cursor)


def _seed_products(cursor):
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] != 0:
        return
    insert_statement = (
        'INSERT INTO products (id, name, price, category) VALUES (%s, %s, %s, %s)'
    )
    for product in products:
        cursor.execute(
            insert_statement,
            [product['id'], product['name'], product['price'], product['category']],
        )


def _seed_users(cursor):
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] != 0:
        return
    insert_statement = (
        'INSERT INTO users (id, username, password, is_admin) VALUES (%s, %s, %s, %s)'
    )
    for user in users:
        cursor.execute(
            insert_statement,
            [user['id'], user['username'], user['password'], user['is_admin']],
        )


def _method_not_allowed_response():
    return JsonResponse(
        {'status': 'error', 'message': 'Method not allowed'},
        status=405,
    )


@csrf_exempt
def user_login(request):
    if request.method != 'POST':
        return _method_not_allowed_response()

    data = json.loads(request.body)
    username = data.get('username')
    password = data.get('password')

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM users WHERE username = %s AND password = %s',
            [username, password],
        )
        user = cursor.fetchone()

    if user:
        return JsonResponse(
            {'status': 'success', 'user_id': user[0], 'is_admin': user[3]}
        )
    return JsonResponse(
        {'status': 'error', 'message': 'Invalid credentials'},
        status=401,
    )


@csrf_exempt
def search_products(request):
    if request.method != 'GET':
        return _method_not_allowed_response()

    search_term = request.GET.get('q', '')
    search_pattern = f'%{search_term}%'
    query = 'SELECT * FROM products WHERE name LIKE %s OR category LIKE %s'

    with connection.cursor() as cursor:
        cursor.execute(query, [search_pattern, search_pattern])
        rows = cursor.fetchall()

    products_list = [
        {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}
        for row in rows
    ]
    return JsonResponse({'products': products_list})


@csrf_exempt
def create_order(request):
    if request.method != 'POST':
        return _method_not_allowed_response()

    data = json.loads(request.body)
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)',
            [user_id, product_id, quantity],
        )

    return JsonResponse({'status': 'success', 'message': 'Order created'})


@csrf_exempt
def get_user_orders(request, user_id):
    if request.method != 'GET':
        return _method_not_allowed_response()

    query = (
        'SELECT o.id, p.name, p.price, o.quantity '
        'FROM orders o JOIN products p ON o.product_id = p.id '
        'WHERE o.user_id = %s'
    )

    with connection.cursor() as cursor:
        cursor.execute(query, [user_id])
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
