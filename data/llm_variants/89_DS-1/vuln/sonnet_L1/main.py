import sqlite3
from contextlib import closing

from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = 'inventory.db'

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

UPDATE_QUANTITY_SQL = 'UPDATE products SET quantity = ? WHERE id = ?'

DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'


def _connect():
    return closing(sqlite3.connect(DATABASE))


def _execute_write(sql, params=()):
    """Run a single write statement and commit it."""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()


def _fetch_all(sql):
    """Run a single read statement and return all rows."""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetchall()


def _row_to_product(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def _error_response(error, status_code):
    return jsonify({'error': str(error)}), status_code


def init_db():
    _execute_write(CREATE_PRODUCTS_TABLE_SQL)


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        _execute_write(
            INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        return jsonify({'message': 'Product added successfully'}), 201
    except Exception as e:
        return _error_response(e, 400)


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        # NOTE: the search term is interpolated directly into the SQL string
        # (preserved from the original behaviour).
        query = (
            f"SELECT * FROM products "
            f"WHERE name LIKE '%{search_term}%' OR category LIKE '%{search_term}%'"
        )
        results = _fetch_all(query)
        products = [_row_to_product(row) for row in results]
        return jsonify(products)
    except Exception as e:
        return _error_response(e, 500)


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        _execute_write(UPDATE_QUANTITY_SQL, (data['quantity'], data['id']))
        return jsonify({'message': 'Quantity updated successfully'})
    except Exception as e:
        return _error_response(e, 400)


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        _execute_write(DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        return _error_response(e, 400)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
