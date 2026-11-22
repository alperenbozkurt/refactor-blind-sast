import json
import sqlite3

from bottle import Bottle, abort, request, response, run

app = Bottle()

DATABASE_PATH = 'inventory.db'

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

PRODUCT_LIST_QUERY = (
    'SELECT p.id, p.name, p.price, c.name as category, p.stock '
    'FROM products p '
    'JOIN categories c ON p.category_id = c.id'
)
PRODUCT_BY_ID_QUERY = PRODUCT_LIST_QUERY + ' WHERE p.id = ?'


def _json_response(payload):
    """Serialize ``payload`` as JSON and set the response content type."""
    response.content_type = 'application/json'
    return json.dumps(payload)


def _product_summary(row):
    """Build the product representation used by listing and search rows."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def _product_details(row):
    """Build the full product representation, including the stock level."""
    details = _product_summary(row)
    details['stock'] = row[4]
    return details


def _build_product_filters(category, min_price, max_price, in_stock):
    """Translate query string parameters into SQL conditions and parameters."""
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


def init_db():
    """Create the database schema and seed it when it is empty."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_CATEGORIES_TABLE)
    cursor.execute(CREATE_PRODUCTS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            'INSERT INTO categories VALUES (?, ?)', SEED_CATEGORIES
        )
        cursor.executemany(
            'INSERT INTO products VALUES (?, ?, ?, ?, ?)', SEED_PRODUCTS
        )
        conn.commit()
    conn.close()


@app.route('/products', method='GET')
def get_products():
    """List products, optionally filtered by category, price and stock."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    category = request.query.get('category')
    min_price = request.query.get('min_price')
    max_price = request.query.get('max_price')
    in_stock = request.query.get('in_stock', 'true').lower() == 'true'

    conditions, params = _build_product_filters(
        category, min_price, max_price, in_stock
    )
    query = PRODUCT_LIST_QUERY
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    cursor.execute(query, params)
    products = [_product_details(row) for row in cursor.fetchall()]
    conn.close()
    return _json_response(products)


@app.route('/products/search', method='GET')
def search_products():
    """Search products and categories by name."""
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    # The term is interpolated directly into the SQL text; this preserves the
    # original behaviour of the endpoint.
    query = (
        f"SELECT p.id, p.name, p.price, c.name as category "
        f"FROM products p JOIN categories c ON p.category_id = c.id "
        f"WHERE p.name LIKE '%{search_term}%' OR c.name LIKE '%{search_term}%'"
    )
    cursor.execute(query)
    results = [_product_summary(row) for row in cursor.fetchall()]
    conn.close()
    return _json_response(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    """Return a single product by id."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(PRODUCT_BY_ID_QUERY, (product_id,))
    product = cursor.fetchone()
    if not product:
        abort(404, 'Product not found')
    result = _product_details(product)
    conn.close()
    return _json_response(result)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
