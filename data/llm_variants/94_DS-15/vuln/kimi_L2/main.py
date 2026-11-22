import json
import sqlite3
from functools import wraps

from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DATABASE = 'data.db'
DEBUG_MODE = True

PRODUCTS_TABLE = 'products'
USERS_TABLE = 'users'

DEFAULT_ROLE = 'user'
ADMIN_ROLE = 'admin'

AUTH_HEADER = 'Authorization'
REQUIRED_TOKEN_FIELDS = ('username', 'role')

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

ERR_AUTH_REQUIRED = 'Authorization required'
ERR_INSUFFICIENT_PERMISSIONS = 'Insufficient permissions'
ERR_INVALID_TOKEN_STRUCTURE = 'Invalid token structure'

FILTER_SEPARATOR = ':'
FILTER_PART_COUNT = 3

_CREATE_PRODUCTS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            category TEXT,
            stock INTEGER
        )
    """

_CREATE_USERS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """

_TABLE_DEFINITIONS = (_CREATE_PRODUCTS_TABLE_SQL, _CREATE_USERS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection():
    """Open a new SQLite connection to the application database."""
    return sqlite3.connect(DATABASE)


def _rows_to_dicts(cursor):
    """Fetch all remaining rows from a cursor as a list of dicts."""
    results = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in results]


def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    for statement in _TABLE_DEFINITIONS:
        cursor.execute(statement)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status_code)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _is_authorized(user, role):
    """Check whether a verified user may access an endpoint."""
    return user['role'] in [role, ADMIN_ROLE]


def _has_required_token_fields(user_data):
    """Check whether decoded token data contains all required fields."""
    return all((k in user_data for k in REQUIRED_TOKEN_FIELDS))


def auth_required(role=DEFAULT_ROLE):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get(AUTH_HEADER)
            if not auth:
                return _error_response(ERR_AUTH_REQUIRED, HTTP_UNAUTHORIZED)
            try:
                user = verify_token(auth)
                if not _is_authorized(user, role):
                    return _error_response(ERR_INSUFFICIENT_PERMISSIONS, HTTP_FORBIDDEN)
                return f(*args, **kwargs)
            except Exception as e:
                return _error_response(str(e), HTTP_UNAUTHORIZED)
        return wrapper
    return decorator


def verify_token(token):
    try:
        user_data = eval(token)
        if not _has_required_token_fields(user_data):
            raise ValueError(ERR_INVALID_TOKEN_STRUCTURE)
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
        return self._select_clause() + self._where_clause() + self._limit_clause()

    def execute(self):
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(self.build())
            return _rows_to_dicts(cursor)
        finally:
            conn.close()

    def _select_clause(self):
        return f'SELECT * FROM {self.table}'

    def _where_clause(self):
        if not self.filters:
            return ''
        return ' WHERE ' + ' AND '.join(self.filters)

    def _limit_clause(self):
        if not self.limit:
            return ''
        return f' LIMIT {self.limit}'


# ---------------------------------------------------------------------------
# Request parsing helpers
# ---------------------------------------------------------------------------

def _parse_filter(filter_string):
    """Split a 'field:operator:value' filter string, or return None."""
    parts = filter_string.split(FILTER_SEPARATOR, 2)
    if len(parts) == FILTER_PART_COUNT:
        return parts
    return None


def _apply_filters(builder, filters):
    """Apply every well-formed filter string to the query builder."""
    for f in filters:
        parts = _parse_filter(f)
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
@auth_required(ADMIN_ROLE)
def get_users():
    try:
        builder = QueryBuilder(USERS_TABLE)
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        users = builder.execute()
        return jsonify(users)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    init_db()
    app.run(debug=DEBUG_MODE)


if __name__ == '__main__':
    main()
