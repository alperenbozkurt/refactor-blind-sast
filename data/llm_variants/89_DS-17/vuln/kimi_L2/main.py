"""Inventory management web API built with Bottle.

Organised around named SQL constants, seed-data definitions, small helper
functions and a server configuration class, while exposing the same routes,
module-level names and behaviour as the original module.
"""

import json
import sqlite3
from contextlib import closing

from bottle import Bottle, run, request, response, abort

# --- Configuration --------------------------------------------------------

DATABASE_PATH = 'inventory.db'
JSON_CONTENT_TYPE = 'application/json'


class ServerConfig:
    """Settings for the bundled development server."""

    HOST = 'localhost'
    PORT = 8080
    DEBUG = True


# --- SQL statements ---------------------------------------------------------

CREATE_CATEGORIES_TABLE = 'CREATE TABLE IF NOT EXISTS categories\n                 (id INTEGER PRIMARY KEY, name TEXT)'
CREATE_PRODUCTS_TABLE = 'CREATE TABLE IF NOT EXISTS products\n                 (id INTEGER PRIMARY KEY,\n                 name TEXT,\n                 price REAL,\n                 category_id INTEGER,\n                 stock INTEGER,\n                 FOREIGN KEY(category_id) REFERENCES categories(id))'

COUNT_CATEGORIES_QUERY = 'SELECT COUNT(*) FROM categories'
INSERT_CATEGORY_QUERY = 'INSERT INTO categories VALUES (?, ?)'
INSERT_PRODUCT_QUERY = 'INSERT INTO products VALUES (?, ?, ?, ?, ?)'

PRODUCTS_BASE_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)
PRODUCT_BY_ID_QUERY = PRODUCTS_BASE_QUERY + ' WHERE p.id = ?'

# --- Seed data --------------------------------------------------------------

SEED_CATEGORIES = [
    (1, 'Electronics'),
    (2, 'Clothing'),
    (3, 'Books'),
]
SEED_PRODUCTS = [
    (1, 'Laptop', 999.99, 1, 10),
    (2, 'T-Shirt', 19.99, 2, 50),
    (3, 'Python Cookbook', 39.99, 3, 20),
    (4, 'Smartphone', 699.99, 1, 15),
]

app = Bottle()


# --- Helpers ------------------------------------------------------------------

def _connect():
    """Open a new connection to the inventory database."""
    return sqlite3.connect(DATABASE_PATH)


def _json_response(payload):
    """Serialize payload to JSON and mark the response content type."""
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


def _product_row_to_dict(row):
    """Map a full product row (with stock) to its JSON representation."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_row_to_dict(row):
    """Map a search result row (without stock) to its JSON representation."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _build_search_query(search_term):
    """Build the search SQL verbatim, exactly as the original inline query."""
    return (
        f"SELECT p.id, p.name, p.price, c.name as category "
        f"FROM products p JOIN categories c ON p.category_id = c.id "
        f"WHERE p.name LIKE '%{search_term}%' OR c.name LIKE '%{search_term}%'"
    )


def _build_product_filters(category, min_price, max_price, in_stock):
    """Translate query-string filters into SQL conditions and parameters."""
    conditions = []
    params = []
    if category:
        conditions.append('c.name = ?')
        params.append(category)
    if min_price:
        conditions.append('p.price >= ?')
        params.append(float(min_price))
    if max_price:
        conditions.append('p.price <= ?')
        params.append(float(max_price))
    if in_stock:
        conditions.append('p.stock > 0')
    return conditions, params


def _seed_data(cursor):
    """Insert the default categories and products into an empty database."""
    cursor.executemany(INSERT_CATEGORY_QUERY, SEED_CATEGORIES)
    cursor.executemany(INSERT_PRODUCT_QUERY, SEED_PRODUCTS)


def init_db():
    """Create the schema if needed and seed it when no categories exist."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_CATEGORIES_TABLE)
        cursor.execute(CREATE_PRODUCTS_TABLE)
        cursor.execute(COUNT_CATEGORIES_QUERY)
        if cursor.fetchone()[0] == 0:
            _seed_data(cursor)
            conn.commit()


# --- Routes -------------------------------------------------------------------

@app.route('/products', method='GET')
def get_products():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        category = request.query.get('category')
        min_price = request.query.get('min_price')
        max_price = request.query.get('max_price')
        in_stock = request.query.get('in_stock', 'true').lower() == 'true'
        conditions, params = _build_product_filters(
            category, min_price, max_price, in_stock
        )
        base_query = PRODUCTS_BASE_QUERY
        if conditions:
            base_query += ' WHERE ' + ' AND '.join(conditions)
        cursor.execute(base_query, params)
        products = [_product_row_to_dict(row) for row in cursor.fetchall()]
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(_build_search_query(search_term))
        results = [_search_row_to_dict(row) for row in cursor.fetchall()]
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(PRODUCT_BY_ID_QUERY, (product_id,))
        product = cursor.fetchone()
        if not product:
            abort(404, 'Product not found')
        result = _product_row_to_dict(product)
    return _json_response(result)


if __name__ == '__main__':
    init_db()
    run(app, host=ServerConfig.HOST, port=ServerConfig.PORT,
        debug=ServerConfig.DEBUG)
