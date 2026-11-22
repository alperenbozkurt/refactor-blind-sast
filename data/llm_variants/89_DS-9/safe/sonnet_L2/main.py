from sanic import Sanic, response
from sanic.response import json
import sqlite3
import datetime
from dateutil.parser import parse
import re
from contextlib import contextmanager

app = Sanic('MedicalRecordsSystem')

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------
DB_PATH = 'medical.db'
DATE_FORMAT = '%Y-%m-%d'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

NAME_PATTERN = "^[a-zA-Z\\-\\'\\s]{1,50}$"
SSN_PATTERN = '^\\d{3}-\\d{2}-\\d{4}$'
SANITIZE_PATTERN = '[;\\\'"\\\\]'

REQUIRED_RECORD_FIELDS = ['patient_id', 'visit_date', 'diagnosis', 'physician']
REQUIRED_PATIENT_FIELDS = ['first_name', 'last_name', 'dob', 'ssn']

# --------------------------------------------------------------------------
# SQL statements
# --------------------------------------------------------------------------
CREATE_PATIENTS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS patients (\n            patient_id INTEGER PRIMARY KEY,\n            first_name TEXT NOT NULL,\n            last_name TEXT NOT NULL,\n            dob TEXT NOT NULL,\n            ssn TEXT UNIQUE NOT NULL,\n            insurance_id TEXT\n        )\n    '
CREATE_RECORDS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS records (\n            record_id INTEGER PRIMARY KEY,\n            patient_id INTEGER NOT NULL,\n            visit_date TEXT NOT NULL,\n            diagnosis TEXT,\n            treatment TEXT,\n            physician TEXT,\n            FOREIGN KEY(patient_id) REFERENCES patients(patient_id)\n        )\n    '
COUNT_PATIENTS_SQL = 'SELECT COUNT(*) FROM patients'
INSERT_PATIENT_SQL = '\n            INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)\n            VALUES (?, ?, ?, ?, ?)\n        '
INSERT_RECORD_SQL = '\n            INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)\n            VALUES (?, ?, ?, ?, ?)\n        '
SELECT_PATIENT_EXISTS_SQL = 'SELECT 1 FROM patients WHERE patient_id = ?'
SELECT_SSN_EXISTS_SQL = 'SELECT 1 FROM patients WHERE ssn = ?'
SEARCH_BASE_SQL = '\n            SELECT p.patient_id, p.first_name, p.last_name, p.dob, \n                   r.visit_date, r.diagnosis, r.treatment, r.physician\n            FROM patients p\n            JOIN records r ON p.patient_id = r.patient_id\n            WHERE p.first_name LIKE ?\n            AND p.last_name LIKE ?\n        '
SEARCH_DIAGNOSIS_CLAUSE = ' AND r.diagnosis LIKE ?'
SEARCH_START_DATE_CLAUSE = ' AND r.visit_date >= ?'
SEARCH_END_DATE_CLAUSE = ' AND r.visit_date <= ?'

