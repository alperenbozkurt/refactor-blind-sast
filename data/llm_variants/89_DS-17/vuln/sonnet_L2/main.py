from contextlib import closing, contextmanager
import json
import sqlite3

from bottle import Bottle, run, request, response, abort

# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------
DB_PATH = 'inventory.db'

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
SERVER_DEBUG = True

JSON_CONTENT_TYPE = 'application/json'

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

PRODUCT_JOIN_SQL = 'FROM products p JOIN categories c ON p.category_id = c.id'
PRODUCT_SELECT_SQL = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock ' + PRODUCT_JOIN_SQL
)
PRODUCT_SEARCH_SQL = (
    'SELECT p.id, p.name, p.price, c.name as category ' + PRODUCT_JOIN_SQL +
    ' WHERE p.name LIKE ? OR c.name LIKE ?'
)

app = Bottle()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
@contextmanager
def get_connection():
    """Yield a SQLite connection that is always closed afterwards."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        yield conn


def _seed_database(cursor):
    cursor.executemany('INSERT INTO categories VALUES (?, ?)', SEED_CATEGORIES)
    cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', SEED_PRODUCTS)


def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(CREATE_CATEGORIES_SQL)
        c.execute(CREATE_PRODUCTS_SQL)
        c.execute('SELECT COUNT(*) FROM categories')
        if c.fetchone()[0] == 0:
            _seed_database(c)
            conn.commit()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def _product_to_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_result_to_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _json_response(payload):
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------
def _build_product_filters():
    """Build the WHERE clause and parameters from the request query string."""
    category = request.query.get('category')
    min_price = request.query.get('min_price')
    max_price = request.query.get('max_price')
    in_stock = request.query.get('in_stock', 'true').lower() == 'true'

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

    where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
    return where, params


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/products', method='GET')
def get_products():
    with get_connection() as conn:
        c = conn.cursor()
        where, params = _build_product_filters()
        c.execute(PRODUCT_SELECT_SQL + where, params)
        products = [_product_to_dict(row) for row in c.fetchall()]
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')
    pattern = f'%{search_term}%'
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(PRODUCT_SEARCH_SQL, (pattern, pattern))
        results = [_search_result_to_dict(row) for row in c.fetchall()]
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(PRODUCT_SELECT_SQL + ' WHERE p.id = ?', (product_id,))
        product = c.fetchone()
    if not product:
        abort(404, 'Product not found')
    return _json_response(_product_to_dict(product))


if __name__ == '__main__':
    init_db()
    run(app, host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
