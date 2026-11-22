from contextlib import closing
import json
import sqlite3

from bottle import Bottle, run, request, response, abort

app = Bottle()

DB_PATH = 'inventory.db'

PRODUCT_SELECT = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)


def _connect():
    return closing(sqlite3.connect(DB_PATH))


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
    with _connect() as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS categories\n                 (id INTEGER PRIMARY KEY, name TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS products\n                 (id INTEGER PRIMARY KEY,\n                 name TEXT,\n                 price REAL,\n                 category_id INTEGER,\n                 stock INTEGER,\n                 FOREIGN KEY(category_id) REFERENCES categories(id))')
        c.execute('SELECT COUNT(*) FROM categories')
        if c.fetchone()[0] == 0:
            categories = [(1, 'Electronics'), (2, 'Clothing'), (3, 'Books')]
            c.executemany('INSERT INTO categories VALUES (?, ?)', categories)
            products = [
                (1, 'Laptop', 999.99, 1, 10),
                (2, 'T-Shirt', 19.99, 2, 50),
                (3, 'Python Cookbook', 39.99, 3, 20),
                (4, 'Smartphone', 699.99, 1, 15),
            ]
            c.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', products)
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

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return _json_response([_product_dict(row) for row in rows])


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    pattern = f'%{search_term}%'
    query = (
        'SELECT p.id, p.name, p.price, c.name as category '
        'FROM products p JOIN categories c ON p.category_id = c.id '
        'WHERE p.name LIKE ? OR c.name LIKE ?'
    )
    with _connect() as conn:
        rows = conn.execute(query, (pattern, pattern)).fetchall()

    results = [
        {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}
        for row in rows
    ]
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    with _connect() as conn:
        product = conn.execute(
            PRODUCT_SELECT + ' WHERE p.id = ?', (product_id,)
        ).fetchone()

    if not product:
        abort(404, 'Product not found')
    return _json_response(_product_dict(product))


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
