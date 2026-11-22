"""Storefront views and database bootstrap.

Refactored for modularity: SQL lives in named constants, seed data and
endpoint settings in configuration objects, and repeated cursor/JSON
plumbing in small helpers. Runtime behaviour is unchanged.
"""

from django.shortcuts import render  # noqa: F401  (kept for backwards compatibility)
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
import json
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

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

INSERT_USER_SQL = """
    INSERT INTO users (username, password, email)
    VALUES (%s, %s, %s)
"""

SELECT_PRODUCT_BY_ID_SQL = "SELECT * FROM products WHERE id = %s"

SEARCH_PRODUCTS_SQL_TEMPLATE = """
    SELECT * FROM products
    WHERE name LIKE '%{search_term}%'
    OR description LIKE '%{search_term}%'
    OR category LIKE '%{search_term}%'
    ORDER BY price DESC
"""

UPDATE_PRODUCT_STOCK_SQL = """
    UPDATE products
    SET stock = %s
    WHERE id = %s
"""

SELECT_USER_BY_CREDENTIALS_SQL = """
    SELECT * FROM users
    WHERE username = %s AND password = %s
"""


# ---------------------------------------------------------------------------
# Configuration and static data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductSearchConfig:
    """Settings for the product search endpoint."""

    query_param: str = "q"
    default_term: str = ""


PRODUCT_SEARCH_CONFIG = ProductSearchConfig()

SEED_PRODUCTS = [
    ("Laptop", "High performance laptop", 999.99, 50, "Electronics"),
    ("Phone", "Latest smartphone", 699.99, 100, "Electronics"),
    ("Headphones", "Noise cancelling", 199.99, 75, "Accessories"),
]

ERROR_INVALID_METHOD = "Invalid method"
ERROR_INVALID_CREDENTIALS = "Invalid credentials"

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_INTERNAL_SERVER_ERROR = 500


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _parse_json_body(request):
    """Return the decoded JSON body of ``request``."""
    return json.loads(request.body)


def _column_names(cursor):
    """Return the column names of the cursor's last result set."""
    return [column[0] for column in cursor.description]


def _fetch_all_as_dicts(cursor):
    """Return every remaining row as a dict keyed by column name."""
    columns = _column_names(cursor)
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_one_as_dict(cursor):
    """Return the next row as a dict keyed by column name."""
    return dict(zip(_column_names(cursor), cursor.fetchone()))


def _error_response(message, status):
    return JsonResponse({"error": message}, status=status)


def _invalid_method_response():
    return _error_response(ERROR_INVALID_METHOD, HTTP_METHOD_NOT_ALLOWED)


def _create_tables(cursor):
    cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
    cursor.execute(CREATE_USERS_TABLE_SQL)


def _seed_products_if_empty(cursor):
    cursor.execute(COUNT_PRODUCTS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

def init_db():
    """Create the schema and seed the products table when it is empty."""
    with connection.cursor() as cursor:
        _create_tables(cursor)
        _seed_products_if_empty(cursor)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@csrf_exempt
def register_user(request):
    if request.method == "POST":
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_USER_SQL,
                    [data["username"], data["password"], data["email"]],
                )
            return JsonResponse({"status": "success"})
        except Exception as e:
            return _error_response(str(e), HTTP_BAD_REQUEST)
    return _invalid_method_response()


@csrf_exempt
def search_products(request):
    if request.method == "GET":
        search_term = request.GET.get(
            PRODUCT_SEARCH_CONFIG.query_param,
            PRODUCT_SEARCH_CONFIG.default_term,
        )
        try:
            with connection.cursor() as cursor:
                query = SEARCH_PRODUCTS_SQL_TEMPLATE.format(
                    search_term=search_term
                )
                cursor.execute(query)
                return JsonResponse({"products": _fetch_all_as_dicts(cursor)})
        except Exception as e:
            return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)
    return _invalid_method_response()


@csrf_exempt
def get_product(request, product_id):
    if request.method == "GET":
        try:
            with connection.cursor() as cursor:
                cursor.execute(SELECT_PRODUCT_BY_ID_SQL, [product_id])
                return JsonResponse(_fetch_one_as_dict(cursor))
        except Exception as e:
            return _error_response(str(e), HTTP_NOT_FOUND)
    return _invalid_method_response()


@csrf_exempt
def update_stock(request):
    if request.method == "POST":
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(
                    UPDATE_PRODUCT_STOCK_SQL,
                    [data["stock"], data["product_id"]],
                )
                return JsonResponse({"status": "success"})
        except Exception as e:
            return _error_response(str(e), HTTP_BAD_REQUEST)
    return _invalid_method_response()


def user_login(request):
    if request.method == "POST":
        try:
            data = _parse_json_body(request)
            with connection.cursor() as cursor:
                cursor.execute(
                    SELECT_USER_BY_CREDENTIALS_SQL,
                    [data["username"], data["password"]],
                )
                return JsonResponse(
                    {"status": "success", "user": _fetch_one_as_dict(cursor)}
                )
        except Exception as e:
            return _error_response(ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    return _invalid_method_response()


init_db()