# --------------------------------------------------------------------------
# Seed data
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
@contextmanager
def _db_connection():
    """Open a connection to the database and always close it on exit."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _seed_database(cursor):
    cursor.executemany(INSERT_PATIENT_SQL, SEED_PATIENTS)
    cursor.executemany(INSERT_RECORD_SQL, SEED_RECORDS)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_PATIENTS_TABLE_SQL)
    cursor.execute(CREATE_RECORDS_TABLE_SQL)
    cursor.execute(COUNT_PATIENTS_SQL)
    if cursor.fetchone()[0] == 0:
        _seed_database(cursor)
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Validation / sanitization
# --------------------------------------------------------------------------
def validate_name(name):
    if not re.match(NAME_PATTERN, name):
        raise ValueError('Invalid name format')
    return name


def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, DATE_FORMAT)
        return date_str
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD')


def validate_ssn(ssn):
    if not re.match(SSN_PATTERN, ssn):
        raise ValueError('Invalid SSN format. Use XXX-XX-XXXX')
    return ssn


def sanitize_input(input_str):
    if not input_str:
        return ''
    return re.sub(SANITIZE_PATTERN, '', input_str)


def _has_all_fields(data, fields):
    return all((key in data for key in fields))


# --------------------------------------------------------------------------
# Response helpers
# --------------------------------------------------------------------------
def _error(message, status):
    return json({'error': message}, status=status)


# --------------------------------------------------------------------------
# Search helpers
# --------------------------------------------------------------------------
def _build_search_query(first_name, last_name, diagnosis, start_date, end_date):
    """Build the search SQL and parameters; raises ValueError on bad dates."""
    query = SEARCH_BASE_SQL
    params = [f'%{first_name}%', f'%{last_name}%']
    if diagnosis:
        query += SEARCH_DIAGNOSIS_CLAUSE
        params.append(f'%{diagnosis}%')
    if start_date:
        validate_date(start_date)
        query += SEARCH_START_DATE_CLAUSE
        params.append(start_date)
    if end_date:
        validate_date(end_date)
        query += SEARCH_END_DATE_CLAUSE
        params.append(end_date)
    return query, params


def _search_row_to_record(row):
    return {
        'patient_id': row[0],
        'patient_name': f'{row[1]} {row[2]}',
        'dob': row[3],
        'visit_date': row[4],
        'diagnosis': row[5],
        'treatment': row[6],
        'physician': row[7],
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    try:
        first_name = sanitize_input(request.args.get('first_name', ''))
        last_name = sanitize_input(request.args.get('last_name', ''))
        diagnosis = sanitize_input(request.args.get('diagnosis', ''))
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        with _db_connection() as conn:
            cursor = conn.cursor()
            try:
                query, params = _build_search_query(
                    first_name, last_name, diagnosis, start_date, end_date
                )
            except ValueError as e:
                return _error(str(e), 400)
            cursor.execute(query, params)
            records = [_search_row_to_record(row) for row in cursor.fetchall()]
        return json({'records': records})
    except Exception as e:
        return _error('Internal server error', 500)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        if not _has_all_fields(data, REQUIRED_RECORD_FIELDS):
            return _error('Missing required fields', 400)
        try:
            validate_date(data['visit_date'])
            if not str(data['patient_id']).isdigit():
                raise ValueError('Invalid patient ID')
        except ValueError as e:
            return _error(str(e), 400)
        with _db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_PATIENT_EXISTS_SQL, (data['patient_id'],))
            if not cursor.fetchone():
                return _error('Patient not found', 404)
            cursor.execute(
                INSERT_RECORD_SQL,
                (
                    data['patient_id'],
                    data['visit_date'],
                    data['diagnosis'],
                    data.get('treatment', ''),
                    data['physician'],
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
        return json({'record_id': record_id})
    except Exception as e:
        return _error('Failed to add record', 500)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        if not _has_all_fields(data, REQUIRED_PATIENT_FIELDS):
            return _error('Missing required fields', 400)
        try:
            validate_name(data['first_name'])
            validate_name(data['last_name'])
            validate_date(data['dob'])
            validate_ssn(data['ssn'])
        except ValueError as e:
            return _error(str(e), 400)
        with _db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_SSN_EXISTS_SQL, (data['ssn'],))
            if cursor.fetchone():
                return _error('SSN already registered', 400)
            cursor.execute(
                INSERT_PATIENT_SQL,
                (
                    data['first_name'],
                    data['last_name'],
                    data['dob'],
                    data['ssn'],
                    data.get('insurance_id', ''),
                ),
            )
            conn.commit()
            patient_id = cursor.lastrowid
        return json({'patient_id': patient_id})
    except Exception as e:
        return _error('Failed to register patient', 500)


if __name__ == '__main__':
    init_db()
    app.run(host=SERVER_HOST, port=SERVER_PORT, access_log=False)
