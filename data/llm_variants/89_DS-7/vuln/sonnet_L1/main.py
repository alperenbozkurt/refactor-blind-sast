from contextlib import closing
from datetime import datetime
import json
import sqlite3

from bottle import Bottle, request, response, run

app = Bottle()

DB_PATH = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'
JSON_CONTENT_TYPE = 'application/json'

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

INSERT_ROOM = '''
            INSERT INTO rooms (room_number, room_type, price_per_night, max_occupancy, amenities)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_BOOKING = '''
            INSERT INTO bookings (room_id, guest_name, check_in_date, check_out_date, total_price)
            VALUES (?, ?, ?, ?, ?)
        '''

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
    return sqlite3.connect(DB_PATH)


def _error_response(status, error):
    response.status = status
    return json.dumps({'error': str(error)})


def _room_to_dict(row):
    amenities = row[5]
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': amenities.split(',') if amenities else [],
    }


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


def _build_search_query(room_type, max_price, check_date):
    # NOTE: the query is intentionally built by string interpolation to keep
    # the existing behaviour of this endpoint unchanged.
    query = f"SELECT * FROM rooms WHERE room_type LIKE '%{room_type}%'"
    if max_price:
        query += f' AND price_per_night <= {max_price}'
    if check_date:
        query += (
            f" AND room_id NOT IN (\n"
            f"            SELECT room_id FROM bookings \n"
            f"            WHERE '{check_date}' BETWEEN check_in_date AND check_out_date\n"
            f"        )"
        )
    return query


@app.route('/rooms/search', method='GET')
def search_rooms():
    room_type = request.query.get('room_type', '')
    max_price = request.query.get('max_price', '')
    check_date = request.query.get('check_date', '')

    with closing(_connect()) as conn:
        cursor = conn.cursor()
        query = _build_search_query(room_type, max_price, check_date)
        try:
            cursor.execute(query)
            rooms = [_room_to_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            return _error_response(500, e)

    response.content_type = JSON_CONTENT_TYPE
    return json.dumps({'rooms': rooms})


def _count_nights(check_in_date, check_out_date):
    check_in = datetime.strptime(check_in_date, DATE_FORMAT)
    check_out = datetime.strptime(check_out_date, DATE_FORMAT)
    return (check_out - check_in).days


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT price_per_night FROM rooms WHERE room_id = ?',
                (data['room_id'],),
            )
            price_per_night = cursor.fetchone()[0]
            nights = _count_nights(data['check_in_date'], data['check_out_date'])
            total_price = price_per_night * nights
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
        response.content_type = JSON_CONTENT_TYPE
        return json.dumps({'booking_id': booking_id, 'total_price': total_price})
    except Exception as e:
        return _error_response(400, e)


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bookings WHERE booking_id = ?', (booking_id,))
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return _error_response(404, 'Booking not found')
        return json.dumps({'status': 'success'})
    except Exception as e:
        return _error_response(500, e)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
