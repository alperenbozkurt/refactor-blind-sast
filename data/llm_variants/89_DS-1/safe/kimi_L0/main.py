import re
import sqlite3
from contextlib import closing

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

DATABASE = 'inventory.db'

CREATE_TABLE_SQL = '''
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
SEARCH_PRODUCT_SQL = '''
    SELECT * FROM products
    WHERE name LIKE ? OR category LIKE ?
'''
UPDATE_QUANTITY_SQL = '''
    UPDATE products SET quantity = ? WHERE id = ?
'''
DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

UNSAFE_SEARCH_CHARS = re.compile(r'[;\'"\\]')

REQUIRED_PRODUCT_FIELDS = ['name', 'price', 'quantity', 'category']

app = Flask(__name__)
app.config['DEBUG'] = False


def _query_db(sql, params=()):
    with closing(sqlite3.connect(DATABASE)) as conn:
        return conn.execute(sql, params).fetchall()


def _modify_db(sql, params=()):
    with closing(sqlite3.connect(DATABASE)) as conn:
        conn.execute(sql, params)
        conn.commit()


def init_db():
    _modify_db(CREATE_TABLE_SQL)


def _validate_name(data):
    if not isinstance(data.get('name'), str) or len(data['name']) > 100:
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
    if not isinstance(data.get('category'), str) or len(data['category']) > 50:
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
    return UNSAFE_SEARCH_CHARS.sub('', term)[:100]


def _product_from_row(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def _parse_quantity_update(data):
    try:
        product_id = int(data['id'])
        quantity = int(data['quantity'])
        if quantity < 0:
            raise BadRequest('Quantity cannot be negative')
    except (ValueError, TypeError):
        raise BadRequest('Invalid ID or quantity format')
    return product_id, quantity


@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        validate_product_data(data, REQUIRED_PRODUCT_FIELDS)
        _modify_db(
            INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return jsonify({'message': 'Product added successfully'}), 201
    except BadRequest as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/search_product', methods=['GET'])
def search_product():
    try:
        safe_search_term = sanitize_search_term(request.args.get('query', ''))
        pattern = f'%{safe_search_term}%'
        rows = _query_db(SEARCH_PRODUCT_SQL, (pattern, pattern))
        return jsonify([_product_from_row(row) for row in rows])
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    try:
        data = request.get_json()
        if not isinstance(data, dict) or 'id' not in data or 'quantity' not in data:
            raise BadRequest('Missing required fields: id and quantity')
        product_id, quantity = _parse_quantity_update(data)
        _modify_db(UPDATE_QUANTITY_SQL, (quantity, product_id))
        return jsonify({'message': 'Quantity updated successfully'})
    except BadRequest as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        _modify_db(DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
