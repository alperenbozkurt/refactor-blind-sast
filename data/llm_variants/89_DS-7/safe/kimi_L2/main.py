"""Hotel booking web service.

A small Bottle + SQLite application structured for a larger codebase:

* runtime settings live in the frozen :class:`Config` object (``CONFIG``),
* SQL statements, seed rows and user-facing messages are named constants,
* database access, validation and response formatting are delegated to
  small single-purpose helper functions,
* the public interface (module-level names, routes, function signatures
  and the command-line entry point) is unchanged.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from bottle import Bottle, request, response, run

app = Bottle()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    """Runtime configuration for the service."""

    database_path: str = 'hotel.db'
    host: str = 'localhost'
    port: int = 8080
    debug: bool = False


CONFIG = Config()

DATE_FORMAT = '%Y-%m-%d'
GUEST_NAME_PATTERN = re.compile(r'^[a-zA-Z\s\-]{2,100}$')
REQUIRED_BOOKING_FIELDS = ('room_id', 'guest_name', 'check_in_date', 'check_out_date')


# ---------------------------------------------------------------------------
# User-facing messages
# ---------------------------------------------------------------------------

MSG_MISSING_FIELDS = 'Missing required fields'
MSG_INVALID_DATE = 'Invalid date format. Use YYYY-MM-DD'
MSG_INVALID_GUEST_NAME = 'Invalid guest name'
MSG_INVALID_MAX_PRICE = 'Invalid max_price value'
MSG_ROOM_NOT_FOUND = 'Room not found'
MSG_ROOM_UNAVAILABLE = 'Room not available for selected dates'
MSG_BOOKING_CREATION_FAILED = 'Booking creation failed'
MSG_INVALID_BOOKING_ID = 'Invalid booking ID'
MSG_BOOKING_NOT_FOUND = 'Booking not found'
MSG_CANCEL_FAILED = 'Failed to cancel booking'
MSG_INTERNAL_ERROR = 'Internal server error'


# ---------------------------------------------------------------------------
# SQL statements and seed data
# ---------------------------------------------------------------------------

SQL_CREATE_ROOMS_TABLE = """
CREATE TABLE IF NOT EXISTS rooms (
    room_id INTEGER PRIMARY KEY,
    room_number TEXT UNIQUE NOT NULL,
    room_type TEXT NOT NULL,
    price_per_night REAL NOT NULL,
    max_occupancy INTEGER NOT NULL,
    amenities TEXT
)
"""

SQL_CREATE_BOOKINGS_TABLE = """
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY,
    room_id INTEGER NOT NULL,
    guest_name TEXT NOT NULL,
    check_in_date TEXT NOT NULL,
    check_out_date TEXT NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY(room_id) REFERENCES rooms(room_id)
)
"""

SQL_COUNT_ROOMS = 'SELECT COUNT(*) FROM rooms'

SQL_INSERT_ROOM = (
    'INSERT INTO rooms (room_number, room_type, price_per_night, '
    'max_occupancy, amenities) VALUES (?, ?, ?, ?, ?)'
)

SQL_INSERT_BOOKING = (
    'INSERT INTO bookings (room_id, guest_name, check_in_date, '
    'check_out_date, total_price) VALUES (?, ?, ?, ?, ?)'
)

SQL_SELECT_ROOM_EXISTS = 'SELECT 1 FROM rooms WHERE room_id = ?'
SQL_SELECT_ROOM_PRICE = 'SELECT price_per_night FROM rooms WHERE room_id = ?'

SQL_SELECT_BOOKING_CONFLICT = """
SELECT 1 FROM bookings
WHERE room_id = ? AND (
    (? BETWEEN check_in_date AND check_out_date) OR
    (? BETWEEN check_in_date AND check_out_date) OR
    (check_in_date BETWEEN ? AND ?) OR
    (check_out_date BETWEEN ? AND ?)
)
"""

SQL_DELETE_BOOKING = 'DELETE FROM bookings WHERE booking_id = ?'

SQL_SEARCH_ROOMS_BASE = 'SELECT * FROM rooms WHERE 1=1'
SQL_FILTER_ROOM_TYPE = ' AND room_type LIKE ?'
SQL_FILTER_MAX_PRICE = ' AND price_per_night <= ?'
SQL_FILTER_AVAILABLE_ON = (
    ' AND room_id NOT IN ('
    'SELECT room_id FROM bookings '
    'WHERE ? BETWEEN check_in_date AND check_out_date)'
)

SEED_ROOMS = [
    ('101', 'Standard', 99.99, 2, 'TV,WiFi'),
    ('201', 'Deluxe', 149.99, 3, 'TV,WiFi,Minibar'),
    ('301', 'Suite', 249.99, 4, 'TV,WiFi,Minibar,Jacuzzi'),
]

SEED_BOOKINGS = [
    (1, 'John Smith', '2023-06-01', '2023-06-05', 399.96),
    (2, 'Alice Johnson', '2023-06-10', '2023-06-15', 749.95),
]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db_connection():
    """Yield an open SQLite connection and guarantee it is closed."""
    conn = sqlite3.connect(CONFIG.database_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create the schema (if needed) and seed an empty database."""
    with _db_connection() as conn:
        cursor = conn.cursor()
        _create_schema(cursor)
        _seed_if_empty(cursor)
        conn.commit()


