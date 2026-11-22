import sqlite3
from contextlib import contextmanager

from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Configuration -----------------------------------------------------------

DATABASE_PATH = 'inventory.db'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

# --- SQL statements ----------------------------------------------------------

CREATE_PRODUCTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            quantity INTEGER,
            category TEXT
        )
    '''

INSERT_PRODUCT_SQL = '''
            INSERT INTO products (name, price, quantity, category)
            VALUES (?, ?, ?, ?)
        '''

# Parameterized to avoid SQL injection; matching semantics are unchanged.
SEARCH_PRODUCTS_SQL = 'SELECT * FROM products WHERE name LIKE ? OR category LIKE ?'

UPDATE_QUANTITY_SQL = '''
            UPDATE products SET quantity = ? WHERE id = ?
        '''

DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

# --- Database helpers --------------------------------------------------------


@contextmanager
def get_connection():
    """Open a connection to the inventory database and always close it."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def execute_write(sql, params=()):
    """Execute a single write statement and commit it."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()


def execute_read(sql, params=()):
    """Execute a single read statement and return all rows."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


def row_to_product(row):
    """Convert a products table row into a JSON-serializable dict."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def build_like_pattern(search_term):
    """Wrap a search term for a substring LIKE match."""
    return f'%{search_term}%'


# --- Response helpers --------------------------------------------------------


def message_response(message, status=HTTP_OK):
    """Build a JSON success message response."""
    if status == HTTP_OK:
        return jsonify({'message': message})
    return (jsonify({'message': message}), status)


def error_response(exc, status):
    """Build a JSON error response from an exception."""
    return (jsonify({'error': str(exc)}), status)


# --- Database initialization -------------------------------------------------


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)
        conn.commit()


# --- Routes ------------------------------------------------------------------


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        execute_write(
            INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return message_response('Product added successfully', HTTP_CREATED)
    except Exception as e:
        return error_response(e, HTTP_BAD_REQUEST)


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        pattern = build_like_pattern(search_term)
        results = execute_read(SEARCH_PRODUCTS_SQL, (pattern, pattern))
        products = [row_to_product(row) for row in results]
        return jsonify(products)
    except Exception as e:
        return error_response(e, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        execute_write(UPDATE_QUANTITY_SQL, (data['quantity'], data['id']))
        return message_response('Quantity updated successfully')
    except Exception as e:
        return error_response(e, HTTP_BAD_REQUEST)


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        execute_write(DELETE_PRODUCT_SQL, (product_id,))
        return message_response('Product deleted successfully')
    except Exception as e:
        return error_response(e, HTTP_BAD_REQUEST)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
