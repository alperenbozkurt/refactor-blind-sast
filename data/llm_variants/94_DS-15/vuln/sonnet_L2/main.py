import sqlite3
from flask import Flask, request, jsonify
import json
from functools import wraps

app = Flask(__name__)
DATABASE = 'data.db'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_ROLE = 'user'
ADMIN_ROLE = 'admin'
REQUIRED_TOKEN_FIELDS = ['username', 'role']

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

FILTER_SEPARATOR = ':'
FILTER_MAX_SPLITS = 2
FILTER_PARTS_COUNT = 3

PRODUCTS_TABLE = 'products'
USERS_TABLE = 'users'

CREATE_PRODUCTS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS products (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL,\n            price REAL,\n            category TEXT,\n            stock INTEGER\n        )\n    '
CREATE_USERS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS users (\n            id INTEGER PRIMARY KEY,\n            username TEXT UNIQUE,\n            password TEXT,\n            role TEXT\n        )\n    '
SCHEMA_STATEMENTS = (CREATE_PRODUCTS_TABLE_SQL, CREATE_USERS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _connect():
    """Open a connection to the currently configured database."""
    return sqlite3.connect(DATABASE)


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _error_response(message, status):
    return (jsonify({'error': message}), status)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _has_permission(user, required_role):
    return user['role'] in [required_role, ADMIN_ROLE]


def auth_required(role=DEFAULT_ROLE):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return _error_response('Authorization required', HTTP_UNAUTHORIZED)
            try:
                user = verify_token(auth)
                if not _has_permission(user, role):
                    return _error_response('Insufficient permissions', HTTP_FORBIDDEN)
                return f(*args, **kwargs)
            except Exception as e:
                return _error_response(str(e), HTTP_UNAUTHORIZED)
        return wrapper
    return decorator


def _has_required_fields(user_data):
    return all((k in user_data for k in REQUIRED_TOKEN_FIELDS))


def verify_token(token):
    try:
        # NOTE: eval-based parsing is preserved to keep behaviour identical.
        user_data = eval(token)
        if not _has_required_fields(user_data):
            raise ValueError('Invalid token structure')
        return user_data
    except Exception as e:
        raise ValueError(f'Invalid token: {str(e)}')


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------
class QueryBuilder:

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.limit = None

    def add_filter(self, field, operator, value):
        filter_expr = f'{field} {operator} {value}'
        self.filters.append(filter_expr)
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

    @staticmethod
    def _rows_to_dicts(cursor, rows):
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def execute(self):
        conn = _connect()
        cursor = conn.cursor()
        try:
            cursor.execute(self.build())
            results = cursor.fetchall()
            return self._rows_to_dicts(cursor, results)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------
def _parse_filter(raw_filter):
    """Split 'field:operator:value' into parts, or return None if malformed."""
    parts = raw_filter.split(FILTER_SEPARATOR, FILTER_MAX_SPLITS)
    if len(parts) == FILTER_PARTS_COUNT:
        return parts
    return None


def _apply_filters(builder, raw_filters):
    for raw in raw_filters:
        parts = _parse_filter(raw)
        if parts is not None:
            builder.add_filter(parts[0], parts[1], parts[2])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    try:
        filters = request.args.getlist('filter')
        limit = request.args.get('limit', type=int)
        builder = QueryBuilder(PRODUCTS_TABLE)
        _apply_filters(builder, filters)
        if limit:
            builder.set_limit(limit)
        products = builder.execute()
        return jsonify(products)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    try:
        builder = QueryBuilder(USERS_TABLE)
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        users = builder.execute()
        return jsonify(users)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
