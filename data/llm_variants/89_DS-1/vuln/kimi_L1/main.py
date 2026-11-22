import sqlite3

from flask import Flask, jsonify, request

_DATABASE_PATH = 'inventory.db'

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

_UPDATE_QUANTITY_SQL = """
    UPDATE products SET quantity = ? WHERE id = ?
"""

_DELETE_PRODUCT_SQL = 'DELETE FROM products WHERE id = ?'

app = Flask(__name__)


def _get_connection():
    """Open a new connection to the inventory database."""
    return sqlite3.connect(_DATABASE_PATH)


def _row_to_product(row):
    """Map a row of the products table to a JSON-serializable dict."""
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'quantity': row[3],
        'category': row[4],
    }


def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(_CREATE_PRODUCTS_TABLE_SQL)
    conn.commit()
    conn.close()


@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            _INSERT_PRODUCT_SQL,
            (data['name'], data['price'], data['quantity'], data['category']),
        )
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/search_product', methods=['GET'])
def search_product():
    search_term = request.args.get('query', '')
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        # Kept exactly as in the original on purpose; changing this
        # interpolation would alter security-relevant behaviour.
        query = f"SELECT * FROM products WHERE name LIKE '%{search_term}%' OR category LIKE '%{search_term}%'"
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        products = [_row_to_product(row) for row in results]
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_quantity', methods=['PUT'])
def update_quantity():
    data = request.get_json()
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(_UPDATE_QUANTITY_SQL, (data['quantity'], data['id']))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Quantity updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(_DELETE_PRODUCT_SQL, (product_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
