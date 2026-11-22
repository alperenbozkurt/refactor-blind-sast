from contextlib import closing, contextmanager
from dataclasses import dataclass

from bottle import Bottle, run, request, response, abort
import sqlite3
import json

app = Bottle()


# --------------------------------------------------------------------------
# Configuration and constants
# --------------------------------------------------------------------------

DB_PATH = 'inventory.db'
JSON_CONTENT_TYPE = 'application/json'


@dataclass(frozen=True)
class ServerConfig:
    host: str = 'localhost'
    port: int = 8080
    debug: bool = True


SERVER_CONFIG = ServerConfig()

CREATE_CATEGORIES_SQL = (
    'CREATE TABLE IF NOT EXISTS categories '
    '(id INTEGER PRIMARY KEY, name TEXT)'
)
CREATE_PRODUCTS_SQL = (
    'CREATE TABLE IF NOT EXISTS products '
    '(id INTEGER PRIMARY KEY, '
    'name TEXT, '
    'price REAL, '
    'category_id INTEGER, '
    'stock INTEGER, '
    'FOREIGN KEY(category_id) REFERENCES categories(id))'
)
COUNT_CATEGORIES_SQL = 'SELECT COUNT(*) FROM categories'
INSERT_CATEGORY_SQL = 'INSERT INTO categories VALUES (?, ?)'
INSERT_PRODUCT_SQL = 'INSERT INTO products VALUES (?, ?, ?, ?, ?)'

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

PRODUCT_SELECT_SQL = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)
PRODUCT_BY_ID_SQL = PRODUCT_SELECT_SQL + ' WHERE p.id = ?'
SEARCH_SQL = (
    'SELECT p.id, p.name, p.price, c.name as category '
    'FROM products p JOIN categories c ON p.category_id = c.id '
    'WHERE p.name LIKE ? OR c.name LIKE ?'
)

ERR_SEARCH_REQUIRED = 'Search term required'
ERR_PRODUCT_NOT_FOUND = 'Product not found'


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

@contextmanager
def get_cursor():
    """Yield a cursor on a fresh connection, closing the connection after."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        yield conn, conn.cursor()


def _seed_database(conn, cursor):
    cursor.executemany(INSERT_CATEGORY_SQL, SEED_CATEGORIES)
    cursor.executemany(INSERT_PRODUCT_SQL, SEED_PRODUCTS)
    conn.commit()


def init_db():
    with get_cursor() as (conn, c):
        c.execute(CREATE_CATEGORIES_SQL)
        c.execute(CREATE_PRODUCTS_SQL)
        c.execute(COUNT_CATEGORIES_SQL)
        if c.fetchone()[0] == 0:
            _seed_database(conn, c)


# --------------------------------------------------------------------------
# Serialization helpers
# --------------------------------------------------------------------------

def _product_row_to_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_row_to_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _json_response(payload):
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


# --------------------------------------------------------------------------
# Query building
# --------------------------------------------------------------------------

def _build_product_filters(query):
    """Return (conditions, params) derived from the request query string."""
    category = query.get('category')
    min_price = query.get('min_price')
    max_price = query.get('max_price')
    in_stock = query.get('in_stock', 'true').lower() == 'true'

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


def _build_product_query(conditions):
    sql = PRODUCT_SELECT_SQL
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)
    return sql


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route('/products', method='GET')
def get_products():
    with get_cursor() as (_conn, c):
        conditions, params = _build_product_filters(request.query)
        c.execute(_build_product_query(conditions), params)
        products = [_product_row_to_dict(row) for row in c.fetchall()]
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, ERR_SEARCH_REQUIRED)
    search_pattern = f'%{search_term}%'
    with get_cursor() as (_conn, c):
        c.execute(SEARCH_SQL, (search_pattern, search_pattern))
        results = [_search_row_to_dict(row) for row in c.fetchall()]
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with get_cursor() as (_conn, c):
        c.execute(PRODUCT_BY_ID_SQL, (product_id,))
        product = c.fetchone()
        if not product:
            abort(404, ERR_PRODUCT_NOT_FOUND)
        result = _product_row_to_dict(product)
    return _json_response(result)


if __name__ == '__main__':
    init_db()
    run(
        app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
