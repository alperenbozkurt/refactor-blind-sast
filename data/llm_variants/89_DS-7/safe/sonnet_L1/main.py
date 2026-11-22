from bottle import Bottle, request, response, run
import sqlite3
import json
from datetime import datetime
import re

app = Bottle()

DB_PATH = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'
GUEST_NAME_PATTERN = '^[a-zA-Z\\s\\-]{2,100}$'
REQUIRED_BOOKING_FIELDS = ['room_id', 'guest_name', 'check_in_date', 'check_out_date']

CREATE_ROOMS_TABLE = """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            price_per_night REAL NOT NULL,
            max_occupancy INTEGER NOT NULL,
            amenities TEXT
        )
    """

CREATE_BOOKINGS_TABLE = """
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

INSERT_ROOM = """
            INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
            VALUES (?, ?, ?, ?, ?)
        """

INSERT_BOOKING = """
            INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
            VALUES (?, ?, ?, ?, ?)
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

AVAILABILITY_FILTER = """ AND room_id NOT IN (
                SELECT room_id FROM bookings 
                WHERE ? BETWEEN check_in_date AND check_out_date
            )"""

OVERLAP_QUERY = """
            SELECT 1 FROM bookings 
            WHERE room_id = ? AND (
                (? BETWEEN check_in_date AND check_out_date) OR
                (? BETWEEN check_in_date AND check_out_date) OR
                (check_in_date BETWEEN ? AND ?) OR
                (check_out_date BETWEEN ? AND ?)
            )
        """


def _connect():
    return sqlite3.connect(DB_PATH)


def _error_response(status, message):
    response.status = status
    return json.dumps({'error': message})


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_ROOMS_TABLE)
    cursor.execute(CREATE_BOOKINGS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM rooms')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM, SEED_ROOMS)
        cursor.executemany(INSERT_BOOKING, SEED_BOOKINGS)
    conn.commit()
    conn.close()


def validate_booking_data(data):
    if not all((field in data for field in REQUIRED_BOOKING_FIELDS)):
        raise ValueError('Missing required fields')
    try:
        check_in = datetime.strptime(data['check_in_date'], DATE_FORMAT)
        check_out = datetime.strptime(data['check_out_date'], DATE_FORMAT)
        if check_in >= check_out:
            raise ValueError('Check-out date must be after check-in date')
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD')
    if not re.match(GUEST_NAME_PATTERN, data['guest_name']):
        raise ValueError('Invalid guest name')
    return True


def _room_row_to_dict(row):
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


@app.route('/rooms/search', method='GET')
def search_rooms():
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')

    conn = _connect()
    try:
        cursor = conn.cursor()
        query = 'SELECT * FROM rooms WHERE 1=1'
        params = []

        if room_type:
            query += ' AND room_type LIKE ?'
            params.append(f'%{room_type}%')

        if max_price:
            try:
                max_price_float = float(max_price)
            except ValueError:
                return _error_response(400, 'Invalid max_price value')
            query += ' AND price_per_night <= ?'
            params.append(max_price_float)

        if check_date:
            try:
                datetime.strptime(check_date, DATE_FORMAT)
            except ValueError:
                return _error_response(400, 'Invalid date format. Use YYYY-MM-DD')
            query += AVAILABILITY_FILTER
            params.append(check_date)

        try:
            cursor.execute(query, params)
            rooms = [_room_row_to_dict(row) for row in cursor.fetchall()]
            response.content_type = 'application/json'
            return json.dumps({'rooms': rooms})
        except Exception:
            return _error_response(500, 'Internal server error')
    finally:
        conn.close()


def _insert_booking(conn, data):
    """Create a booking using an open connection and return the JSON body."""
    cursor = conn.cursor()
    room_id = data['room_id']
    check_in = data['check_in_date']
    check_out = data['check_out_date']

    cursor.execute('SELECT 1 FROM rooms WHERE room_id = ?', (room_id,))
    if not cursor.fetchone():
        return _error_response(404, 'Room not found')

    cursor.execute(
        OVERLAP_QUERY,
        (room_id, check_in, check_out, check_in, check_out, check_in, check_out),
    )
    if cursor.fetchone():
        return _error_response(400, 'Room not available for selected dates')

    cursor.execute('SELECT price_per_night FROM rooms WHERE room_id = ?', (room_id,))
    price_per_night = cursor.fetchone()[0]
    nights = (
        datetime.strptime(check_out, DATE_FORMAT)
        - datetime.strptime(check_in, DATE_FORMAT)
    ).days
    total_price = price_per_night * nights

    cursor.execute(
        INSERT_BOOKING,
        (room_id, data['guest_name'], check_in, check_out, total_price),
    )
    conn.commit()
    booking_id = cursor.lastrowid

    response.content_type = 'application/json'
    return json.dumps({'booking_id': booking_id, 'total_price': total_price})


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        validate_booking_data(data)
        conn = _connect()
        try:
            return _insert_booking(conn, data)
        finally:
            conn.close()
    except ValueError as e:
        return _error_response(400, str(e))
    except Exception:
        return _error_response(500, 'Booking creation failed')


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        if not booking_id or not booking_id.isdigit():
            return _error_response(400, 'Invalid booking ID')

        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bookings WHERE booking_id = ?', (booking_id,))
            conn.commit()
            affected = cursor.rowcount
        finally:
            conn.close()

        if affected == 0:
            return _error_response(404, 'Booking not found')
        return json.dumps({'status': 'success'})
    except Exception:
        return _error_response(500, 'Failed to cancel booking')


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=False)
