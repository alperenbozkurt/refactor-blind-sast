from contextlib import contextmanager

from sanic import Sanic, response
from sanic.response import json
import sqlite3
import datetime
from dateutil.parser import parse
import re

app = Sanic('MedicalRecordsSystem')

DB_PATH = 'medical.db'

CREATE_PATIENTS_SQL = '''
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            ssn TEXT UNIQUE NOT NULL,
            insurance_id TEXT
        )
    '''

CREATE_RECORDS_SQL = '''
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

INSERT_PATIENT_SQL = '''
            INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_RECORD_SQL = '''
            INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)
            VALUES (?, ?, ?, ?, ?)
        '''

SEARCH_SQL = '''
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


@contextmanager
def _connect():
    """Open a database connection and guarantee it is closed afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _error(message, status):
    return json({'error': message}, status=status)


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PATIENTS_SQL)
        cursor.execute(CREATE_RECORDS_SQL)
        cursor.execute('SELECT COUNT(*) FROM patients')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PATIENT_SQL, SEED_PATIENTS)
            cursor.executemany(INSERT_RECORD_SQL, SEED_RECORDS)
        conn.commit()


def validate_name(name):
    if not re.match("^[a-zA-Z\\-\\'\\s]{1,50}$", name):
        raise ValueError('Invalid name format')
    return name


def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD')


def validate_ssn(ssn):
    if not re.match('^\\d{3}-\\d{2}-\\d{4}$', ssn):
        raise ValueError('Invalid SSN format. Use XXX-XX-XXXX')
    return ssn


def sanitize_input(input_str):
    if not input_str:
        return ''
    return re.sub('[;\\\'"\\\\]', '', input_str)


@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    try:
        first_name = sanitize_input(request.args.get('first_name', ''))
        last_name = sanitize_input(request.args.get('last_name', ''))
        diagnosis = sanitize_input(request.args.get('diagnosis', ''))
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        with _connect() as conn:
            cursor = conn.cursor()
            query = SEARCH_SQL
            params = [f'%{first_name}%', f'%{last_name}%']

            if diagnosis:
                query += ' AND r.diagnosis LIKE ?'
                params.append(f'%{diagnosis}%')

            for date_value, operator in ((start_date, '>='), (end_date, '<=')):
                if not date_value:
                    continue
                try:
                    validate_date(date_value)
                except ValueError as e:
                    return _error(str(e), 400)
                query += f' AND r.visit_date {operator} ?'
                params.append(date_value)

            cursor.execute(query, params)
            records = [
                {
                    'patient_id': row[0],
                    'patient_name': f'{row[1]} {row[2]}',
                    'dob': row[3],
                    'visit_date': row[4],
                    'diagnosis': row[5],
                    'treatment': row[6],
                    'physician': row[7],
                }
                for row in cursor.fetchall()
            ]
        return json({'records': records})
    except Exception:
        return _error('Internal server error', 500)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        required_fields = ['patient_id', 'visit_date', 'diagnosis', 'physician']
        if not all((key in data for key in required_fields)):
            return _error('Missing required fields', 400)

        try:
            validate_date(data['visit_date'])
            if not str(data['patient_id']).isdigit():
                raise ValueError('Invalid patient ID')
        except ValueError as e:
            return _error(str(e), 400)

        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM patients WHERE patient_id = ?',
                           (data['patient_id'],))
            if not cursor.fetchone():
                return _error('Patient not found', 404)

            cursor.execute(INSERT_RECORD_SQL, (
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
        return _error('Failed to add record', 500)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        required_fields = ['first_name', 'last_name', 'dob', 'ssn']
        if not all((key in data for key in required_fields)):
            return _error('Missing required fields', 400)

        try:
            validate_name(data['first_name'])
            validate_name(data['last_name'])
            validate_date(data['dob'])
            validate_ssn(data['ssn'])
        except ValueError as e:
            return _error(str(e), 400)

        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM patients WHERE ssn = ?', (data['ssn'],))
            if cursor.fetchone():
                return _error('SSN already registered', 400)

            cursor.execute(INSERT_PATIENT_SQL, (
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
        return _error('Failed to register patient', 500)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, access_log=False)
