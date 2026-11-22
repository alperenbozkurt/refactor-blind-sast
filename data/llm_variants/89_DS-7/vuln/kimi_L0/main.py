import json
import sqlite3
from datetime import datetime

from bottle import Bottle, request, response, run

DATABASE = 'hotel.db'
DATE_FORMAT = '%Y-%m-%d'

app = Bottle()

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

SELECT_ROOM_PRICE = 'SELECT price_per_night FROM rooms WHERE room_id = ?'
DELETE_BOOKING = 'DELETE FROM bookings WHERE booking_id = ?'

SAMPLE_ROOMS = [
    ('101', 'Standard', 99.99, 2, 'TV,WiFi'),
    ('201', 'Deluxe', 149.99, 3, 'TV,WiFi,Minibar'),
    ('301', 'Suite', 249.99, 4, 'TV,WiFi,Minibar,Jacuzzi'),
]

SAMPLE_BOOKINGS = [
    (1, 'John Smith', '2023-06-01', '2023-06-05', 399.96),
    (2, 'Alice Johnson', '2023-06-10', '2023-06-15', 749.95),
]


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_ROOMS_TABLE)
    cursor.execute(CREATE_BOOKINGS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM rooms')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_ROOM, SAMPLE_ROOMS)
        cursor.executemany(INSERT_BOOKING, SAMPLE_BOOKINGS)
    conn.commit()
    conn.close()


def room_row_to_dict(row):
    return {
        'room_id': row[0],
        'room_number': row[1],
        'room_type': row[2],
        'price_per_night': row[3],
        'max_occupancy': row[4],
        'amenities': row[5].split(',') if row[5] else [],
    }


def build_room_search_query(room_type, max_price, check_date):
    query = f"SELECT * FROM rooms WHERE room_type LIKE '%{room_type}%'"
    if max_price:
        query += f' AND price_per_night <= {max_price}'
    if check_date:
        query += (
            ' AND room_id NOT IN ('
            'SELECT room_id FROM bookings '
            f"WHERE '{check_date}' BETWEEN check_in_date AND check_out_date"
            ')'
        )
    return query


def json_error(message, status):
    response.status = status
    return json.dumps({'error': message})


@app.route('/rooms/search', method='GET')
def search_rooms():
    query = build_room_search_query(
        request.query.get('room_type', ''),
        request.query.get('max_price', ''),
        request.query.get('check_date', ''),
    )
    conn = sqlite3.connect(DATABASE)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rooms = [room_row_to_dict(row) for row in cursor.fetchall()]
    except Exception as e:
        return json_error(str(e), 500)
    finally:
        conn.close()
    response.content_type = 'application/json'
    return json.dumps({'rooms': rooms})


@app.route('/bookings/create', method='POST')
def create_booking():
    try:
        data = request.json
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(SELECT_ROOM_PRICE, (data['room_id'],))
        price_per_night = cursor.fetchone()[0]
        check_in = datetime.strptime(data['check_in_date'], DATE_FORMAT)
        check_out = datetime.strptime(data['check_out_date'], DATE_FORMAT)
        total_price = price_per_night * (check_out - check_in).days
        cursor.execute(INSERT_BOOKING, (
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
    except Exception as e:
        return json_error(str(e), 400)


@app.route('/bookings/cancel', method='DELETE')
def cancel_booking():
    try:
        booking_id = request.query.get('booking_id')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(DELETE_BOOKING, (booking_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            return json_error('Booking not found', 404)
        return json.dumps({'status': 'success'})
    except Exception as e:
        return json_error(str(e), 500)


if __name__ == '__main__':
    init_db()
    run(app, host='localhost', port=8080, debug=True)
