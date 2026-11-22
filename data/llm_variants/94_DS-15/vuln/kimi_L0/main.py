import json
import sqlite3
from functools import wraps

from flask import Flask, jsonify, request

app = Flask(__name__)
DATABASE = 'data.db'

CREATE_PRODUCTS_TABLE = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL,
        category TEXT,
        stock INTEGER
    )
"""

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
"""


def init_db():
    """Create the database tables if they do not already exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_PRODUCTS_TABLE)
    cursor.execute(CREATE_USERS_TABLE)
    conn.commit()
    conn.close()


def auth_required(role='user'):
    """Require a valid Authorization token with the given role (or admin)."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return jsonify({'error': 'Authorization required'}), 401
            try:
                user = verify_token(auth)
                if user['role'] not in (role, 'admin'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': str(e)}), 401

        return wrapper

    return decorator


def verify_token(token):
    """Decode a token into user data, raising ValueError if it is invalid."""
    try:
        user_data = eval(token)
        required_keys = ('username', 'role')
        if not all(key in user_data for key in required_keys):
            raise ValueError('Invalid token structure')
        return user_data
    except Exception as e:
        raise ValueError(f'Invalid token: {str(e)}')


class QueryBuilder:
    """Build and execute simple SELECT queries with filters and a limit."""

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.limit = None

    def add_filter(self, field, operator, value):
        self.filters.append(f'{field} {operator} {value}')
        return self

    def set_limit(self, limit):
        self.limit = limit
        return self

    def build(self):
        query = f'SELECT * FROM {self.table}'
        if self.filters:
            query += ' WHERE ' + ' AND '.join(self.filters)
        if self.limit:
            query += f' LIMIT {self.limit}'
        return query

    def execute(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute(self.build())
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in results]
        finally:
            conn.close()


@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    try:
        filters = request.args.getlist('filter')
        limit = request.args.get('limit', type=int)

        builder = QueryBuilder('products')
        for filter_param in filters:
            parts = filter_param.split(':', 2)
            if len(parts) == 3:
                builder.add_filter(*parts)
        if limit:
            builder.set_limit(limit)

        return jsonify(builder.execute())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder('users')
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))

        return jsonify(builder.execute())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
