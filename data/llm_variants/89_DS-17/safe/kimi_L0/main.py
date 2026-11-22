from bottle import Bottle, run, request, response, abort
import sqlite3
import json

app = Bottle()

DATABASE = 'inventory.db'

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

SEED_CATEGORIES = [(1, 'Electronics'), (2, 'Clothing'), (3, 'Books')]
SEED_PRODUCTS = [
    (1, 'Laptop', 999.99, 1, 10),
    (2, 'T-Shirt', 19.99, 2, 50),
    (3, 'Python Cookbook', 39.99, 3, 20),
    (4, 'Smartphone', 699.99, 1, 15),
]

PRODUCTS_BASE_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p JOIN categories c ON p.category_id = c.id'
)
SEARCH_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category \n'
    '               FROM products p JOIN categories c ON p.category_id = c.id \n'
    '               WHERE p.name LIKE ? OR c.name LIKE ?'
)
PRODUCT_BY_ID_QUERY = PRODUCTS_BASE_QUERY + ' WHERE p.id = ?'


def _connect():
    return sqlite3.connect(DATABASE)


def _product_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _search_result_dict(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _json_response(data):
    response.content_type = 'application/json'
    return json.dumps(data)


def _build_filters():
    conditions = []
    params = []
    category = request.query.get('category')
    min_price = request.query.get('min_price')
    max_price = request.query.get('max_price')
    in_stock = request.query.get('in_stock', 'true').lower() == 'true'
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


def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute(CREATE_CATEGORIES_TABLE)
    c.execute(CREATE_PRODUCTS_TABLE)
    c.execute('SELECT COUNT(*) FROM categories')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO categories VALUES (?, ?)', SEED_CATEGORIES)
        c.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', SEED_PRODUCTS)
        conn.commit()
    conn.close()


@app.route('/products', method='GET')
def get_products():
    conn = _connect()
    c = conn.cursor()
    query = PRODUCTS_BASE_QUERY
    conditions, params = _build_filters()
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    c.execute(query, params)
    products = [_product_dict(row) for row in c.fetchall()]
    conn.close()
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')
    conn = _connect()
    c = conn.cursor()
    search_pattern = f'%{search_term}%'
    c.execute(SEARCH_QUERY, (search_pattern, search_pattern))
    results = [_search_result_dict(row) for row in c.fetchall()]
    conn.close()
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    conn = _connect()
    c = conn.cursor()
    c.execute(PRODUCT_BY_ID_QUERY, (product_id,))
    product = c.fetchone()
    if not product:
        abort(404, 'Product not found')
    result = _product_dict(product)
    conn.close()
    return _json_response(result)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
