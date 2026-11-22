from fastapi import FastAPI, HTTPException, Query
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the legal case service."""

    database_path: str = 'legal_cases.db'
    server_host: str = '0.0.0.0'
    server_port: int = 8000


settings = Settings()

app = FastAPI()


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

CASE_ID_PREFIX = 'CASE-'
CASE_ID_SUFFIX_LENGTH = 4
CLOSED_STATUS = 'closed'
VALID_STATUSES = ['open', 'active', 'closed']


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

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

INSERT_CLIENT_SQL = (
    'INSERT INTO clients (client_id, name, contact_email, phone, address) '
    'VALUES (?, ?, ?, ?, ?)'
)
INSERT_ATTORNEY_SQL = (
    'INSERT INTO attorneys (attorney_id, name, email, specialization) '
    'VALUES (?, ?, ?, ?)'
)
INSERT_CASE_SQL = (
    'INSERT INTO cases (case_id, title, description, status, client_id, assigned_to) '
    'VALUES (?, ?, ?, ?, ?, ?)'
)

COUNT_CLIENTS_SQL = 'SELECT COUNT(*) FROM clients'
SELECT_CLIENT_SQL = 'SELECT 1 FROM clients WHERE client_id = ?'
SELECT_ATTORNEY_SQL = 'SELECT 1 FROM attorneys WHERE attorney_id = ?'

UPDATE_CASE_STATUS_SQL = """
    UPDATE cases
    SET status = ?, closed_at = ?
    WHERE case_id = ?
"""

SEARCH_CASES_BASE_SQL = """
    SELECT c.case_id, c.title, c.description, c.status,
           c.client_id, c.assigned_to, c.created_at
    FROM cases c
    WHERE 1=1
"""


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

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
# Models
# ---------------------------------------------------------------------------

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

def _connect() -> sqlite3.Connection:
    """Open a new connection to the application database."""
    return sqlite3.connect(settings.database_path)


def _create_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute(CREATE_CLIENTS_TABLE_SQL)
    cursor.execute(CREATE_ATTORNEYS_TABLE_SQL)
    cursor.execute(CREATE_CASES_TABLE_SQL)


def _seed_initial_data(cursor: sqlite3.Cursor) -> None:
    cursor.executemany(INSERT_CLIENT_SQL, SEED_CLIENTS)
    cursor.executemany(INSERT_ATTORNEY_SQL, SEED_ATTORNEYS)
    cursor.executemany(INSERT_CASE_SQL, SEED_CASES)


def _row_to_case(row: tuple) -> Case:
    """Map a cases table row onto the Case response model."""
    return Case(
        case_id=row[0],
        title=row[1],
        description=row[2],
        status=row[3],
        client_id=row[4],
        assigned_to=row[5],
        created_at=row[6],
    )


def _build_search_query(
    query: Optional[str],
    status: Optional[str],
    client_id: Optional[str],
    assigned_to: Optional[str],
) -> tuple[str, list]:
    """Build the parameterized case search SQL and its bound parameters."""
    sql = SEARCH_CASES_BASE_SQL
    params = []
    if query:
        sql += ' AND (c.title LIKE ? OR c.description LIKE ?)'
        search_term = f'%{query}%'
        params.extend([search_term, search_term])
    if status:
        sql += ' AND c.status = ?'
        params.append(status)
    if client_id:
        sql += ' AND c.client_id = ?'
        params.append(client_id)
    if assigned_to:
        sql += ' AND c.assigned_to = ?'
        params.append(assigned_to)
    return sql, params


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_new_case(case: Case) -> None:
    if not all([case.title, case.description, case.client_id, case.assigned_to]):
        raise HTTPException(status_code=400, detail='Missing required fields')
    if case.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail='Invalid status value')


def _ensure_client_exists(cursor: sqlite3.Cursor, client_id: str) -> None:
    cursor.execute(SELECT_CLIENT_SQL, (client_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=400, detail='Client not found')


def _ensure_attorney_exists(cursor: sqlite3.Cursor, attorney_id: str) -> None:
    cursor.execute(SELECT_ATTORNEY_SQL, (attorney_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=400, detail='Attorney not found')


def _generate_case_id() -> str:
    return f'{CASE_ID_PREFIX}{str(uuid.uuid4())[:CASE_ID_SUFFIX_LENGTH].upper()}'


def _closed_timestamp(new_status: str) -> Optional[str]:
    return datetime.now().isoformat() if new_status == CLOSED_STATUS else None


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

def init_db():
    conn = _connect()
    cursor = conn.cursor()
    _create_tables(cursor)
    cursor.execute(COUNT_CLIENTS_SQL)
    if cursor.fetchone()[0] == 0:
        _seed_initial_data(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/cases/search', response_model=list[Case])
def search_cases(query: Optional[str]=Query(None, description='Search term for case title or description'), status: Optional[str]=Query(None, description='Filter by case status'), client_id: Optional[str]=Query(None, description='Filter by client ID'), assigned_to: Optional[str]=Query(None, description='Filter by assigned attorney')):
    conn = _connect()
    cursor = conn.cursor()
    base_query, params = _build_search_query(query, status, client_id, assigned_to)
    try:
        cursor.execute(base_query, params)
        cases = [_row_to_case(row) for row in cursor.fetchall()]
        conn.close()
        return cases
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/cases/create')
def create_case(case: Case):
    try:
        _validate_new_case(case)
        conn = _connect()
        cursor = conn.cursor()
        _ensure_client_exists(cursor, case.client_id)
        _ensure_attorney_exists(cursor, case.assigned_to)
        case_id = _generate_case_id()
        cursor.execute(INSERT_CASE_SQL, (case_id, case.title, case.description, case.status, case.client_id, case.assigned_to))
        conn.commit()
        conn.close()
        return {'case_id': case_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail='Failed to create case')


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str=Query(..., regex='^(open|active|closed)$')):
    try:
        if not case_id.startswith(CASE_ID_PREFIX):
            raise HTTPException(status_code=400, detail='Invalid case ID format')
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(UPDATE_CASE_STATUS_SQL, (new_status, _closed_timestamp(new_status), case_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'status': 'success'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail='Failed to update case status')


if __name__ == '__main__':
    import uvicorn
    init_db()
    uvicorn.run(app, host=settings.server_host, port=settings.server_port)
