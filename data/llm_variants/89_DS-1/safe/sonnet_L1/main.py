import re
import sqlite3
from contextlib import closing

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

app = Flask(__name__)
app.config['DEBUG'] = False

DATABASE_PATH = 'inventory.db'

MAX_NAME_LENGTH = 100
MAX_CATEGORY_LENGTH = 50
MAX_SEARCH_TERM_LENGTH = 100

_UNSAFE_SEARCH_CHARS = re.compile('[;\\\'"\\\\]')

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

UPDATE_QUANTITY_SQL = 'UPDATE products SET quantity = ? WHERE id = ?'

DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _execute_write(query, params=()):
    """Run a single modifying statement and commit it."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()


def _fetch_all(query, params=()):
    """Run a single query and return all resulting rows."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def init_db():
    _execute_write(CREATE_PRODUCTS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


def _internal_error_response():
    return _error_response('Internal server error', 500)


def _row_to_product(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_price(value):
    try:
        price = float(value)
        if price <= 0:
            raise BadRequest('Price must be positive')
    except (ValueError, TypeError):
        raise BadRequest('Invalid price format')


def _validate_quantity(value):
    try:
        quantity = int(value)
        if quantity < 0:
            raise BadRequest('Quantity cannot be negative')
    except (ValueError, TypeError):
        raise BadRequest('Invalid quantity format')


def _is_valid_string(value, max_length):
    return isinstance(value, str) and len(value) <= max_length


def validate_product_data(data, required_fields):
    if not isinstance(data, dict):
        raise BadRequest('Invalid data format')

    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise BadRequest(f"Missing required fields: {', '.join(missing_fields)}")

    if not _is_valid_string(data.get('name'), MAX_NAME_LENGTH):
        raise BadRequest('Invalid product name')

    _validate_price(data['price'])
    _validate_quantity(data['quantity'])

    if not _is_valid_string(data.get('category'), MAX_CATEGORY_LENGTH):
        raise BadRequest('Invalid category')


def sanitize_search_term(term):
    if not isinstance(term, str):
        return ''
    return _UNSAFE_SEARCH_CHARS.sub('', term)[:MAX_SEARCH_TERM_LENGTH]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        validate_product_data(data, ['name', 'price', 'quantity', 'category'])
        _execute_write(
            INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return jsonify({'message': 'Product added successfully'}), 201
    except BadRequest as e:
        return _error_response(str(e), 400)
    except Exception:
        return _internal_error_response()


@app.route('/search_product', methods=['GET'])
def search_product():
    try:
        search_term = request.args.get('query', '')
        safe_search_term = sanitize_search_term(search_term)
        pattern = f'%{safe_search_term}%'
        rows = _fetch_all(SEARCH_PRODUCTS_SQL, (pattern, pattern))
        return jsonify([_row_to_product(row) for row in rows])
    except Exception:
        return _internal_error_response()


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    try:
        data = request.get_json()
        if not isinstance(data, dict) or 'id' not in data or 'quantity' not in data:
            raise BadRequest('Missing required fields: id and quantity')
        try:
            product_id = int(data['id'])
            quantity = int(data['quantity'])
            if quantity < 0:
                raise BadRequest('Quantity cannot be negative')
        except (ValueError, TypeError):
            raise BadRequest('Invalid ID or quantity format')

        _execute_write(UPDATE_QUANTITY_SQL, (quantity, product_id))
        return jsonify({'message': 'Quantity updated successfully'})
    except BadRequest as e:
        return _error_response(str(e), 400)
    except Exception:
        return _internal_error_response()


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        _execute_write(DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception:
        return _internal_error_response()


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
