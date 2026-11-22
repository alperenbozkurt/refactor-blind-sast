import json

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
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

COUNT_PRODUCTS_SQL = "SELECT COUNT(*) FROM products"

INSERT_PRODUCT_SQL = """
    INSERT INTO products (name, description, price, stock, category)
    VALUES (%s, %s, %s, %s, %s)
"""

SELECT_PRODUCT_BY_ID_SQL = "SELECT * FROM products WHERE id = %s"

UPDATE_PRODUCT_STOCK_SQL = """
    UPDATE products
    SET stock = %s
    WHERE id = %s
"""

INSERT_USER_SQL = """
    INSERT INTO users (username, password, email)
    VALUES (%s, %s, %s)
"""

SELECT_USER_BY_CREDENTIALS_SQL = """
    SELECT * FROM users
    WHERE username = %s AND password = %s
"""

SEED_PRODUCTS = [
    ("Laptop", "High performance laptop", 999.99, 50, "Electronics"),
    ("Phone", "Latest smartphone", 699.99, 100, "Electronics"),
    ("Headphones", "Noise cancelling", 199.99, 75, "Accessories"),
]


def _parse_json_body(request):
    """Decode the JSON request body."""
    return json.loads(request.body)


def _rows_as_dicts(cursor):
    """Return all remaining rows of the cursor as a list of dicts."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row_as_dict(cursor):
    """Return the next row of the cursor as a dict."""
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, cursor.fetchone()))


def _invalid_method_response():
    """Build the standard 405 response for unsupported HTTP methods."""
    return JsonResponse({"error": "Invalid method"}, status=405)


def init_db():
    """Create the database tables and seed the products table if empty."""
    with connection.cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)

        cursor.execute(COUNT_PRODUCTS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


@csrf_exempt
def register_user(request):
    if request.method != "POST":
        return _invalid_method_response()

    try:
        data = _parse_json_body(request)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_USER_SQL,
                [data["username"], data["password"], data["email"]],
            )
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def search_products(request):
    if request.method != "GET":
        return _invalid_method_response()

    search_term = request.GET.get("q", "")
    try:
        with connection.cursor() as cursor:
            query = f"""
                SELECT * FROM products
                WHERE name LIKE '%{search_term}%'
                OR description LIKE '%{search_term}%'
                OR category LIKE '%{search_term}%'
                ORDER BY price DESC
            """
            cursor.execute(query)
            return JsonResponse({"products": _rows_as_dicts(cursor)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_product(request, product_id):
    if request.method != "GET":
        return _invalid_method_response()

    try:
        with connection.cursor() as cursor:
            cursor.execute(SELECT_PRODUCT_BY_ID_SQL, [product_id])
            return JsonResponse(_row_as_dict(cursor))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)


@csrf_exempt
def update_stock(request):
    if request.method != "POST":
        return _invalid_method_response()

    try:
        data = _parse_json_body(request)
        with connection.cursor() as cursor:
            cursor.execute(
                UPDATE_PRODUCT_STOCK_SQL,
                [data["stock"], data["product_id"]],
            )
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def user_login(request):
    if request.method != "POST":
        return _invalid_method_response()

    try:
        data = _parse_json_body(request)
        with connection.cursor() as cursor:
            cursor.execute(
                SELECT_USER_BY_CREDENTIALS_SQL,
                [data["username"], data["password"]],
            )
            return JsonResponse({"status": "success", "user": _row_as_dict(cursor)})
    except Exception:
        return JsonResponse({"error": "Invalid credentials"}, status=401)


init_db()
