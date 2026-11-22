"""Medical Records System.

A Sanic-based web service backed by a SQLite database.

This module preserves the original public interface (module-level names,
route handlers, routes and the command-line entry point) while organising
the implementation into small helper functions, named constants and a
configuration object.
"""

from sanic import Sanic, response
from sanic.response import json
import sqlite3
import datetime
from dateutil.parser import parse

from dataclasses import dataclass
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the medical records service."""

    app_name: str = 'MedicalRecordsSystem'
    database_path: str = 'medical.db'
    host: str = '0.0.0.0'
    port: int = 8000


CONFIG = AppConfig()


# ---------------------------------------------------------------------------
# Routes and request parameter names
# ---------------------------------------------------------------------------

ROUTE_SEARCH_RECORDS = '/records/search'
ROUTE_ADD_RECORD = '/records/add'
ROUTE_REGISTER_PATIENT = '/patients/register'

PARAM_FIRST_NAME = 'first_name'
PARAM_LAST_NAME = 'last_name'
PARAM_DIAGNOSIS = 'diagnosis'
PARAM_START_DATE = 'start_date'
PARAM_END_DATE = 'end_date'


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

SQL_CREATE_PATIENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        dob TEXT NOT NULL,
        ssn TEXT UNIQUE NOT NULL,
        insurance_id TEXT
    )
"""

SQL_CREATE_RECORDS_TABLE = """
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

SQL_COUNT_PATIENTS = 'SELECT COUNT(*) FROM patients'

SQL_INSERT_PATIENT = """
    INSERT INTO patients (first_name, last_name, dob, ssn, insurance_id)
    VALUES (?, ?, ?, ?, ?)
"""

SQL_INSERT_RECORD = """
    INSERT INTO records (patient_id, visit_date, diagnosis, treatment, physician)
    VALUES (?, ?, ?, ?, ?)
"""


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = Sanic(CONFIG.app_name)


# ---------------------------------------------------------------------------
# Search criteria
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchCriteria:
    """Filter parameters accepted by the record search endpoint."""

    first_name: str = ''
    last_name: str = ''
    diagnosis: str = ''
    start_date: str = ''
    end_date: str = ''


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Open a new connection to the application database."""
    return sqlite3.connect(CONFIG.database_path)


def _create_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(SQL_CREATE_PATIENTS_TABLE)
    cursor.execute(SQL_CREATE_RECORDS_TABLE)


def _seed_if_empty(cursor: sqlite3.Cursor) -> None:
    cursor.execute(SQL_COUNT_PATIENTS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(SQL_INSERT_PATIENT, SEED_PATIENTS)
        cursor.executemany(SQL_INSERT_RECORD, SEED_RECORDS)


def init_db():
    """Create the database schema (if needed) and insert the seed data."""
    conn = get_connection()
    cursor = conn.cursor()
    _create_schema(cursor)
    _seed_if_empty(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _parse_search_criteria(request) -> SearchCriteria:
    return SearchCriteria(
        first_name=request.args.get(PARAM_FIRST_NAME, ''),
        last_name=request.args.get(PARAM_LAST_NAME, ''),
        diagnosis=request.args.get(PARAM_DIAGNOSIS, ''),
        start_date=request.args.get(PARAM_START_DATE, ''),
        end_date=request.args.get(PARAM_END_DATE, ''),
    )


def _build_search_query(criteria: SearchCriteria) -> str:
    # NOTE: value interpolation is intentionally preserved to keep the
    # original behaviour exactly the same.
    query = f"""
        SELECT p.patient_id, p.first_name, p.last_name, p.dob,
               r.visit_date, r.diagnosis, r.treatment, r.physician
        FROM patients p
        JOIN records r ON p.patient_id = r.patient_id
        WHERE p.first_name LIKE '%{criteria.first_name}%'
        AND p.last_name LIKE '%{criteria.last_name}%'
    """
    if criteria.diagnosis:
        query += f" AND r.diagnosis LIKE '%{criteria.diagnosis}%'"
    if criteria.start_date:
        query += f" AND r.visit_date >= '{criteria.start_date}'"
    if criteria.end_date:
        query += f" AND r.visit_date <= '{criteria.end_date}'"
    return query


def _row_to_record_dict(row: tuple) -> Dict[str, Any]:
    return {
        'patient_id': row[0],
        'patient_name': f'{row[1]} {row[2]}',
        'dob': row[3],
        'visit_date': row[4],
        'diagnosis': row[5],
        'treatment': row[6],
        'physician': row[7],
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@app.route(ROUTE_SEARCH_RECORDS, methods=['GET'])
async def search_patient_records(request):
    criteria = _parse_search_criteria(request)

    conn = get_connection()
    cursor = conn.cursor()
    query = _build_search_query(criteria)
    try:
        cursor.execute(query)
        records = [_row_to_record_dict(row) for row in cursor.fetchall()]
        conn.close()
        return json({'records': records})
    except Exception as e:
        conn.close()
        return json({'error': str(e)}, status=500)


@app.route(ROUTE_ADD_RECORD, methods=['POST'])
async def add_patient_record(request):
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(SQL_INSERT_RECORD, (
            data['patient_id'],
            data['visit_date'],
            data['diagnosis'],
            data['treatment'],
            data['physician'],
        ))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return json({'record_id': record_id})
    except Exception as e:
        return json({'error': str(e)}, status=400)


@app.route(ROUTE_REGISTER_PATIENT, methods=['POST'])
async def register_patient(request):
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(SQL_INSERT_PATIENT, (
            data['first_name'],
            data['last_name'],
            data['dob'],
            data['ssn'],
            data.get('insurance_id', ''),
        ))
        conn.commit()
        patient_id = cursor.lastrowid
        conn.close()
        return json({'patient_id': patient_id})
    except Exception as e:
        return json({'error': str(e)}, status=400)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(host=CONFIG.host, port=CONFIG.port)
