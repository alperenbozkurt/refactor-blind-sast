"""Inventory management web API backed by a SQLite database."""

import re
import sqlite3
from contextlib import contextmanager

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest


class Config:
    """Application-wide configuration values."""

    DEBUG = False
    DATABASE = 'inventory.db'
    MAX_NAME_LENGTH = 100
    MAX_CATEGORY_LENGTH = 50
    MAX_SEARCH_TERM_LENGTH = 100


app = Flask(__name__)
app.config['DEBUG'] = Config.DEBUG

_CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL,
        quantity INTEGER,
        category TEXT
    )
"""
_INSERT_PRODUCT_SQL = """
    INSERT INTO products (name, price, quantity, category)
    VALUES (?, ?, ?, ?)
"""
_SEARCH_PRODUCTS_SQL = """
    SELECT * FROM products
    WHERE name LIKE ? OR category LIKE ?
"""
_UPDATE_QUANTITY_SQL = """
    UPDATE products SET quantity = ? WHERE id = ?
"""
_DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

_UNSAFE_SEARCH_CHARS_RE = re.compile(r'[;\'"\\]')


def _get_connection():
    """Return a new connection to the inventory database."""
    return sqlite3.connect(Config.DATABASE)


@contextmanager
def _db_cursor():
    """Yield a database cursor, committing on success and closing on exit."""
    conn = _get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def _require_dict(data):
    if not isinstance(data, dict):
        raise BadRequest('Invalid data format')


def _require_fields(data, required_fields):
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise BadRequest(f"Missing required fields: {', '.join(missing_fields)}")


def _validate_name(name):
    if not isinstance(name, str) or len(name) > Config.MAX_NAME_LENGTH:
        raise BadRequest('Invalid product name')


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


def _validate_category(category):
    if not isinstance(category, str) or len(category) > Config.MAX_CATEGORY_LENGTH:
        raise BadRequest('Invalid category')


def _parse_quantity_update(data):
    """Extract and validate the product ID and quantity from request data."""
    try:
        product_id = int(data['id'])
        quantity = int(data['quantity'])
        if quantity < 0:
            raise BadRequest('Quantity cannot be negative')
    except (ValueError, TypeError):
        raise BadRequest('Invalid ID or quantity format')
    return product_id, quantity


def _product_from_row(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def _bad_request_response(error):
    return jsonify({'error': str(error)}), 400


def _internal_error_response():
    return jsonify({'error': 'Internal server error'}), 500


def init_db():
    """Create the products table if it does not already exist."""
    with _db_cursor() as cursor:
        cursor.execute(_CREATE_PRODUCTS_TABLE_SQL)


def validate_product_data(data, required_fields):
    """Validate incoming product data, raising BadRequest on any problem."""
    _require_dict(data)
    _require_fields(data, required_fields)
    _validate_name(data.get('name'))
    _validate_price(data['price'])
    _validate_quantity(data['quantity'])
    _validate_category(data.get('category'))


def sanitize_search_term(term):
    """Strip unsafe characters from a search term and limit its length."""
    if not isinstance(term, str):
        return ''
    return _UNSAFE_SEARCH_CHARS_RE.sub('', term)[:Config.MAX_SEARCH_TERM_LENGTH]


@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        validate_product_data(data, ['name', 'price', 'quantity', 'category'])
        with _db_cursor() as cursor:
            cursor.execute(
                _INSERT_PRODUCT_SQL,
                (data['name'], data['price'], data['quantity'], data['category']),
            )
        return jsonify({'message': 'Product added successfully'}), 201
    except BadRequest as e:
        return _bad_request_response(e)
    except Exception:
        return _internal_error_response()


@app.route('/search_product', methods=['GET'])
def search_product():
    try:
        safe_search_term = sanitize_search_term(request.args.get('query', ''))
        with _db_cursor() as cursor:
            cursor.execute(
                _SEARCH_PRODUCTS_SQL,
                (f'%{safe_search_term}%', f'%{safe_search_term}%'),
            )
            results = cursor.fetchall()
        return jsonify([_product_from_row(row) for row in results])
    except Exception:
        return _internal_error_response()


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    try:
        data = request.get_json()
        if not isinstance(data, dict) or 'id' not in data or 'quantity' not in data:
            raise BadRequest('Missing required fields: id and quantity')
        product_id, quantity = _parse_quantity_update(data)
        with _db_cursor() as cursor:
            cursor.execute(_UPDATE_QUANTITY_SQL, (quantity, product_id))
        return jsonify({'message': 'Quantity updated successfully'})
    except BadRequest as e:
        return _bad_request_response(e)
    except Exception:
        return _internal_error_response()


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        with _db_cursor() as cursor:
            cursor.execute(_DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception:
        return _internal_error_response()


if __name__ == '__main__':
    init_db()
    app.run(debug=Config.DEBUG)
