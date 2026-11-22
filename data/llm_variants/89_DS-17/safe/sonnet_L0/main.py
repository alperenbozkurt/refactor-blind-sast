import json
import sqlite3
from contextlib import closing

from bottle import Bottle, run, request, response, abort

app = Bottle()

DB_PATH = 'inventory.db'

PRODUCT_SELECT = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)

SEARCH_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category '
    'FROM products p JOIN categories c ON p.category_id = c.id '
    'WHERE p.name LIKE ? OR c.name LIKE ?'
)

INITIAL_CATEGORIES = [(1, 'Electronics'), (2, 'Clothing'), (3, 'Books')]
INITIAL_PRODUCTS = [
    (1, 'Laptop', 999.99, 1, 10),
    (2, 'T-Shirt', 19.99, 2, 50),
    (3, 'Python Cookbook', 39.99, 3, 20),
    (4, 'Smartphone', 699.99, 1, 15),
]


def _connect():
    return closing(sqlite3.connect(DB_PATH))


def _json_response(data):
    response.content_type = 'application/json'
    return json.dumps(data)


def _product_to_dict(row, include_stock=True):
    result = {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }
    if include_stock:
        result['stock'] = row[4]
    return result


def init_db():
    with _connect() as conn:
        c = conn.cursor()
        c.execute(
            'CREATE TABLE IF NOT EXISTS categories '
            '(id INTEGER PRIMARY KEY, name TEXT)'
        )
        c.execute(
            'CREATE TABLE IF NOT EXISTS products ('
            'id INTEGER PRIMARY KEY, '
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


@app.route('/products', method='GET')
def get_products():
    query = request.query
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

    sql = PRODUCT_SELECT
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)

    with _connect() as conn:
        rows = conn.cursor().execute(sql, params).fetchall()

    return _json_response([_product_to_dict(row) for row in rows])


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    pattern = f'%{search_term}%'
    with _connect() as conn:
        rows = conn.cursor().execute(SEARCH_QUERY, (pattern, pattern)).fetchall()

    return _json_response([_product_to_dict(row, include_stock=False) for row in rows])


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with _connect() as conn:
        product = conn.cursor().execute(
            PRODUCT_SELECT + ' WHERE p.id = ?', (product_id,)
        ).fetchone()

    if not product:
        abort(404, 'Product not found')

    return _json_response(_product_to_dict(product))


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
