import json
import sqlite3
from contextlib import contextmanager

from bottle import Bottle, run, request, response, abort

DB_PATH = 'inventory.db'

app = Bottle()

PRODUCT_SELECT = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)

INITIAL_CATEGORIES = [
    (1, 'Electronics'),
    (2, 'Clothing'),
    (3, 'Books'),
]

INITIAL_PRODUCTS = [
    (1, 'Laptop', 999.99, 1, 10),
    (2, 'T-Shirt', 19.99, 2, 50),
    (3, 'Python Cookbook', 39.99, 3, 20),
    (4, 'Smartphone', 699.99, 1, 15),
]


@contextmanager
def _connect():
    """Open a database connection and always close it afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _json_response(payload):
    """Set the JSON content type and serialise the payload."""
    response.content_type = 'application/json'
    return json.dumps(payload)


def _product_to_dict(row):
    """Convert a (id, name, price, category, stock) row to a dict."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_result_to_dict(row):
    """Convert a (id, name, price, category) row to a dict."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def init_db():
    with _connect() as conn:
        c = conn.cursor()
        c.execute(
            'CREATE TABLE IF NOT EXISTS categories '
            '(id INTEGER PRIMARY KEY, name TEXT)'
        )
        c.execute(
            'CREATE TABLE IF NOT EXISTS products '
            '(id INTEGER PRIMARY KEY, '
            'name TEXT, '
            'price REAL, '
            'category_id INTEGER, '
            'stock INTEGER, '
            'FOREIGN KEY(category_id) REFERENCES categories(id))'
        )
        c.execute('SELECT COUNT(*) FROM categories')
        if c.fetchone()[0] == 0:
            c.executemany('INSERT INTO categories VALUES (?, ?)', INITIAL_CATEGORIES)
            c.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', INITIAL_PRODUCTS)
            conn.commit()


def _build_product_filters(category, min_price, max_price, in_stock):
    """Build the WHERE conditions and parameters for the product listing."""
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


@app.route('/products', method='GET')
def get_products():
    category = request.query.get('category')
    min_price = request.query.get('min_price')
    max_price = request.query.get('max_price')
    in_stock = request.query.get('in_stock', 'true').lower() == 'true'

    with _connect() as conn:
        c = conn.cursor()
        conditions, params = _build_product_filters(
            category, min_price, max_price, in_stock
        )
        query = PRODUCT_SELECT
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        c.execute(query, params)
        products = [_product_to_dict(row) for row in c.fetchall()]

    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    with _connect() as conn:
        c = conn.cursor()
        # NOTE: the search term is interpolated directly into the SQL string.
        # This is preserved as-is to keep the existing behaviour unchanged.
        query = (
            'SELECT p.id, p.name, p.price, c.name as category '
            'FROM products p JOIN categories c ON p.category_id = c.id '
            f"WHERE p.name LIKE '%{search_term}%' OR c.name LIKE '%{search_term}%'"
        )
        c.execute(query)
        results = [_search_result_to_dict(row) for row in c.fetchall()]

    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with _connect() as conn:
        c = conn.cursor()
        c.execute(PRODUCT_SELECT + ' WHERE p.id = ?', (product_id,))
        product = c.fetchone()
        if not product:
            abort(404, 'Product not found')
        result = _product_to_dict(product)

    return _json_response(result)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
