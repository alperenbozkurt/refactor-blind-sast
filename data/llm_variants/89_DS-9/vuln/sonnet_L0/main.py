from contextlib import closing
import datetime
import sqlite3

from dateutil.parser import parse
from sanic import Sanic, response
from sanic.response import json

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

SEARCH_BASE_SQL = '''
    SELECT p.patient_id, p.first_name, p.last_name, p.dob,
           r.visit_date, r.diagnosis, r.treatment, r.physician
    FROM patients p
    JOIN records r ON p.patient_id = r.patient_id
    WHERE p.first_name LIKE ?
    AND p.last_name LIKE ?
'''

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


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_PATIENTS_SQL)
        cursor.execute(CREATE_RECORDS_SQL)
        cursor.execute('SELECT COUNT(*) FROM patients')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_PATIENT_SQL, SAMPLE_PATIENTS)
            cursor.executemany(INSERT_RECORD_SQL, SAMPLE_RECORDS)
        conn.commit()


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


@app.route('/records/search', methods=['GET'])
async def search_patient_records(request):
    first_name = request.args.get('first_name', '')
    last_name = request.args.get('last_name', '')
    diagnosis = request.args.get('diagnosis', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = SEARCH_BASE_SQL
    params = [f'%{first_name}%', f'%{last_name}%']
    if diagnosis:
        query += ' AND r.diagnosis LIKE ?'
        params.append(f'%{diagnosis}%')
    if start_date:
        query += ' AND r.visit_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND r.visit_date <= ?'
        params.append(end_date)

    with closing(_connect()) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            records = [_row_to_record(row) for row in cursor.fetchall()]
            return json({'records': records})
        except Exception as e:
            return json({'error': str(e)}, status=500)


@app.route('/records/add', methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(INSERT_RECORD_SQL, (
                data['patient_id'],
                data['visit_date'],
                data['diagnosis'],
                data['treatment'],
                data['physician'],
            ))
            conn.commit()
            record_id = cursor.lastrowid
        return json({'record_id': record_id})
    except Exception as e:
        return json({'error': str(e)}, status=400)


@app.route('/patients/register', methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        with closing(_connect()) as conn:
            cursor = conn.cursor()
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
    except Exception as e:
        return json({'error': str(e)}, status=400)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
