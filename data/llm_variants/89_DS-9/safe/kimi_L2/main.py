"""Medical records HTTP API (Sanic + SQLite).

Refactored into a modular design: a frozen configuration object, named
SQL/regex/message constants, small database and validation helpers, and
slim route handlers. Behaviour, public names, signatures, routes and the
CLI are unchanged from the original module.
"""

import re
import sqlite3
import datetime
from contextlib import closing
from dataclasses import dataclass

from dateutil.parser import parse
from sanic import Sanic, response
from sanic.response import json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_NAME = 'MedicalRecordsSystem'
DATABASE_PATH = 'medical.db'
DATE_FORMAT = '%Y-%m-%d'

NAME_PATTERN = re.compile(r"^[a-zA-Z\-\'\s]{1,50}$")
SSN_PATTERN = re.compile(r'^\d{3}-\d{2}-\d{4}$')
SANITIZE_PATTERN = re.compile(r'[;\'"\\]')

REQUIRED_RECORD_FIELDS = ('patient_id', 'visit_date', 'diagnosis', 'physician')
REQUIRED_PATIENT_FIELDS = ('first_name', 'last_name', 'dob', 'ssn')

ERR_MISSING_FIELDS = 'Missing required fields'
ERR_PATIENT_NOT_FOUND = 'Patient not found'
ERR_SSN_REGISTERED = 'SSN already registered'
ERR_INTERNAL = 'Internal server error'
ERR_ADD_RECORD = 'Failed to add record'
ERR_REGISTER_PATIENT = 'Failed to register patient'


@dataclass(frozen=True)
class ServerConfig:
    """Runtime settings for the HTTP server and its database."""

    database_path: str = DATABASE_PATH
    host: str = '0.0.0.0'
    port: int = 8000
    access_log: bool = False


CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# SQL statements and seed data
# ---------------------------------------------------------------------------

CREATE_PATIENTS_TABLE = '''
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        dob TEXT NOT NULL,
        ssn TEXT UNIQUE NOT NULL,
        insurance_id TEXT
    )
'''

CREATE_RECORDS_TABLE = '''
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

INSERT_PATIENT = '''
    INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)
    VALUES (?, ?, ?, ?, ?)
'''

INSERT_RECORD = '''
    INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)
    VALUES (?, ?, ?, ?, ?)
'''

SEARCH_QUERY_BASE = '''
    SELECT p.patient_id, p.first_name, p.last_name, p.dob,
           r.visit_date, r.diagnosis, r.treatment, r.physician
    FROM patients p
    JOIN records r ON p.patient_id = r.patient_id
    WHERE p.first_name LIKE ?
    AND p.last_name LIKE ?
