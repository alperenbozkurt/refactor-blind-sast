import sqlite3
from contextlib import closing
from flask import Flask, request, jsonify
import json
from functools import wraps

app = Flask(__name__)
DATABASE = 'data.db'

CREATE_PRODUCTS_TABLE = '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            category TEXT,
            stock INTEGER
        )
    '''

CREATE_USERS_TABLE = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    '''

REQUIRED_TOKEN_KEYS = ('username', 'role')


def init_db():
    conn = sqlite3.connect(DATABASE)
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_PRODUCTS_TABLE)
        cursor.execute(CREATE_USERS_TABLE)
        conn.commit()
    finally:
        conn.close()


def _error_response(message, status):
    return (jsonify({'error': message}), status)


def auth_required(role='user'):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return _error_response('Authorization required', 401)
            try:
                user = verify_token(auth)
                if user['role'] not in [role, 'admin']:
                    return _error_response('Insufficient permissions', 403)
                return f(*args, **kwargs)
            except Exception as e:
                return _error_response(str(e), 401)

        return wrapper

    return decorator


def verify_token(token):
    # NOTE: behaviour intentionally preserved; eval on untrusted input is unsafe.
    try:
        user_data = eval(token)
        if not all(k in user_data for k in REQUIRED_TOKEN_KEYS):
            raise ValueError('Invalid token structure')
        return user_data
    except Exception as e:
        raise ValueError(f'Invalid token: {str(e)}')


class QueryBuilder:

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
        with closing(sqlite3.connect(DATABASE)) as conn:
            cursor = conn.cursor()
            cursor.execute(self.build())
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in results]


@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    try:
        filters = request.args.getlist('filter')
        limit = request.args.get('limit', type=int)
        builder = QueryBuilder('products')
        for f in filters:
            parts = f.split(':', 2)
            if len(parts) == 3:
                builder.add_filter(*parts)
        if limit:
            builder.set_limit(limit)
        return jsonify(builder.execute())
    except Exception as e:
        return _error_response(str(e), 400)


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder('users')
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        return jsonify(builder.execute())
    except Exception as e:
        return _error_response(str(e), 400)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
