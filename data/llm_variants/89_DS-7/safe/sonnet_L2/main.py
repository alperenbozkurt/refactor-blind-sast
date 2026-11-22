from bottle import Bottle, request, response, run
import sqlite3
import json
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import re

app = Bottle()

# --------------------------------------------------------------------------- #
# Configuration and constants
# --------------------------------------------------------------------------- #

DB_PATH = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'
JSON_CONTENT_TYPE = 'application/json'

GUEST_NAME_PATTERN = '^[a-zA-Z\\s\\-]{2,100}$'
REQUIRED_BOOKING_FIELDS = ['room_id', 'guest_name', 'check_in_date', 'check_out_date']

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

ERR_MISSING_FIELDS = 'Missing required fields'
ERR_CHECKOUT_BEFORE_CHECKIN = 'Check-out date must be after check-in date'
ERR_INVALID_DATE = 'Invalid date format. Use YYYY-MM-DD'
ERR_INVALID_GUEST_NAME = 'Invalid guest name'
ERR_INVALID_MAX_PRICE = 'Invalid max_price value'
ERR_INTERNAL = 'Internal server error'
ERR_ROOM_NOT_FOUND = 'Room not found'
ERR_ROOM_UNAVAILABLE = 'Room not available for selected dates'
ERR_BOOKING_FAILED = 'Booking creation failed'
ERR_INVALID_BOOKING_ID = 'Invalid booking ID'
ERR_BOOKING_NOT_FOUND = 'Booking not found'
ERR_CANCEL_FAILED = 'Failed to cancel booking'

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #

CREATE_ROOMS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            price_per_night REAL NOT NULL,
            max_occupancy INTEGER NOT NULL,
            amenities TEXT
        )
    '''

CREATE_BOOKINGS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY,
            room_id INTEGER NOT NULL,
            guest_name TEXT NOT NULL,
            check_in_date TEXT NOT NULL,
            check_out_date TEXT NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY(room_id) REFERENCES rooms(room_id)
        )
    '''

COUNT_ROOMS_SQL = 'SELECT COUNT(*) FROM rooms'

