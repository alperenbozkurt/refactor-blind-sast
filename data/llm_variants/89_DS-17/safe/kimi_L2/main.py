"""Inventory service: a Bottle JSON API backed by a SQLite database."""

from bottle import Bottle, run, request, response, abort
import sqlite3
import json

app = Bottle()


class Config:
    """Runtime configuration for the inventory service."""

    DATABASE_PATH = 'inventory.db'
    HOST = 'localhost'
    PORT = 8080
    DEBUG = True


CONFIG = Config()

JSON_CONTENT_TYPE = 'application/json'

# --- SQL statements --------------------------------------------------------

CREATE_CATEGORIES_TABLE = (
    'CREATE TABLE IF NOT EXISTS categories\n'
    '                 (id INTEGER PRIMARY KEY, name TEXT)'
)
CREATE_PRODUCTS_TABLE = (
    'CREATE TABLE IF NOT EXISTS products\n'
    '                 (id INTEGER PRIMARY KEY,\n'
    '                 name TEXT,\n'
    '                 price REAL,\n'
    '                 category_id INTEGER,\n'
    '                 stock INTEGER,\n'
    '                 FOREIGN KEY(category_id) REFERENCES categories(id))'
)

COUNT_CATEGORIES = 'SELECT COUNT(*) FROM categories'
INSERT_CATEGORY = 'INSERT INTO categories VALUES (?, ?)'
INSERT_PRODUCT = 'INSERT INTO products VALUES (?, ?, ?, ?, ?)'

SELECT_PRODUCTS = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)
SELECT_PRODUCT_BY_ID = SELECT_PRODUCTS + ' WHERE p.id = ?'
SEARCH_PRODUCTS_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category \n'
    '               FROM products p JOIN categories c ON p.category_id = c.id \n'
    '               WHERE p.name LIKE ? OR c.name LIKE ?'
)

FILTER_BY_CATEGORY = 'c.name = ?'
FILTER_BY_MIN_PRICE = 'p.price >= ?'
FILTER_BY_MAX_PRICE = 'p.price <= ?'
FILTER_IN_STOCK = 'p.stock > 0'

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


# --- Database helpers ------------------------------------------------------

def _get_connection():
    return sqlite3.connect(CONFIG.DATABASE_PATH)


def _create_tables(cursor):
    cursor.execute(CREATE_CATEGORIES_TABLE)
    cursor.execute(CREATE_PRODUCTS_TABLE)


def _has_categories(cursor):
    cursor.execute(COUNT_CATEGORIES)
    return cursor.fetchone()[0] != 0


def _seed_database(cursor, conn):
    cursor.executemany(INSERT_CATEGORY, SEED_CATEGORIES)
    cursor.executemany(INSERT_PRODUCT, SEED_PRODUCTS)
    conn.commit()


def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    _create_tables(cursor)
    if not _has_categories(cursor):
        _seed_database(cursor, conn)
    conn.close()


# --- Serialization helpers -------------------------------------------------

def _product_row(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _product_search_row(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _json_response(payload):
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


# --- Query helpers ---------------------------------------------------------

def _product_filters():
    conditions = []
    params = []
    category = request.query.get('category')
    min_price = request.query.get('min_price')
    max_price = request.query.get('max_price')
    in_stock = request.query.get('in_stock', 'true').lower() == 'true'
    if category:
        conditions.append(FILTER_BY_CATEGORY)
        params.append(category)
    if min_price:
        conditions.append(FILTER_BY_MIN_PRICE)
        params.append(float(min_price))
    if max_price:
        conditions.append(FILTER_BY_MAX_PRICE)
        params.append(float(max_price))
    if in_stock:
        conditions.append(FILTER_IN_STOCK)
    return conditions, params


def _products_query(conditions):
    query = SELECT_PRODUCTS
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    return query


# --- Routes ----------------------------------------------------------------

@app.route('/products', method='GET')
def get_products():
    conn = _get_connection()
    cursor = conn.cursor()
    conditions, params = _product_filters()
    cursor.execute(_products_query(conditions), params)
    products = [_product_row(row) for row in cursor.fetchall()]
    conn.close()
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')
    conn = _get_connection()
    cursor = conn.cursor()
    search_pattern = f'%{search_term}%'
    cursor.execute(SEARCH_PRODUCTS_QUERY, (search_pattern, search_pattern))
    results = [_product_search_row(row) for row in cursor.fetchall()]
    conn.close()
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(SELECT_PRODUCT_BY_ID, (product_id,))
    product = cursor.fetchone()
    if not product:
        abort(404, 'Product not found')
    result = _product_row(product)
    conn.close()
    return _json_response(result)


# --- Entry point -----------------------------------------------------------

def main():
    init_db()
    run(app, host=CONFIG.HOST, port=CONFIG.PORT, debug=CONFIG.DEBUG)


if __name__ == '__main__':
    main()
