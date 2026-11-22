from contextlib import closing

from bottle import Bottle, run, request, response, abort
import sqlite3
import json

app = Bottle()

DB_PATH = 'inventory.db'

CREATE_CATEGORIES_SQL = """
    CREATE TABLE IF NOT EXISTS categories
    (id INTEGER PRIMARY KEY, name TEXT)
"""

CREATE_PRODUCTS_SQL = """
    CREATE TABLE IF NOT EXISTS products
    (id INTEGER PRIMARY KEY,
     name TEXT,
     price REAL,
     category_id INTEGER,
     stock INTEGER,
     FOREIGN KEY(category_id) REFERENCES categories(id))
"""

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

SEARCH_SQL = (
    'SELECT p.id, p.name, p.price, c.name as category '
    'FROM products p JOIN categories c ON p.category_id = c.id '
    'WHERE p.name LIKE ? OR c.name LIKE ?'
)


def _connect():
    """Return a connection that is closed automatically when used with `with`."""
    return closing(sqlite3.connect(DB_PATH))


def _json_response(data):
    """Set the JSON content type and serialise the given data."""
    response.content_type = 'application/json'
    return json.dumps(data)


def _product_to_dict(row):
    """Convert a full product row (with stock) to a dictionary."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_result_to_dict(row):
    """Convert a search result row (without stock) to a dictionary."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def init_db():
    with _connect() as conn:
        c = conn.cursor()
        c.execute(CREATE_CATEGORIES_SQL)
        c.execute(CREATE_PRODUCTS_SQL)
        c.execute('SELECT COUNT(*) FROM categories')
        if c.fetchone()[0] == 0:
            c.executemany('INSERT INTO categories VALUES (?, ?)', SEED_CATEGORIES)
            c.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', SEED_PRODUCTS)
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

    conditions, params = _build_product_filters(
        category, min_price, max_price, in_stock
    )

    query = PRODUCT_SELECT_SQL
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    with _connect() as conn:
        c = conn.cursor()
        c.execute(query, params)
        products = [_product_to_dict(row) for row in c.fetchall()]

    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    search_pattern = f'%{search_term}%'

    with _connect() as conn:
        c = conn.cursor()
        c.execute(SEARCH_SQL, (search_pattern, search_pattern))
        results = [_search_result_to_dict(row) for row in c.fetchall()]

    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with _connect() as conn:
        c = conn.cursor()
        c.execute(PRODUCT_SELECT_SQL + ' WHERE p.id = ?', (product_id,))
        product = c.fetchone()

    if not product:
        abort(404, 'Product not found')

    return _json_response(_product_to_dict(product))


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