INSERT_ROOM_SQL = '''
            INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_BOOKING_SQL = '''
            INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
            VALUES (?, ?, ?, ?, ?)
        '''

SEARCH_ROOMS_BASE_SQL = 'SELECT * FROM rooms WHERE 1=1'
SEARCH_ROOM_TYPE_CLAUSE = ' AND room_type LIKE ?'
SEARCH_MAX_PRICE_CLAUSE = ' AND price_per_night <= ?'
SEARCH_AVAILABILITY_CLAUSE = ' AND room_id NOT IN (\n                SELECT room_id FROM bookings \n                WHERE ? BETWEEN check_in_date AND check_out_date\n            )'

ROOM_EXISTS_SQL = 'SELECT 1 FROM rooms WHERE room_id = ?'

BOOKING_CONFLICT_SQL = '''
            SELECT 1 FROM bookings 
            WHERE room_id = ? AND (
                (? BETWEEN check_in_date AND check_out_date) OR
                (? BETWEEN check_in_date AND check_out_date) OR
                (check_in_date BETWEEN ? AND ?) OR
                (check_out_date BETWEEN ? AND ?)
            )
        '''

ROOM_PRICE_SQL = 'SELECT price_per_night FROM rooms WHERE room_id = ?'
DELETE_BOOKING_SQL = 'DELETE FROM bookings WHERE booking_id = ?'

# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #

SEED_ROOMS = [
    ('101', 'Standard', 99.99, 2, 'TV,WiFi'),
    ('201', 'Deluxe', 149.99, 3, 'TV,WiFi,Minibar'),
    ('301', 'Suite', 249.99, 4, 'TV,WiFi,Minibar,Jacuzzi'),
]

SEED_BOOKINGS = [
    (1, 'John Smith', '2023-06-01', '2023-06-05', 399.96),
    (2, 'Alice Johnson', '2023-06-10', '2023-06-15', 749.95),
]


@dataclass(frozen=True)
class ServerConfig:
    host: str = 'localhost'
    port: int = 8080
    debug: bool = False


SERVER_CONFIG = ServerConfig()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _connect():
    return sqlite3.connect(DB_PATH)


def _error_response(status, message):
    """Set the HTTP status and return a JSON error body."""
    response.status = status
    return json.dumps({'error': message})


def _json_response(payload):
    """Set the JSON content type and return the serialized payload."""
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


def _parse_date(value):
    return datetime.strptime(value, DATE_FORMAT)


def _row_to_room(row):
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


def _seed_database(cursor):
    cursor.execute(COUNT_ROOMS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM_SQL, SEED_ROOMS)
        cursor.executemany(INSERT_BOOKING_SQL, SEED_BOOKINGS)


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_ROOMS_TABLE_SQL)
    cursor.execute(CREATE_BOOKINGS_TABLE_SQL)
    _seed_database(cursor)
    conn.commit()
    conn.close()


def _validate_dates(data):
    try:
        check_in = _parse_date(data['check_in_date'])
        check_out = _parse_date(data['check_out_date'])
        if check_in >= check_out:
            raise ValueError(ERR_CHECKOUT_BEFORE_CHECKIN)
    except ValueError:
        # Any ValueError (including the ordering check) is reported as a
        # date format error; this is the established behaviour.
        raise ValueError(ERR_INVALID_DATE)


def validate_booking_data(data):
    if not all((field in data for field in REQUIRED_BOOKING_FIELDS)):
        raise ValueError(ERR_MISSING_FIELDS)
    _validate_dates(data)
    if not re.match(GUEST_NAME_PATTERN, data['guest_name']):
        raise ValueError(ERR_INVALID_GUEST_NAME)
    return True


def _build_search_query(room_type, max_price, check_date):
    """Build the room search query; raises ValueError(message) on bad input."""
    query = SEARCH_ROOMS_BASE_SQL
    params = []
    if room_type:
        query += SEARCH_ROOM_TYPE_CLAUSE
        params.append(f'%{room_type}%')
    if max_price:
        try:
            max_price_float = float(max_price)
        except ValueError:
            raise ValueError(ERR_INVALID_MAX_PRICE)
        query += SEARCH_MAX_PRICE_CLAUSE
        params.append(max_price_float)
    if check_date:
        try:
            _parse_date(check_date)
        except ValueError:
            raise ValueError(ERR_INVALID_DATE)
        query += SEARCH_AVAILABILITY_CLAUSE
        params.append(check_date)
    return query, params


def _room_exists(cursor, room_id):
    cursor.execute(ROOM_EXISTS_SQL, (room_id,))
    return cursor.fetchone() is not None


def _has_conflicting_booking(cursor, data):
    check_in = data['check_in_date']
    check_out = data['check_out_date']
    cursor.execute(
        BOOKING_CONFLICT_SQL,
        (data['room_id'], check_in, check_out, check_in, check_out, check_in, check_out),
    )
    return cursor.fetchone() is not None


def _calculate_total_price(cursor, data):
    cursor.execute(ROOM_PRICE_SQL, (data['room_id'],))
    price_per_night = cursor.fetchone()[0]
    nights = (_parse_date(data['check_out_date']) - _parse_date(data['check_in_date'])).days
    return price_per_night * nights


def _insert_booking(cursor, data, total_price):
    cursor.execute(
        INSERT_BOOKING_SQL,
        (data['room_id'], data['guest_name'], data['check_in_date'], data['check_out_date'], total_price),
    )

# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.route('/rooms/search', method='GET')
def search_rooms():
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        try:
            query, params = _build_search_query(room_type, max_price, check_date)
        except ValueError as e:
            return _error_response(HTTP_BAD_REQUEST, str(e))
        try:
            cursor.execute(query, params)
            rooms = [_row_to_room(row) for row in cursor.fetchall()]
        except Exception:
            return _error_response(HTTP_SERVER_ERROR, ERR_INTERNAL)
    return _json_response({'rooms': rooms})


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        validate_booking_data(data)
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            if not _room_exists(cursor, data['room_id']):
                return _error_response(HTTP_NOT_FOUND, ERR_ROOM_NOT_FOUND)
            if _has_conflicting_booking(cursor, data):
                return _error_response(HTTP_BAD_REQUEST, ERR_ROOM_UNAVAILABLE)
            total_price = _calculate_total_price(cursor, data)
            _insert_booking(cursor, data, total_price)
            conn.commit()
            booking_id = cursor.lastrowid
        return _json_response({'booking_id': booking_id, 'total_price': total_price})
    except ValueError as e:
        return _error_response(HTTP_BAD_REQUEST, str(e))
    except Exception:
        return _error_response(HTTP_SERVER_ERROR, ERR_BOOKING_FAILED)


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        if not booking_id or not booking_id.isdigit():
            return _error_response(HTTP_BAD_REQUEST, ERR_INVALID_BOOKING_ID)
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(DELETE_BOOKING_SQL, (booking_id,))
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return _error_response(HTTP_NOT_FOUND, ERR_BOOKING_NOT_FOUND)
        return json.dumps({'status': 'success'})
    except Exception:
        return _error_response(HTTP_SERVER_ERROR, ERR_CANCEL_FAILED)


if __name__ == '__main__':
    init_db()
    run(app, host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)
