"""Legal case management API.

A small FastAPI service backed by a SQLite database for managing legal
cases, clients and attorneys.
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the service."""

    database_path: str = 'legal_cases.db'
    host: str = '0.0.0.0'
    port: int = 8000


SETTINGS = Settings()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ID_PREFIX = 'CASE'
CASE_ID_SUFFIX_LENGTH = 4
STATUS_CLOSED = 'closed'

CREATE_CLIENTS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT
        )
    """

CREATE_ATTORNEYS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS attorneys (
            attorney_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            specialization TEXT
        )
    """

CREATE_CASES_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            client_id TEXT NOT NULL,
            assigned_to TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(client_id),
            FOREIGN KEY(assigned_to) REFERENCES attorneys(attorney_id)
        )
    """

COUNT_CLIENTS_SQL = 'SELECT COUNT(*) FROM clients'

INSERT_CLIENT_SQL = """
            INSERT INTO clients (client_id, name, contact_email, phone, address)
            VALUES (?, ?, ?, ?, ?)
        """

INSERT_ATTORNEY_SQL = """
            INSERT INTO attorneys (attorney_id, name, email, specialization)
            VALUES (?, ?, ?, ?)
        """

INSERT_CASE_SQL = """
            INSERT INTO cases (case_id, title, description, status, client_id, assigned_to)
            VALUES (?, ?, ?, ?, ?, ?)
        """

SELECT_CASES_BASE_SQL = """
        SELECT c.case_id, c.title, c.description, c.status, 
               c.client_id, c.assigned_to, c.created_at
        FROM cases c
        WHERE 1=1
    """

UPDATE_CASE_STATUS_SQL = """
            UPDATE cases 
            SET status = ?, closed_at = ?
            WHERE case_id = ?
        """

SEED_CLIENTS = [
    ('CLI-1001', 'Acme Corp', 'legal@acme.com', '555-1001', '123 Business Ave'),
    ('CLI-1002', 'Smith Family', 'smith.family@example.com', '555-1002', '456 Residential St'),
]

SEED_ATTORNEYS = [
    ('ATT-1001', 'Robert Johnson', 'r.johnson@lawfirm.com', 'Corporate'),
    ('ATT-1002', 'Sarah Williams', 's.williams@lawfirm.com', 'Family'),
]

SEED_CASES = [
    ('CASE-1001', 'Acme Merger', 'Review merger documents', 'open', 'CLI-1001', 'ATT-1001'),
    ('CASE-1002', 'Smith Divorce', 'Divorce proceedings', 'active', 'CLI-1002', 'ATT-1002'),
]


# ---------------------------------------------------------------------------
# Application and models
# ---------------------------------------------------------------------------

app = FastAPI()


class Case(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    client_id: str
    assigned_to: str
    created_at: str


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Open a new connection to the application database."""
    return sqlite3.connect(SETTINGS.database_path)


def _create_tables(cursor: sqlite3.Cursor) -> None:
    """Create the database schema if it does not already exist."""
    cursor.execute(CREATE_CLIENTS_TABLE_SQL)
    cursor.execute(CREATE_ATTORNEYS_TABLE_SQL)
    cursor.execute(CREATE_CASES_TABLE_SQL)


def _seed_initial_data(cursor: sqlite3.Cursor) -> None:
    """Insert demo data when the database has no clients yet."""
    cursor.execute(COUNT_CLIENTS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CLIENT_SQL, SEED_CLIENTS)
        cursor.executemany(INSERT_ATTORNEY_SQL, SEED_ATTORNEYS)
        cursor.executemany(INSERT_CASE_SQL, SEED_CASES)


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def _generate_case_id() -> str:
    """Generate a short, human-readable unique case identifier."""
    return f'{CASE_ID_PREFIX}-{str(uuid.uuid4())[:CASE_ID_SUFFIX_LENGTH].upper()}'


def _closed_at_for_status(status: str) -> Optional[str]:
    """Return a timestamp for closed cases, otherwise None."""
    return datetime.now().isoformat() if status == STATUS_CLOSED else None


def _build_search_query(
    query: Optional[str],
    status: Optional[str],
    client_id: Optional[str],
    assigned_to: Optional[str],
) -> str:
    """Build the case search SQL statement from the given filters."""
    sql = SELECT_CASES_BASE_SQL
    if query:
        sql += f" AND (c.title LIKE '%{query}%' OR c.description LIKE '%{query}%')"
    if status:
        sql += f" AND c.status = '{status}'"
    if client_id:
        sql += f" AND c.client_id = '{client_id}'"
    if assigned_to:
        sql += f" AND c.assigned_to = '{assigned_to}'"
    return sql


def _row_to_case(row: tuple) -> Case:
    """Map a database row onto a Case model instance."""
    return Case(
        case_id=row[0],
        title=row[1],
        description=row[2],
        status=row[3],
        client_id=row[4],
        assigned_to=row[5],
        created_at=row[6],
    )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def init_db():
    """Initialise the database schema and seed it with demo data."""
    conn = _get_connection()
    cursor = conn.cursor()
    _create_tables(cursor)
    _seed_initial_data(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/cases/search', response_model=list[Case])
def search_cases(
    query: Optional[str] = Query(None, description='Search term for case title or description'),
    status: Optional[str] = Query(None, description='Filter by case status'),
    client_id: Optional[str] = Query(None, description='Filter by client ID'),
    assigned_to: Optional[str] = Query(None, description='Filter by assigned attorney'),
):
    """Search cases by free text and/or structured filters."""
    conn = _get_connection()
    cursor = conn.cursor()
    search_sql = _build_search_query(query, status, client_id, assigned_to)
    try:
        cursor.execute(search_sql)
        cases = [_row_to_case(row) for row in cursor.fetchall()]
        conn.close()
        return cases
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/cases/create')
def create_case(case: Case):
    """Create a new case and return its generated identifier."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        case_id = _generate_case_id()
        cursor.execute(
            INSERT_CASE_SQL,
            (case_id, case.title, case.description, case.status, case.client_id, case.assigned_to),
        )
        conn.commit()
        conn.close()
        return {'case_id': case_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str):
    """Update the status of an existing case."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            UPDATE_CASE_STATUS_SQL,
            (new_status, _closed_at_for_status(new_status), case_id),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import uvicorn
    init_db()
    uvicorn.run(app, host=SETTINGS.host, port=SETTINGS.port)
