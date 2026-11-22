import json
import sqlite3
from contextlib import closing

from bottle import Bottle, abort, request, response, run

app = Bottle()

DB_PATH = 'inventory.db'

PRODUCT_SELECT = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
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


def _connect():
    return sqlite3.connect(DB_PATH)


def _fetch_all(query, params=()):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def _fetch_one(query, params=()):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()


def _json_response(data):
    response.content_type = 'application/json'
    return json.dumps(data)


def _product_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def init_db():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS categories\n'
            '                 (id INTEGER PRIMARY KEY, name TEXT)'
        )
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS products\n'
            '                 (id INTEGER PRIMARY KEY,\n'
            '                 name TEXT,\n'
            '                 price REAL,\n'
            '                 category_id INTEGER,\n'
            '                 stock INTEGER,\n'
            '                 FOREIGN KEY(category_id) REFERENCES categories(id))'
        )
        cursor.execute('SELECT COUNT(*) FROM categories')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO categories VALUES (?, ?)', SEED_CATEGORIES
            )
            cursor.executemany(
                'INSERT INTO products VALUES (?, ?, ?, ?, ?)', SEED_PRODUCTS
            )
            conn.commit()


@app.route('/products', method='GET')
def get_products():
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

    query = PRODUCT_SELECT
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    products = [_product_dict(row) for row in _fetch_all(query, params)]
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    query = (
        'SELECT p.id, p.name, p.price, c.name as category '
        'FROM products p JOIN categories c ON p.category_id = c.id '
        f"WHERE p.name LIKE '%{search_term}%' OR c.name LIKE '%{search_term}%'"
    )
    results = [
        {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}
        for row in _fetch_all(query)
    ]
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    product = _fetch_one(PRODUCT_SELECT + ' WHERE p.id = ?', (product_id,))
    if not product:
        abort(404, 'Product not found')
    return _json_response(_product_dict(product))


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
