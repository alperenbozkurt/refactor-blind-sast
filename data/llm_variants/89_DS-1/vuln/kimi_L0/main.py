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

INSERT_PRODUCT = '''
    INSERT INTO products (name, price, quantity, category)
    VALUES (?, ?, ?, ?)
'''

UPDATE_PRODUCT_QUANTITY = 'UPDATE products SET quantity = ? WHERE id = ?'

DELETE_PRODUCT_BY_ID = 'DELETE FROM products WHERE id = ?'


@contextmanager
def db_connection():
    conn = sqlite3.connect(DATABASE)
    try:
        yield conn
    finally:
        conn.close()


def product_from_row(row):
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def init_db():
    with db_connection() as conn:
        conn.execute(CREATE_PRODUCTS_TABLE)
        conn.commit()


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        with db_connection() as conn:
            conn.execute(
                INSERT_PRODUCT,
                (data['name'], data['price'], data['quantity'], data['category']),
            )
            conn.commit()
        return jsonify({'message': 'Product added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        with db_connection() as conn:
            query = f"SELECT * FROM products WHERE name LIKE '%{search_term}%' OR category LIKE '%{search_term}%'"
            results = conn.execute(query).fetchall()
        products = [product_from_row(row) for row in results]
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        with db_connection() as conn:
            conn.execute(UPDATE_PRODUCT_QUANTITY, (data['quantity'], data['id']))
            conn.commit()
        return jsonify({'message': 'Quantity updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        with db_connection() as conn:
            conn.execute(DELETE_PRODUCT_BY_ID, (product_id,))
            conn.commit()
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
