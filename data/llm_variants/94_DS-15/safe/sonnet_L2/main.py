import sqlite3
from flask import Flask, request, jsonify
import json
from functools import wraps
import jwt
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE = 'data.db'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

JWT_ALGORITHMS = ['HS256']
REQUIRED_TOKEN_CLAIMS = ['username', 'role', 'exp']
BEARER_PREFIX = 'Bearer '
ADMIN_ROLE = 'admin'
DEFAULT_ROLE = 'user'

VALID_OPERATORS = ['=', '!=', '<', '>', '<=', '>=', 'LIKE', 'IN']
FILTER_SEPARATOR = ':'
FILTER_PARTS = 3

CREATE_PRODUCTS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS products (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL,\n            price REAL,\n            category TEXT,\n            stock INTEGER\n        )\n    '
CREATE_USERS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS users (\n            id INTEGER PRIMARY KEY,\n            username TEXT UNIQUE,\n            password TEXT,\n            role TEXT\n        )\n    '
SCHEMA_STATEMENTS = (CREATE_PRODUCTS_TABLE_SQL, CREATE_USERS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _connect():
    """Open a new connection to the currently configured database."""
    return sqlite3.connect(DATABASE)


def _error_response(message, status):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status)


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------
def init_db():
    conn = _connect()
    cursor = conn.cursor()
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _extract_bearer_token(auth_header):
    if not auth_header.startswith(BEARER_PREFIX):
        raise ValueError('Invalid authorization format')
    return auth_header[len(BEARER_PREFIX):]


def _has_required_role(user, role):
    return user['role'] in [role, ADMIN_ROLE]


def auth_required(role=DEFAULT_ROLE):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return _error_response('Authorization required', 401)
            try:
                token = _extract_bearer_token(auth)
                user = verify_token(token)
                if not _has_required_role(user, role):
                    return _error_response('Insufficient permissions', 403)
                return f(*args, **kwargs)
            except Exception as e:
                return _error_response(str(e), 401)
        return wrapper
    return decorator


def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=JWT_ALGORITHMS)
        if not all((k in payload for k in REQUIRED_TOKEN_CLAIMS)):
            raise ValueError('Invalid token structure')
        if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
            raise ValueError('Token expired')
        return {'username': payload['username'], 'role': payload['role']}
    except jwt.PyJWTError as e:
        raise ValueError(f'Invalid token: {str(e)}')


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------
class QueryBuilder:

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.params = []
        self.limit = None

    @staticmethod
    def _validate_field(field):
        if not isinstance(field, str) or not field.replace('_', '').isalnum():
            raise ValueError('Invalid field name')

    @staticmethod
    def _validate_operator(operator):
        if operator not in VALID_OPERATORS:
            raise ValueError(f"Invalid operator. Must be one of: {', '.join(VALID_OPERATORS)}")

    def add_filter(self, field, operator, value):
        self._validate_field(field)
        self._validate_operator(operator)
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
        conn = _connect()
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def _apply_request_filters(builder, raw_filters):
    """Apply well-formed 'field:operator:value' filters to the builder."""
    for raw in raw_filters:
        parts = raw.split(FILTER_SEPARATOR, FILTER_PARTS - 1)
        if len(parts) == FILTER_PARTS:
            builder.add_filter(parts[0], parts[1], parts[2])


@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    try:
        filters = request.args.getlist('filter')
        limit = request.args.get('limit', type=int)
        builder = QueryBuilder('products')
        _apply_request_filters(builder, filters)
        if limit:
            builder.set_limit(limit)
        products = builder.execute()
        return jsonify(products)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception as e:
        return _error_response('Internal server error', 500)


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder('users')
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        users = builder.execute()
        return jsonify(users)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception as e:
        return _error_response('Internal server error', 500)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
