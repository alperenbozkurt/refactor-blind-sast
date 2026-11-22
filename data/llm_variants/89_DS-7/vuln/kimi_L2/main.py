import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from bottle import Bottle, request, response, run

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Application configuration values."""

    db_path: str = 'hotel.db'
    host: str = 'localhost'
    port: int = 8080
    debug: bool = True
    date_format: str = '%Y-%m-%d'


CONFIG = Config()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

ERROR_BOOKING_NOT_FOUND = 'Booking not found'

CREATE_ROOMS_TABLE = '''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            price_per_night REAL NOT NULL,
            max_occupancy INTEGER NOT NULL,
            amenities TEXT
        )
    '''

CREATE_BOOKINGS_TABLE = '''
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

COUNT_ROOMS = 'SELECT COUNT(*) FROM rooms'

INSERT_ROOM = '''
            INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_BOOKING = '''
            INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
            VALUES (?, ?, ?, ?, ?)
        '''

SELECT_ROOM_PRICE = 'SELECT price_per_night FROM rooms WHERE room_id = ?'

DELETE_BOOKING = 'DELETE FROM bookings WHERE booking_id = ?'

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

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_connection():
    """Open a new connection to the hotel database."""
    return sqlite3.connect(CONFIG.db_path)


def create_tables(cursor):
    """Create the database schema if it does not already exist."""
    cursor.execute(CREATE_ROOMS_TABLE)
    cursor.execute(CREATE_BOOKINGS_TABLE)


def seed_data(cursor):
    """Insert initial data when the rooms table is empty."""
    cursor.execute(COUNT_ROOMS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM, SEED_ROOMS)
        cursor.executemany(INSERT_BOOKING, SEED_BOOKINGS)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    create_tables(cursor)
    seed_data(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------


def room_row_to_dict(row):
    """Convert a raw rooms table row into its JSON representation."""
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


def build_room_search_query(room_type, max_price, check_date):
    """Build the room search SQL from the supplied filters."""
    query = f"SELECT * FROM rooms WHERE room_type LIKE '%{room_type}%'"
    if max_price:
        query += f' AND price_per_night <= {max_price}'
    if check_date:
        query += f" AND room_id NOT IN (\n            SELECT room_id FROM bookings \n            WHERE '{check_date}' BETWEEN check_in_date AND check_out_date\n        )"
    return query


def calculate_total_price(price_per_night, check_in_date, check_out_date):
    """Calculate the total booking price from the nightly rate and dates."""
    nights = (
        datetime.strptime(check_out_date, CONFIG.date_format)
        - datetime.strptime(check_in_date, CONFIG.date_format)
    ).days
    return price_per_night * nights


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route('/rooms/search', method='GET')
def search_rooms():
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')
    conn = get_connection()
    cursor = conn.cursor()
    query = build_room_search_query(room_type, max_price, check_date)
    try:
        cursor.execute(query)
        rooms = [room_row_to_dict(row) for row in cursor.fetchall()]
        conn.close()
        response.content_type = 'application/json'
        return json.dumps({'rooms': rooms})
    except Exception as e:
        conn.close()
        response.status = HTTP_INTERNAL_ERROR
        return json.dumps({'error': str(e)})


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(SELECT_ROOM_PRICE, (data['room_id'],))
        price_per_night = cursor.fetchone()[0]
        total_price = calculate_total_price(
            price_per_night, data['check_in_date'], data['check_out_date']
        )
        cursor.execute(
            INSERT_BOOKING,
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
        conn.close()
        response.content_type = 'application/json'
        return json.dumps({'booking_id': booking_id, 'total_price': total_price})
    except Exception as e:
        response.status = HTTP_BAD_REQUEST
        return json.dumps({'error': str(e)})


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(DELETE_BOOKING, (booking_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            response.status = HTTP_NOT_FOUND
            return json.dumps({'error': ERROR_BOOKING_NOT_FOUND})
        return json.dumps({'status': 'success'})
    except Exception as e:
        response.status = HTTP_INTERNAL_ERROR
        return json.dumps({'error': str(e)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    init_db()
    run(app, host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug)


if __name__ == '__main__':
    main()
