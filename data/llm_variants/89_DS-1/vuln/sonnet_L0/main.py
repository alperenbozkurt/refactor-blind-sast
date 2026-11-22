import sqlite3
from contextlib import contextmanager

from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = 'inventory.db'

CREATE_PRODUCTS_TABLE = '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            quantity INTEGER,
            category TEXT
        )
    '''


@contextmanager
def get_connection():
    """Yield a database connection and always close it afterwards."""
    conn = sqlite3.connect(DATABASE)
    try:
        yield conn
    finally:
        conn.close()


def _error_response(error, status):
    return jsonify({'error': str(error)}), status


def _row_to_product(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def init_db():
    with get_connection() as conn:
        conn.cursor().execute(CREATE_PRODUCTS_TABLE)
        conn.commit()


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                '''
            INSERT INTO products (name, price, quantity, category)
            VALUES (?, ?, ?, ?)
        ''',
                (data['name'], data['price'], data['quantity'], data['category']),
            )
            conn.commit()
        return jsonify({'message': 'Product added successfully'}), 201
    except Exception as e:
        return _error_response(e, 400)


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        pattern = f'%{search_term}%'
        with get_connection() as conn:
            cursor = conn.cursor()
            # Parameterized query to avoid SQL injection.
            cursor.execute(
                'SELECT * FROM products WHERE name LIKE ? OR category LIKE ?',
                (pattern, pattern),
            )
            results = cursor.fetchall()
        return jsonify([_row_to_product(row) for row in results])
    except Exception as e:
        return _error_response(e, 500)


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                '''
            UPDATE products SET quantity = ? WHERE id = ?
        ''',
                (data['quantity'], data['id']),
            )
            conn.commit()
        return jsonify({'message': 'Quantity updated successfully'})
    except Exception as e:
        return _error_response(e, 400)


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                'DELETE FROM products WHERE id = ?', (product_id,)
            )
            conn.commit()
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        return _error_response(e, 400)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
