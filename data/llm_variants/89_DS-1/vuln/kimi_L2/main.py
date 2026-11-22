"""Inventory management API backed by a SQLite database."""

import sqlite3
from contextlib import contextmanager

from flask import Flask, request, jsonify

DATABASE_PATH = 'inventory.db'

CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL,
        quantity INTEGER,
        category TEXT
    )
"""
INSERT_PRODUCT_SQL = """
    INSERT INTO products (name, price, quantity, category)
    VALUES (?, ?, ?, ?)
"""
UPDATE_PRODUCT_QUANTITY_SQL = 'UPDATE products SET quantity = ? WHERE id = ?'
DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

MESSAGE_PRODUCT_ADDED = 'Product added successfully'
MESSAGE_QUANTITY_UPDATED = 'Quantity updated successfully'
MESSAGE_PRODUCT_DELETED = 'Product deleted successfully'

app = Flask(__name__)


@contextmanager
def database_cursor():
    """Yield a cursor, committing on success and closing the connection after."""
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        yield connection.cursor()
        connection.commit()
    finally:
        connection.close()


def row_to_product(row):
    """Convert a products table row into its JSON-serializable dictionary form."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def build_search_query(search_term):
    """Build the product search query (kept verbatim from the original)."""
    return (
        'SELECT * FROM products WHERE '
        f"name LIKE '%{search_term}%' OR category LIKE '%{search_term}%'"
    )


def init_db():
    with database_cursor() as cursor:
        cursor.execute(CREATE_PRODUCTS_TABLE_SQL)


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        with database_cursor() as cursor:
            cursor.execute(
                INSERT_PRODUCT_SQL,
                (data['name'], data['price'], data['quantity'], data['category']),
            )
        return jsonify({'message': MESSAGE_PRODUCT_ADDED}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        with database_cursor() as cursor:
            cursor.execute(build_search_query(search_term))
            results = cursor.fetchall()
        return jsonify([row_to_product(row) for row in results])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        with database_cursor() as cursor:
            cursor.execute(
                UPDATE_PRODUCT_QUANTITY_SQL,
                (data['quantity'], data['id']),
            )
        return jsonify({'message': MESSAGE_QUANTITY_UPDATED})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        with database_cursor() as cursor:
            cursor.execute(DELETE_PRODUCT_SQL, (product_id,))
        return jsonify({'message': MESSAGE_PRODUCT_DELETED})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


def main():
    init_db()
    app.run(debug=True)


if __name__ == '__main__':
    main()
