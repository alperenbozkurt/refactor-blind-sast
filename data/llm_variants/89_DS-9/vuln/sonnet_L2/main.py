from contextlib import closing

from sanic import Sanic, response
from sanic.response import json
import sqlite3
import datetime
from dateutil.parser import parse

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
APP_NAME = 'MedicalRecordsSystem'
DB_PATH = 'medical.db'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

HTTP_BAD_REQUEST = 400
HTTP_SERVER_ERROR = 500

CREATE_PATIENTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            ssn TEXT UNIQUE NOT NULL,
            insurance_id TEXT
        )
    '''

CREATE_RECORDS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS records (
            record_id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            visit_date TEXT NOT NULL,
            diagnosis TEXT,
            treatment TEXT,
            physician TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
        )
    '''

COUNT_PATIENTS_SQL = 'SELECT COUNT(*) FROM patients'

INSERT_PATIENT_SQL = '''
            INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_RECORD_SQL = '''
            INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)
            VALUES (?, ?, ?, ?, ?)
        '''

SEARCH_BASE_SQL = '''
        SELECT p.patient_id, p.first_name, p.last_name, p.dob,
               r.visit_date, r.diagnosis, r.treatment, r.physician
        FROM patients p
        JOIN records r ON p.patient_id = r.patient_id
        WHERE p.first_name LIKE ?
        AND p.last_name LIKE ?
    '''

SEED_PATIENTS = [
    ('John', 'Smith', '1980-05-15', '123-45-6789', 'INS123456'),
    ('Sarah', 'Johnson', '1975-11-22', '987-65-4321', 'INS789012'),
    ('Michael', 'Williams', '1990-02-10', '456-78-9012', 'INS345678'),
]

SEED_RECORDS = [
    (1, '2023-01-10', 'Hypertension', 'Prescribed medication', 'Dr. Anderson'),
    (1, '2023-03-15', 'Annual checkup', 'Routine tests', 'Dr. Brown'),
    (2, '2023-02-20', 'Diabetes', 'Insulin therapy', 'Dr. Carter'),
]

app = Sanic(APP_NAME)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def _connect():
    """Open a new connection to the medical database."""
    return sqlite3.connect(DB_PATH)


def _seed_if_empty(cursor):
    """Populate the database with sample data when no patients exist."""
    cursor.execute(COUNT_PATIENTS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_PATIENT_SQL, SEED_PATIENTS)
        cursor.executemany(INSERT_RECORD_SQL, SEED_RECORDS)


def init_db():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PATIENTS_TABLE_SQL)
        cursor.execute(CREATE_RECORDS_TABLE_SQL)
        _seed_if_empty(cursor)
        conn.commit()


def _like(value):
    """Wrap a value for a substring LIKE match."""
    return f'%{value}%'


def _build_search_query(first_name, last_name, diagnosis, start_date, end_date):
    """Build the (parameterized) search SQL and its parameters."""
    query = SEARCH_BASE_SQL
    params = [_like(first_name), _like(last_name)]
    if diagnosis:
        query += ' AND r.diagnosis LIKE ?'
        params.append(_like(diagnosis))
    if start_date:
        query += ' AND r.visit_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND r.visit_date <= ?'
        params.append(end_date)
    return query, params


def _row_to_record(row):
    return {
        'patient_id': row[0],
        'patient_name': f'{row[1]} {row[2]}',
        'dob': row[3],
        'visit_date': row[4],
        'diagnosis': row[5],
        'treatment': row[6],
        'physician': row[7],
    }


def _insert_and_get_id(sql, params):
    """Execute an INSERT, commit, and return the new row id."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def _error_response(exc, status):
    return json({'error': str(exc)}, status=status)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    first_name = request.args.get('first_name', '')
    last_name = request.args.get('last_name', '')
    diagnosis = request.args.get('diagnosis', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query, params = _build_search_query(
        first_name, last_name, diagnosis, start_date, end_date
    )

    with closing(_connect()) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            records = [_row_to_record(row) for row in cursor.fetchall()]
            return json({'records': records})
        except Exception as e:
            return _error_response(e, HTTP_SERVER_ERROR)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        record_id = _insert_and_get_id(
            INSERT_RECORD_SQL,
            (
                data['patient_id'],
                data['visit_date'],
                data['diagnosis'],
                data['treatment'],
                data['physician'],
            ),
        )
        return json({'record_id': record_id})
    except Exception as e:
        return _error_response(e, HTTP_BAD_REQUEST)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        patient_id = _insert_and_get_id(
            INSERT_PATIENT_SQL,
            (
                data['first_name'],
                data['last_name'],
                data['dob'],
                data['ssn'],
                data.get('insurance_id', ''),
            ),
        )
        return json({'patient_id': patient_id})
    except Exception as e:
        return _error_response(e, HTTP_BAD_REQUEST)


if __name__ == '__main__':
    init_db()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
