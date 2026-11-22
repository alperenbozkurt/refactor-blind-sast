import sqlite3
from flask import Flask, request, jsonify
import json
from functools import wraps
import jwt
from datetime import datetime, timedelta
import os

app = Flask(__name__)

DATABASE = 'data.db'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

BEARER_PREFIX = 'Bearer '
REQUIRED_TOKEN_FIELDS = ['username', 'role', 'exp']
VALID_OPERATORS = ['=', '!=', '<', '>', '<=', '>=', 'LIKE', 'IN']

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


def error_response(message, status_code):
    """Build a JSON error response with the given HTTP status code."""
    return jsonify({'error': message}), status_code


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_PRODUCTS_TABLE)
    cursor.execute(CREATE_USERS_TABLE)
    conn.commit()
    conn.close()


def auth_required(role='user'):
    """Require a valid bearer token whose role is `role` or 'admin'."""

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return error_response('Authorization required', 401)
            try:
                if not auth.startswith(BEARER_PREFIX):
                    raise ValueError('Invalid authorization format')
                token = auth[len(BEARER_PREFIX):]
                user = verify_token(token)
                if user['role'] not in [role, 'admin']:
                    return error_response('Insufficient permissions', 403)
                return f(*args, **kwargs)
            except Exception as e:
                return error_response(str(e), 401)

        return wrapper

    return decorator


def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        if not all(key in payload for key in REQUIRED_TOKEN_FIELDS):
            raise ValueError('Invalid token structure')
        if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
            raise ValueError('Token expired')
        return {'username': payload['username'], 'role': payload['role']}
    except jwt.PyJWTError as e:
        raise ValueError(f'Invalid token: {str(e)}')


class QueryBuilder:

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.params = []
        self.limit = None

    def add_filter(self, field, operator, value):
        if not isinstance(field, str) or not field.replace('_', '').isalnum():
            raise ValueError('Invalid field name')
        if operator not in VALID_OPERATORS:
            raise ValueError(
                f"Invalid operator. Must be one of: {', '.join(VALID_OPERATORS)}"
            )
        self.filters.append(f'{field} {operator} ?')
        self.params.append(value)
        return self

    def set_limit(self, limit):
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError('Limit must be a positive integer')
        self.limit = limit
        return self

    def build(self):
        query = f'SELECT * FROM {self.table}'
        if self.filters:
            query += ' WHERE ' + ' AND '.join(self.filters)
        if self.limit:
            query += ' LIMIT ?'
            self.params.append(self.limit)
        return query

    def execute(self):
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            query = self.build()
            cursor.execute(query, self.params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise ValueError(f'Database error: {str(e)}')
        finally:
            conn.close()


@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    try:
        filters = request.args.getlist('filter')
        limit = request.args.get('limit', type=int)
        builder = QueryBuilder('products')
        for filter_spec in filters:
            parts = filter_spec.split(':', 2)
            if len(parts) == 3:
                field, operator, value = parts
                builder.add_filter(field, operator, value)
        if limit:
            builder.set_limit(limit)
        return jsonify(builder.execute())
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception:
        return error_response('Internal server error', 500)


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder('users')
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        return jsonify(builder.execute())
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception:
        return error_response('Internal server error', 500)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
