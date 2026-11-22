"""Hotel room booking web service built with Bottle and SQLite."""

from bottle import Bottle, request, response, run
import sqlite3
import json
from datetime import datetime
import re

app = Bottle()

DB_PATH = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'
GUEST_NAME_PATTERN = re.compile(r'^[a-zA-Z\s\-]{2,100}$')

REQUIRED_BOOKING_FIELDS = ['room_id', 'guest_name', 'check_in_date', 'check_out_date']

CREATE_ROOMS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY,
        room_number TEXT UNIQUE NOT NULL,
        room_type TEXT NOT NULL,
        price_per_night REAL NOT NULL,
        max_occupancy INTEGER NOT NULL,
        amenities TEXT
    )
"""

CREATE_BOOKINGS_TABLE_SQL = """
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

INSERT_ROOM_SQL = """
    INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
    VALUES (?, ?, ?, ?, ?)
"""

INSERT_BOOKING_SQL = """
    INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
    VALUES (?, ?, ?, ?, ?)
"""

OVERLAPPING_BOOKINGS_SQL = """
    SELECT 1 FROM bookings
    WHERE room_id = ? AND (
        (? BETWEEN check_in_date AND check_out_date) OR
        (? BETWEEN check_in_date AND check_out_date) OR
        (check_in_date BETWEEN ? AND ?) OR
        (check_out_date BETWEEN ? AND ?)
    )
"""

SEED_ROOMS = [
    ('101', 'Standard', 99.99, 2, 'TV,WiFi'),
    ('201', 'Deluxe', 149.99, 3, 'TV,WiFi,Minibar'),
    ('301', 'Suite', 249.99, 4, 'TV,WiFi,Minibar,Jacuzzi'),
]

SEED_BOOKINGS = [
    (1, 'John Smith', '2023-06-01', '2023-06-05', 399.96),
    (2, 'Alice Johnson', '2023-06-10', '2023-06-15', 749.95),
]


def _connect():
    """Open a new connection to the hotel database."""
    return sqlite3.connect(DB_PATH)


def _room_row_to_dict(row):
    """Convert a row from the rooms table into a JSON-serializable dict."""
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


def init_db():
    """Create the database tables and seed them with sample data if empty."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_ROOMS_TABLE_SQL)
    cursor.execute(CREATE_BOOKINGS_TABLE_SQL)
    cursor.execute('SELECT COUNT(*) FROM rooms')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM_SQL, SEED_ROOMS)
        cursor.executemany(INSERT_BOOKING_SQL, SEED_BOOKINGS)
    conn.commit()
    conn.close()


def validate_booking_data(data):
    """Validate booking payload fields, dates and guest name."""
    if not all(field in data for field in REQUIRED_BOOKING_FIELDS):
        raise ValueError('Missing required fields')
    try:
        check_in = datetime.strptime(data['check_in_date'], DATE_FORMAT)
        check_out = datetime.strptime(data['check_out_date'], DATE_FORMAT)
        if check_in >= check_out:
            raise ValueError('Check-out date must be after check-in date')
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD')
    if not GUEST_NAME_PATTERN.match(data['guest_name']):
        raise ValueError('Invalid guest name')
    return True


@app.route('/rooms/search', method='GET')
def search_rooms():
    """Search rooms by type, maximum price and availability on a given date."""
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')

    conn = _connect()
    cursor = conn.cursor()

    query = 'SELECT * FROM rooms WHERE 1=1'
    params = []

    if room_type:
        query += ' AND room_type LIKE ?'
        params.append(f'%{room_type}%')

    if max_price:
        try:
            max_price_float = float(max_price)
            query += ' AND price_per_night <= ?'
            params.append(max_price_float)
        except ValueError:
            conn.close()
            response.status = 400
            return json.dumps({'error': 'Invalid max_price value'})

    if check_date:
        try:
            datetime.strptime(check_date, DATE_FORMAT)
            query += (
                ' AND room_id NOT IN ('
                'SELECT room_id FROM bookings '
                'WHERE ? BETWEEN check_in_date AND check_out_date)'
            )
            params.append(check_date)
        except ValueError:
            conn.close()
            response.status = 400
            return json.dumps({'error': 'Invalid date format. Use YYYY-MM-DD'})

    try:
        cursor.execute(query, params)
        rooms = [_room_row_to_dict(row) for row in cursor.fetchall()]
        conn.close()
        response.content_type = 'application/json'
        return json.dumps({'rooms': rooms})
    except Exception:
        conn.close()
        response.status = 500
        return json.dumps({'error': 'Internal server error'})


@app.route('/bookings/create', method='POST')
def create_booking():
    """Create a booking for an available room and return its id and price."""
    try:
        data = request.json
        validate_booking_data(data)

        conn = _connect()
        cursor = conn.cursor()

        cursor.execute('SELECT 1 FROM rooms WHERE room_id = ?', (data['room_id'],))
        if not cursor.fetchone():
            response.status = 404
            return json.dumps({'error': 'Room not found'})

        cursor.execute(OVERLAPPING_BOOKINGS_SQL, (
            data['room_id'],
            data['check_in_date'],
            data['check_out_date'],
            data['check_in_date'],
            data['check_out_date'],
            data['check_in_date'],
            data['check_out_date'],
        ))
        if cursor.fetchone():
            response.status = 400
            return json.dumps({'error': 'Room not available for selected dates'})

        cursor.execute('SELECT price_per_night FROM rooms WHERE room_id = ?', (data['room_id'],))
        price_per_night = cursor.fetchone()[0]
        nights = (
            datetime.strptime(data['check_out_date'], DATE_FORMAT)
            - datetime.strptime(data['check_in_date'], DATE_FORMAT)
        ).days
        total_price = price_per_night * nights

        cursor.execute(INSERT_BOOKING_SQL, (
            data['room_id'],
            data['guest_name'],
            data['check_in_date'],
            data['check_out_date'],
            total_price,
        ))
        conn.commit()
        booking_id = cursor.lastrowid
        conn.close()

        response.content_type = 'application/json'
        return json.dumps({'booking_id': booking_id, 'total_price': total_price})
    except ValueError as e:
        response.status = 400
        return json.dumps({'error': str(e)})
    except Exception:
        if 'conn' in locals():
            conn.close()
        response.status = 500
        return json.dumps({'error': 'Booking creation failed'})


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    """Cancel an existing booking identified by the booking_id query parameter."""
    try:
        booking_id = request.query.get('booking_id')
        if not booking_id or not booking_id.isdigit():
            response.status = 400
            return json.dumps({'error': 'Invalid booking ID'})

        conn = _connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bookings WHERE booking_id = ?', (booking_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            response.status = 404
            return json.dumps({'error': 'Booking not found'})
        return json.dumps({'status': 'success'})
    except Exception:
        if 'conn' in locals():
            conn.close()
        response.status = 500
        return json.dumps({'error': 'Failed to cancel booking'})


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=False)
