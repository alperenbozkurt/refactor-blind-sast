from contextlib import closing

from sanic import Sanic, response
from sanic.response import json
import sqlite3
import datetime
from dateutil.parser import parse
import re

app = Sanic('MedicalRecordsSystem')

DB_PATH = 'medical.db'

NAME_PATTERN = "^[a-zA-Z\\-\\'\\s]{1,50}$"
SSN_PATTERN = '^\\d{3}-\\d{2}-\\d{4}$'
SANITIZE_PATTERN = '[;\\\'"\\\\]'

CREATE_PATIENTS_TABLE = """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            ssn TEXT UNIQUE NOT NULL,
            insurance_id TEXT
        )
    """

CREATE_RECORDS_TABLE = """
        CREATE TABLE IF NOT EXISTS records (
            record_id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            visit_date TEXT NOT NULL,
            diagnosis TEXT,
            treatment TEXT,
            physician TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
        )
    """

INSERT_PATIENT = """
            INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)
            VALUES (?, ?, ?, ?, ?)
        """

INSERT_RECORD = """
            INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)
            VALUES (?, ?, ?, ?, ?)
        """

SEARCH_QUERY = """
            SELECT p.patient_id, p.first_name, p.last_name, p.dob, 
                   r.visit_date, r.diagnosis, r.treatment, r.physician
            FROM patients p
            JOIN records r ON p.patient_id = r.patient_id
            WHERE p.first_name LIKE ?
            AND p.last_name LIKE ?
        """

SAMPLE_PATIENTS = [
    ('John', 'Smith', '1980-05-15', '123-45-6789', 'INS123456'),
    ('Sarah', 'Johnson', '1975-11-22', '987-65-4321', 'INS789012'),
    ('Michael', 'Williams', '1990-02-10', '456-78-9012', 'INS345678'),
]

SAMPLE_RECORDS = [
    (1, '2023-01-10', 'Hypertension', 'Prescribed medication', 'Dr. Anderson'),
    (1, '2023-03-15', 'Annual checkup', 'Routine tests', 'Dr. Brown'),
    (2, '2023-02-20', 'Diabetes', 'Insulin therapy', 'Dr. Carter'),
]

ADD_RECORD_REQUIRED_FIELDS = ['patient_id', 'visit_date', 'diagnosis', 'physician']
REGISTER_REQUIRED_FIELDS = ['first_name', 'last_name', 'dob', 'ssn']


def _connect():
    return sqlite3.connect(DB_PATH)


def _has_all_fields(data, fields):
    return all((key in data for key in fields))


def init_db():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PATIENTS_TABLE)
        cursor.execute(CREATE_RECORDS_TABLE)
        cursor.execute('SELECT COUNT(*) FROM patients')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PATIENT, SAMPLE_PATIENTS)
            cursor.executemany(INSERT_RECORD, SAMPLE_RECORDS)
        conn.commit()


def validate_name(name):
    if not re.match(NAME_PATTERN, name):
        raise ValueError('Invalid name format')
    return name


def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
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


def _row_to_search_result(row):
    return {
        'patient_id': row[0],
        'patient_name': f'{row[1]} {row[2]}',
        'dob': row[3],
        'visit_date': row[4],
        'diagnosis': row[5],
        'treatment': row[6],
        'physician': row[7],
    }


@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    try:
        first_name = sanitize_input(request.args.get('first_name', ''))
        last_name = sanitize_input(request.args.get('last_name', ''))
        diagnosis = sanitize_input(request.args.get('diagnosis', ''))
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            query = SEARCH_QUERY
            params = [f'%{first_name}%', f'%{last_name}%']

            if diagnosis:
                query += ' AND r.diagnosis LIKE ?'
                params.append(f'%{diagnosis}%')

            date_filters = [
                (start_date, ' AND r.visit_date >= ?'),
                (end_date, ' AND r.visit_date <= ?'),
            ]
            for date_value, clause in date_filters:
                if not date_value:
                    continue
                try:
                    validate_date(date_value)
                except ValueError as e:
                    return json({'error': str(e)}, status=400)
                query += clause
                params.append(date_value)

            cursor.execute(query, params)
            records = [_row_to_search_result(row) for row in cursor.fetchall()]

        return json({'records': records})
    except Exception:
        return json({'error': 'Internal server error'}, status=500)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        if not _has_all_fields(data, ADD_RECORD_REQUIRED_FIELDS):
            return json({'error': 'Missing required fields'}, status=400)

        try:
            validate_date(data['visit_date'])
            if not str(data['patient_id']).isdigit():
                raise ValueError('Invalid patient ID')
        except ValueError as e:
            return json({'error': str(e)}, status=400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM patients WHERE patient_id = ?',
                (data['patient_id'],),
            )
            if not cursor.fetchone():
                return json({'error': 'Patient not found'}, status=404)

            cursor.execute(
                INSERT_RECORD,
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
    except Exception:
        return json({'error': 'Failed to add record'}, status=500)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        if not _has_all_fields(data, REGISTER_REQUIRED_FIELDS):
            return json({'error': 'Missing required fields'}, status=400)

        try:
            validate_name(data['first_name'])
            validate_name(data['last_name'])
            validate_date(data['dob'])
            validate_ssn(data['ssn'])
        except ValueError as e:
            return json({'error': str(e)}, status=400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM patients WHERE ssn = ?', (data['ssn'],))
            if cursor.fetchone():
                return json({'error': 'SSN already registered'}, status=400)

            cursor.execute(
                INSERT_PATIENT,
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
    except Exception:
        return json({'error': 'Failed to register patient'}, status=500)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, access_log=False)
