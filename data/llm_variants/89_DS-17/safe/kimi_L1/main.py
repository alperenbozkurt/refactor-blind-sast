"""Inventory management web service.

A small Bottle application that exposes JSON endpoints to list, search and
retrieve products stored in a SQLite database. When run as a script, the
database is created (and seeded with sample data on first run) and a
development server is started on localhost:8080.
"""

import json
import sqlite3

from bottle import Bottle, abort, request, response, run

app = Bottle()

DATABASE_PATH = 'inventory.db'

CREATE_CATEGORIES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS categories
        (id INTEGER PRIMARY KEY, name TEXT)
"""

CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products
        (id INTEGER PRIMARY KEY,
         name TEXT,
         price REAL,
         category_id INTEGER,
         stock INTEGER,
         FOREIGN KEY(category_id) REFERENCES categories(id))
"""

SELECT_PRODUCTS_SQL = """
    SELECT p.id, p.name, p.price, c.name AS category, p.stock
    FROM products p
    JOIN categories c ON p.category_id = c.id
"""

SEARCH_PRODUCTS_SQL = """
    SELECT p.id, p.name, p.price, c.name AS category
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE p.name LIKE ? OR c.name LIKE ?
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


def _connect():
    """Return a new connection to the inventory database."""
    return sqlite3.connect(DATABASE_PATH)


def _product_from_row(row):
    """Build a product dict from an (id, name, price, category, stock) row."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
    }


def _product_summary_from_row(row):
    """Build a product dict from an (id, name, price, category) row."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
    }


def init_db():
    """Create the database tables and seed them if they are empty."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_CATEGORIES_TABLE_SQL)
    cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
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
    """Return the products, optionally filtered by query parameters."""
    conn = _connect()
    cursor = conn.cursor()

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

    query = SELECT_PRODUCTS_SQL
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    cursor.execute(query, params)
    products = [_product_from_row(row) for row in cursor.fetchall()]
    conn.close()

    response.content_type = 'application/json'
    return json.dumps(products)


@app.route('/products/search', method='GET')
def search_products():
    """Return the products whose name or category matches the search term."""
    search_term = request.query.get('q')
    if not search_term:
        abort(400, 'Search term required')

    conn = _connect()
    cursor = conn.cursor()
    search_pattern = f'%{search_term}%'
    cursor.execute(SEARCH_PRODUCTS_SQL, (search_pattern, search_pattern))
    results = [_product_summary_from_row(row) for row in cursor.fetchall()]
    conn.close()

    response.content_type = 'application/json'
    return json.dumps(results)


@app.route('/products/<product_id:int>', method='GET')
def get_product(product_id):
    """Return the product with the given id."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(SELECT_PRODUCTS_SQL + ' WHERE p.id = ?', (product_id,))
    row = cursor.fetchone()
    if not row:
        abort(404, 'Product not found')
    product = _product_from_row(row)
    conn.close()

    response.content_type = 'application/json'
    return json.dumps(product)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