'''

DIAGNOSIS_CLAUSE = ' AND r.diagnosis LIKE ?'
START_DATE_CLAUSE = ' AND r.visit_date >= ?'
END_DATE_CLAUSE = ' AND r.visit_date <= ?'

PATIENT_COUNT_QUERY = 'SELECT COUNT(*) FROM patients'
PATIENT_EXISTS_QUERY = 'SELECT 1 FROM patients WHERE patient_id = ?'
SSN_EXISTS_QUERY = 'SELECT 1 FROM patients WHERE ssn = ?'

SEED_PATIENTS = (
    ('John', 'Smith', '1980-05-15', '123-45-6789', 'INS123456'),
    ('Sarah', 'Johnson', '1975-11-22', '987-65-4321', 'INS789012'),
    ('Michael', 'Williams', '1990-02-10', '456-78-9012', 'INS345678'),
)

SEED_RECORDS = (
    (1, '2023-01-10', 'Hypertension', 'Prescribed medication', 'Dr. Anderson'),
    (1, '2023-03-15', 'Annual checkup', 'Routine tests', 'Dr. Brown'),
    (2, '2023-02-20', 'Diabetes', 'Insulin therapy', 'Dr. Carter'),
)

app = Sanic(APP_NAME)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Open a new connection to the application database."""
    return sqlite3.connect(CONFIG.database_path)


def database_is_empty(cursor):
    cursor.execute(PATIENT_COUNT_QUERY)
    return cursor.fetchone()[0] == 0


def seed_database(cursor):
    cursor.executemany(INSERT_PATIENT, SEED_PATIENTS)
    cursor.executemany(INSERT_RECORD, SEED_RECORDS)


def init_db():
    """Create the schema and seed sample data when the database is empty."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PATIENTS_TABLE)
        cursor.execute(CREATE_RECORDS_TABLE)
        if database_is_empty(cursor):
            seed_database(cursor)
        conn.commit()


def patient_exists(cursor, patient_id):
    cursor.execute(PATIENT_EXISTS_QUERY, (patient_id,))
    return cursor.fetchone() is not None


def ssn_exists(cursor, ssn):
    cursor.execute(SSN_EXISTS_QUERY, (ssn,))
    return cursor.fetchone() is not None

# ---------------------------------------------------------------------------
# Validation and sanitisation
# ---------------------------------------------------------------------------

def validate_name(name):
    if not NAME_PATTERN.match(name):
        raise ValueError('Invalid name format')
    return name


def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, DATE_FORMAT)
        return date_str
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD')


def validate_ssn(ssn):
    if not SSN_PATTERN.match(ssn):
        raise ValueError('Invalid SSN format. Use XXX-XX-XXXX')
    return ssn


def sanitize_input(input_str):
    if not input_str:
        return ''
    return SANITIZE_PATTERN.sub('', input_str)


def validate_record_payload(data):
    validate_date(data['visit_date'])
    if not str(data['patient_id']).isdigit():
        raise ValueError('Invalid patient ID')


def validate_patient_payload(data):
    validate_name(data['first_name'])
    validate_name(data['last_name'])
    validate_date(data['dob'])
    validate_ssn(data['ssn'])

# ---------------------------------------------------------------------------
# Query building and result mapping
# ---------------------------------------------------------------------------

def build_search_query(first_name, last_name, diagnosis, start_date, end_date):
    """Assemble the search SQL and parameters, validating any dates given."""
    query = SEARCH_QUERY_BASE
    params = [f'%{first_name}%', f'%{last_name}%']
    if diagnosis:
        query += DIAGNOSIS_CLAUSE
        params.append(f'%{diagnosis}%')
    if start_date:
        validate_date(start_date)
        query += START_DATE_CLAUSE
        params.append(start_date)
    if end_date:
        validate_date(end_date)
        query += END_DATE_CLAUSE
        params.append(end_date)
    return query, params


def row_to_record(row):
    return {
        'patient_id': row[0],
        'patient_name': f'{row[1]} {row[2]}',
        'dob': row[3],
        'visit_date': row[4],
        'diagnosis': row[5],
        'treatment': row[6],
        'physician': row[7],
    }


def error_response(message, status):
    return json({'error': message}, status=status)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    try:
        first_name = sanitize_input(request.args.get('first_name', ''))
        last_name = sanitize_input(request.args.get('last_name', ''))
        diagnosis = sanitize_input(request.args.get('diagnosis', ''))
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            try:
                query, params = build_search_query(
                    first_name, last_name, diagnosis, start_date, end_date
                )
            except ValueError as e:
                return error_response(str(e), 400)
            cursor.execute(query, params)
            records = [row_to_record(row) for row in cursor.fetchall()]
        return json({'records': records})
    except Exception:
        return error_response(ERR_INTERNAL, 500)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        if not all(key in data for key in REQUIRED_RECORD_FIELDS):
            return error_response(ERR_MISSING_FIELDS, 400)
        try:
            validate_record_payload(data)
        except ValueError as e:
            return error_response(str(e), 400)

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            if not patient_exists(cursor, data['patient_id']):
                return error_response(ERR_PATIENT_NOT_FOUND, 404)
            cursor.execute(INSERT_RECORD, (
                data['patient_id'],
                data['visit_date'],
                data['diagnosis'],
                data.get('treatment', ''),
                data['physician'],
            ))
            conn.commit()
            record_id = cursor.lastrowid
        return json({'record_id': record_id})
    except Exception:
        return error_response(ERR_ADD_RECORD, 500)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        if not all(key in data for key in REQUIRED_PATIENT_FIELDS):
            return error_response(ERR_MISSING_FIELDS, 400)
        try:
            validate_patient_payload(data)
        except ValueError as e:
            return error_response(str(e), 400)

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            if ssn_exists(cursor, data['ssn']):
                return error_response(ERR_SSN_REGISTERED, 400)
            cursor.execute(INSERT_PATIENT, (
                data['first_name'],
                data['last_name'],
                data['dob'],
                data['ssn'],
                data.get('insurance_id', ''),
            ))
            conn.commit()
            patient_id = cursor.lastrowid
        return json({'patient_id': patient_id})
    except Exception:
        return error_response(ERR_REGISTER_PATIENT, 500)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    init_db()
    app.run(host=CONFIG.host, port=CONFIG.port, access_log=CONFIG.access_log)


if __name__ == '__main__':
    main()
