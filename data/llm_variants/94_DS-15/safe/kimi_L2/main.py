"""Flask API exposing authenticated product and user queries over SQLite."""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

DATABASE = 'data.db'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

PRODUCTS_TABLE = 'products'
USERS_TABLE = 'users'

AUTHORIZATION_HEADER = 'Authorization'
BEARER_PREFIX = 'Bearer '

JWT_ALGORITHM = 'HS256'
REQUIRED_CLAIMS = ('username', 'role', 'exp')
ADMIN_ROLE = 'admin'

FILTER_SEPARATOR = ':'
FILTER_PART_COUNT = 3

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

SCHEMA_STATEMENTS = (CREATE_PRODUCTS_TABLE, CREATE_USERS_TABLE)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _connect():
    """Open a new connection to the application database."""
    return sqlite3.connect(DATABASE)


def _error_response(message, status_code):
    """Build a JSON error response tuple of (response, status_code)."""
    return (jsonify({'error': message}), status_code)


def init_db():
    """Create the products and users tables if they do not already exist."""
    conn = _connect()
    cursor = conn.cursor()
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _extract_bearer_token(auth):
    """Return the token portion of an Authorization header value."""
    if not auth.startswith(BEARER_PREFIX):
        raise ValueError('Invalid authorization format')
    return auth[len(BEARER_PREFIX):]


def _has_required_role(user, role):
    """Check whether the user's role satisfies the required role."""
    return user['role'] in (role, ADMIN_ROLE)


def auth_required(role='user'):
    """Require a valid bearer token with at least the given role."""

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get(AUTHORIZATION_HEADER)
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


def _validate_token_claims(payload):
    """Ensure the decoded payload carries every required claim."""
    if not all((k in payload for k in REQUIRED_CLAIMS)):
        raise ValueError('Invalid token structure')


def _validate_token_expiry(payload):
    """Ensure the token's expiry timestamp is still in the future."""
    if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
        raise ValueError('Token expired')


def verify_token(token):
    """Decode a JWT and return its user identity after validation."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        _validate_token_claims(payload)
        _validate_token_expiry(payload)
        return {'username': payload['username'], 'role': payload['role']}
    except jwt.PyJWTError as e:
        raise ValueError(f'Invalid token: {str(e)}')

# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------


class QueryBuilder:
    """Fluent builder for simple parameterized SELECT queries."""

    VALID_OPERATORS = ('=', '!=', '<', '>', '<=', '>=', 'LIKE', 'IN')

    def __init__(self, table):
        self.table = table
        self.filters = []
        self.params = []
        self.limit = None

    def add_filter(self, field, operator, value):
        """Add a WHERE condition after validating field and operator."""
        self._validate_field(field)
        self._validate_operator(operator)
        self.filters.append(f'{field} {operator} ?')
        self.params.append(value)
        return self

    def set_limit(self, limit):
        """Set a positive integer row limit."""
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError('Limit must be a positive integer')
        self.limit = limit
        return self

    def build(self):
        """Render the SQL string.

        Note: the limit parameter is appended to ``self.params`` here,
        preserving the original semantics of repeated ``build()`` calls.
        """
        query = f'SELECT * FROM {self.table}'
        if self.filters:
            query += ' WHERE ' + ' AND '.join(self.filters)
        if self.limit:
            query += ' LIMIT ?'
            self.params.append(self.limit)
        return query

    def execute(self):
        """Run the built query and return all rows as dictionaries."""
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

    @staticmethod
    def _validate_field(field):
        """Reject field names that are not simple identifiers."""
        if not isinstance(field, str) or not field.replace('_', '').isalnum():
            raise ValueError('Invalid field name')

    @classmethod
    def _validate_operator(cls, operator):
        """Reject operators outside the supported whitelist."""
        if operator not in cls.VALID_OPERATORS:
            raise ValueError(
                'Invalid operator. Must be one of: '
                f"{', '.join(cls.VALID_OPERATORS)}"
            )

# ---------------------------------------------------------------------------
# Request parsing helpers
# ---------------------------------------------------------------------------


def _apply_filters(builder, raw_filters):
    """Apply 'field:operator:value' filter strings to the builder.

    Malformed filter strings (those not splitting into three parts)
    are silently ignored.
    """
    for raw_filter in raw_filters:
        parts = raw_filter.split(FILTER_SEPARATOR, 2)
        if len(parts) == FILTER_PART_COUNT:
            builder.add_filter(parts[0], parts[1], parts[2])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route('/api/products', methods=['GET'])
@auth_required()
def get_products():
    """List products, with optional filters and a row limit."""
    try:
        builder = QueryBuilder(PRODUCTS_TABLE)
        _apply_filters(builder, request.args.getlist('filter'))
        limit = request.args.get('limit', type=int)
        if limit:
            builder.set_limit(limit)
        products = builder.execute()
        return jsonify(products)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


@app.route('/api/users', methods=['GET'])
@auth_required('admin')
def get_users():
    """List users (admin only), with an optional row limit."""
    try:
        builder = QueryBuilder(USERS_TABLE)
        if 'limit' in request.args:
            builder.set_limit(request.args.get('limit', type=int))
        users = builder.execute()
        return jsonify(users)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Initialize the database and start the application server."""
    init_db()
    app.run(debug=False)


if __name__ == '__main__':
    main()
