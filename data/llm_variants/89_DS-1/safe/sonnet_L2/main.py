import re
import sqlite3
from contextlib import closing

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
DATABASE_PATH = 'inventory.db'

MAX_NAME_LENGTH = 100
MAX_CATEGORY_LENGTH = 50
MAX_SEARCH_TERM_LENGTH = 100

PRODUCT_REQUIRED_FIELDS = ['name', 'price', 'quantity', 'category']

SEARCH_TERM_FORBIDDEN_CHARS = re.compile(r'''[;'"\\]''')

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

INTERNAL_ERROR_MESSAGE = 'Internal server error'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------
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

SEARCH_PRODUCTS_SQL = '''
            SELECT * FROM products 
            WHERE name LIKE ? OR category LIKE ?
        '''

UPDATE_QUANTITY_SQL = '''
            UPDATE products SET quantity = ? WHERE id = ?
        '''

DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['DEBUG'] = False


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _connect():
    """Open a new connection to the inventory database."""
    return sqlite3.connect(DATABASE_PATH)


def _execute_write(sql, params=()):
    """Execute a single write statement and commit it."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()


def _execute_read(sql, params=()):
    """Execute a single read statement and return all rows."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


def init_db():
    _execute_write(CREATE_PRODUCTS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _validate_name(data):
    if not isinstance(data.get('name'), str) or len(data['name']) > MAX_NAME_LENGTH:
        raise BadRequest('Invalid product name')


def _validate_price(data):
    try:
        price = float(data['price'])
        if price <= 0:
            raise BadRequest('Price must be positive')
    except (ValueError, TypeError):
        raise BadRequest('Invalid price format')


def _validate_quantity(data):
    try:
        quantity = int(data['quantity'])
        if quantity < 0:
            raise BadRequest('Quantity cannot be negative')
    except (ValueError, TypeError):
        raise BadRequest('Invalid quantity format')


def _validate_category(data):
    if not isinstance(data.get('category'), str) or len(data['category']) > MAX_CATEGORY_LENGTH:
        raise BadRequest('Invalid category')


def validate_product_data(data, required_fields):
    if not isinstance(data, dict):
        raise BadRequest('Invalid data format')
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise BadRequest(f"Missing required fields: {', '.join(missing_fields)}")
    _validate_name(data)
    _validate_price(data)
    _validate_quantity(data)
    _validate_category(data)


def sanitize_search_term(term):
    if not isinstance(term, str):
        return ''
    return SEARCH_TERM_FORBIDDEN_CHARS.sub('', term)[:MAX_SEARCH_TERM_LENGTH]


def _parse_quantity_update(data):
    """Validate an update-quantity payload and return (product_id, quantity)."""
    if not isinstance(data, dict) or 'id' not in data or 'quantity' not in data:
        raise BadRequest('Missing required fields: id and quantity')
    try:
        product_id = int(data['id'])
        quantity = int(data['quantity'])
        if quantity < 0:
            raise BadRequest('Quantity cannot be negative')
    except (ValueError, TypeError):
        raise BadRequest('Invalid ID or quantity format')
    return product_id, quantity


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _bad_request_response(error):
    return _error_response(str(error), HTTP_BAD_REQUEST)


def _internal_error_response():
    return _error_response(INTERNAL_ERROR_MESSAGE, HTTP_INTERNAL_SERVER_ERROR)


def _row_to_product(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        validate_product_data(data, PRODUCT_REQUIRED_FIELDS)
        _execute_write(
            INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return (jsonify({'message': 'Product added successfully'}), HTTP_CREATED)
    except BadRequest as e:
        return _bad_request_response(e)
    except Exception as e:
        return _internal_error_response()


@app.route('/search_product', methods=['GET'])
def search_product():
    try:
        search_term = request.args.get('query', '')
        safe_search_term = sanitize_search_term(search_term)
        pattern = f'%{safe_search_term}%'
        results = _execute_read(SEARCH_PRODUCTS_SQL, (pattern, pattern))
        products = [_row_to_product(row) for row in results]
        return jsonify(products)
    except Exception as e:
        return _internal_error_response()


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    try:
        data = request.get_json()
        product_id, quantity = _parse_quantity_update(data)
        _execute_write(UPDATE_QUANTITY_SQL, (quantity, product_id))
        return jsonify({'message': 'Quantity updated successfully'})
    except BadRequest as e:
        return _bad_request_response(e)
    except Exception as e:
        return _internal_error_response()


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        _execute_write(DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        return _internal_error_response()


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
