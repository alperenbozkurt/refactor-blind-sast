import json
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, jsonify, request

app = Flask(__name__)
DATABASE = 'data.db'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')


def init_db():
    statements = (
        '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            category TEXT,
            stock INTEGER
        )
    ''',
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''',
    )
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    for statement in statements:
        cursor.execute(statement)
    conn.commit()
    conn.close()


def _extract_bearer_token(auth):
    if not auth.startswith('Bearer '):
        raise ValueError('Invalid authorization format')
    return auth[len('Bearer '):]


def auth_required(role='user'):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return jsonify({'error': 'Authorization required'}), 401
            try:
                token = _extract_bearer_token(auth)
                user = verify_token(token)
                if user['role'] not in (role, 'admin'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': str(e)}), 401
        return wrapper
    return decorator


def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        required_claims = ('username', 'role', 'exp')
        if not all(key in payload for key in required_claims):
            raise ValueError('Invalid token structure')
        if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
            raise ValueError('Token expired')
        return {'username': payload['username'], 'role': payload['role']}
    except jwt.PyJWTError as e:
        raise ValueError(f'Invalid token: {str(e)}')


class QueryBuilder:
    VALID_OPERATORS = ('=', '!=', '<', '>', '<=', '>=', 'LIKE', 'IN')

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.params = []
        self.limit = None

    def add_filter(self, field, operator, value):
        if not isinstance(field, str) or not field.replace('_', '').isalnum():
            raise ValueError('Invalid field name')
        if operator not in self.VALID_OPERATORS:
            raise ValueError(
                f"Invalid operator. Must be one of: {', '.join(self.VALID_OPERATORS)}"
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
        for f in filters:
            parts = f.split(':', 2)
            if len(parts) == 3:
                builder.add_filter(*parts)
        if limit:
            builder.set_limit(limit)
        return jsonify(builder.execute())
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder('users')
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        return jsonify(builder.execute())
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