def _create_schema(cursor):
    cursor.execute(SQL_CREATE_ROOMS_TABLE)
    cursor.execute(SQL_CREATE_BOOKINGS_TABLE)


def _seed_if_empty(cursor):
    cursor.execute(SQL_COUNT_ROOMS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(SQL_INSERT_ROOM, SEED_ROOMS)
        cursor.executemany(SQL_INSERT_BOOKING, SEED_BOOKINGS)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_booking_data(data):
    """Validate a booking payload, raising ``ValueError`` when invalid."""
    if not all(field in data for field in REQUIRED_BOOKING_FIELDS):
        raise ValueError(MSG_MISSING_FIELDS)
    _validate_stay_dates(data['check_in_date'], data['check_out_date'])
    _validate_guest_name(data['guest_name'])
    return True


def _validate_stay_dates(check_in_date, check_out_date):
    try:
        check_in = datetime.strptime(check_in_date, DATE_FORMAT)
        check_out = datetime.strptime(check_out_date, DATE_FORMAT)
        if check_in >= check_out:
            # Deliberately re-raised as the generic date-format error
            # below, preserving the original externally visible message.
            raise ValueError('Check-out date must be after check-in date')
    except ValueError:
        raise ValueError(MSG_INVALID_DATE)


def _validate_guest_name(guest_name):
    if not GUEST_NAME_PATTERN.match(guest_name):
        raise ValueError(MSG_INVALID_GUEST_NAME)


def _parse_optional_float(raw_value):
    """Return ``float(raw_value)`` for a non-empty string, else ``None``."""
    if not raw_value:
        return None
    return float(raw_value)


def _is_valid_date(value):
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# Response / mapping helpers
# ---------------------------------------------------------------------------

def _error_response(message, status):
    response.status = status
    return json.dumps({'error': message})


def _room_row_to_dict(row):
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


# ---------------------------------------------------------------------------
# Booking query helpers
# ---------------------------------------------------------------------------

def _build_room_search_query(room_type, max_price, check_date):
    query = SQL_SEARCH_ROOMS_BASE
    params = []
    if room_type:
        query += SQL_FILTER_ROOM_TYPE
        params.append(f'%{room_type}%')
    if max_price is not None:
        query += SQL_FILTER_MAX_PRICE
        params.append(max_price)
    if check_date:
        query += SQL_FILTER_AVAILABLE_ON
        params.append(check_date)
    return query, params


def _room_exists(cursor, room_id):
    cursor.execute(SQL_SELECT_ROOM_EXISTS, (room_id,))
    return cursor.fetchone() is not None


def _has_booking_conflict(cursor, data):
    cursor.execute(
        SQL_SELECT_BOOKING_CONFLICT,
        (
            data['room_id'],
            data['check_in_date'],
            data['check_out_date'],
            data['check_in_date'],
            data['check_out_date'],
            data['check_in_date'],
            data['check_out_date'],
        ),
    )
    return cursor.fetchone() is not None


def _calculate_total_price(cursor, data):
    cursor.execute(SQL_SELECT_ROOM_PRICE, (data['room_id'],))
    price_per_night = cursor.fetchone()[0]
    nights = (
        datetime.strptime(data['check_out_date'], DATE_FORMAT)
        - datetime.strptime(data['check_in_date'], DATE_FORMAT)
    ).days
    return price_per_night * nights


def _insert_booking(cursor, data, total_price):
    cursor.execute(
        SQL_INSERT_BOOKING,
        (
            data['room_id'],
            data['guest_name'],
            data['check_in_date'],
            data['check_out_date'],
            total_price,
        ),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/rooms/search', method='GET')
def search_rooms():
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')

    with _db_connection() as conn:
        try:
            max_price_value = _parse_optional_float(max_price)
        except ValueError:
            return _error_response(MSG_INVALID_MAX_PRICE, 400)

        if check_date and not _is_valid_date(check_date):
            return _error_response(MSG_INVALID_DATE, 400)

        query, params = _build_room_search_query(room_type, max_price_value, check_date)
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rooms = [_room_row_to_dict(row) for row in cursor.fetchall()]
        except Exception:
            return _error_response(MSG_INTERNAL_ERROR, 500)

    response.content_type = 'application/json'
    return json.dumps({'rooms': rooms})


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        validate_booking_data(data)

        with _db_connection() as conn:
            cursor = conn.cursor()

            if not _room_exists(cursor, data['room_id']):
                return _error_response(MSG_ROOM_NOT_FOUND, 404)

            if _has_booking_conflict(cursor, data):
                return _error_response(MSG_ROOM_UNAVAILABLE, 400)

            total_price = _calculate_total_price(cursor, data)
            booking_id = _insert_booking(cursor, data, total_price)
            conn.commit()

        response.content_type = 'application/json'
        return json.dumps({'booking_id': booking_id, 'total_price': total_price})
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception:
        return _error_response(MSG_BOOKING_CREATION_FAILED, 500)


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        if not booking_id or not booking_id.isdigit():
            return _error_response(MSG_INVALID_BOOKING_ID, 400)

        with _db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SQL_DELETE_BOOKING, (booking_id,))
            conn.commit()
            affected_rows = cursor.rowcount

        if affected_rows == 0:
            return _error_response(MSG_BOOKING_NOT_FOUND, 404)
        return json.dumps({'status': 'success'})
    except Exception:
        return _error_response(MSG_CANCEL_FAILED, 500)


if __name__ == '__main__':
    init_db()
    run(app, host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug)
