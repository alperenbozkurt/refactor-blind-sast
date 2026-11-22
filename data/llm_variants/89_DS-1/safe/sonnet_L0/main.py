import re
import sqlite3
from contextlib import closing

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

app = Flask(__name__)
app.config['DEBUG'] = False

DB_PATH = 'inventory.db'

CREATE_PRODUCTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            quantity INTEGER,
            category TEXT
        )
    '''


def _connect():
    return closing(sqlite3.connect(DB_PATH))


def _execute_write(sql, params=()):
    with _connect() as conn:
        conn.cursor().execute(sql, params)
        conn.commit()


def _error_response(message, status):
    return jsonify({'error': message}), status


def _internal_error():
    return _error_response('Internal server error', 500)


def init_db():
    with _connect() as conn:
        conn.cursor().execute(CREATE_PRODUCTS_TABLE_SQL)
        conn.commit()


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
    if not _is_valid_string(data.get('name'), 100):
        raise BadRequest('Invalid product name')
    _validate_price(data['price'])
    _validate_quantity(data['quantity'])
    if not _is_valid_string(data.get('category'), 50):
        raise BadRequest('Invalid category')


def sanitize_search_term(term):
    if not isinstance(term, str):
        return ''
    return re.sub('[;\\\'"\\\\]', '', term)[:100]


def _row_to_product(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        validate_product_data(data, ['name', 'price', 'quantity', 'category'])
        _execute_write(
            '''
            INSERT INTO products (name, price, quantity, category)
            VALUES (?, ?, ?, ?)
        ''',
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return jsonify({'message': 'Product added successfully'}), 201
    except BadRequest as e:
        return _error_response(str(e), 400)
    except Exception:
        return _internal_error()


@app.route('/search_product', methods=['GET'])
def search_product():
    try:
        search_term = request.args.get('query', '')
        pattern = f'%{sanitize_search_term(search_term)}%'
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
            SELECT * FROM products 
            WHERE name LIKE ? OR category LIKE ?
        ''',
                (pattern, pattern),
            )
            results = cursor.fetchall()
        return jsonify([_row_to_product(row) for row in results])
    except Exception:
        return _internal_error()


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
        _execute_write(
            '''
            UPDATE products SET quantity = ? WHERE id = ?
        ''',
            (quantity, product_id),
        )
        return jsonify({'message': 'Quantity updated successfully'})
    except BadRequest as e:
        return _error_response(str(e), 400)
    except Exception:
        return _internal_error()


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        _execute_write('DELETE FROM products WHERE id = ?', (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception:
        return _internal_error()


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
