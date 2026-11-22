from contextlib import closing
from datetime import datetime
import json
import sqlite3

from bottle import Bottle, request, response, run

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
DB_PATH = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'
JSON_CONTENT_TYPE = 'application/json'

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
SERVER_DEBUG = True

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

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

INSERT_ROOM_SQL = '''
            INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_BOOKING_SQL = '''
            INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
            VALUES (?, ?, ?, ?, ?)
        '''

COUNT_ROOMS_SQL = 'SELECT COUNT(*) FROM rooms'
SELECT_ROOM_PRICE_SQL = 'SELECT price_per_night FROM rooms WHERE room_id = ?'
DELETE_BOOKING_SQL = 'DELETE FROM bookings WHERE booking_id = ?'

SEARCH_ROOMS_BASE_SQL = 'SELECT * FROM rooms WHERE room_type LIKE ?'
SEARCH_ROOMS_MAX_PRICE_SQL = ' AND price_per_night <= ?'
SEARCH_ROOMS_AVAILABILITY_SQL = (
    ' AND room_id NOT IN ('
    ' SELECT room_id FROM bookings'
    ' WHERE ? BETWEEN check_in_date AND check_out_date'
    ')'
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

app = Bottle()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _connect():
    """Return a new connection to the hotel database."""
    return sqlite3.connect(DB_PATH)


def _json_success(payload):
    """Serialize a successful payload as a JSON response."""
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(payload)


def _json_error(message, status):
    """Set the HTTP status and serialize an error payload."""
    response.status = status
    return json.dumps({'error': message})


def _row_to_room(row):
    """Convert a rooms table row into its API representation."""
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


def _build_search_query(room_type, max_price, check_date):
    """Build the (parameterized) room search SQL and its parameters."""
    query = SEARCH_ROOMS_BASE_SQL
    params = [f'%{room_type}%']
    if max_price:
        query += SEARCH_ROOMS_MAX_PRICE_SQL
        params.append(float(max_price))
    if check_date:
        query += SEARCH_ROOMS_AVAILABILITY_SQL
        params.append(check_date)
    return query, params


def _calculate_nights(check_in_date, check_out_date):
    """Return the number of nights between two ISO formatted dates."""
    check_in = datetime.strptime(check_in_date, DATE_FORMAT)
    check_out = datetime.strptime(check_out_date, DATE_FORMAT)
    return (check_out - check_in).days


def _seed_database(cursor):
    """Insert the default rooms and bookings when no rooms exist."""
    cursor.execute(COUNT_ROOMS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM_SQL, SEED_ROOMS)
        cursor.executemany(INSERT_BOOKING_SQL, SEED_BOOKINGS)


# --------------------------------------------------------------------------- #
# Database initialization
# --------------------------------------------------------------------------- #
def init_db():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_ROOMS_TABLE_SQL)
        cursor.execute(CREATE_BOOKINGS_TABLE_SQL)
        _seed_database(cursor)
        conn.commit()


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
            cursor.execute(query, params)
            rooms = [_row_to_room(row) for row in cursor.fetchall()]
            return _json_success({'rooms': rooms})
        except Exception as e:
            return _json_error(str(e), HTTP_SERVER_ERROR)


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_ROOM_PRICE_SQL, (data['room_id'],))
            price_per_night = cursor.fetchone()[0]
            nights = _calculate_nights(data['check_in_date'], data['check_out_date'])
            total_price = price_per_night * nights
            cursor.execute(
                INSERT_BOOKING_SQL,
                (
                    data['room_id'],
                    data['guest_name'],
                    data['check_in_date'],
                    data['check_out_date'],
                    total_price,
                ),
            )
            conn.commit()
            booking_id = cursor.lastrowid
        return _json_success({'booking_id': booking_id, 'total_price': total_price})
    except Exception as e:
        return _json_error(str(e), HTTP_BAD_REQUEST)


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(DELETE_BOOKING_SQL, (booking_id,))
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return _json_error('Booking not found', HTTP_NOT_FOUND)
        return json.dumps({'status': 'success'})
    except Exception as e:
        return _json_error(str(e), HTTP_SERVER_ERROR)


if __name__ == '__main__':
    init_db()
    run(app, host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
