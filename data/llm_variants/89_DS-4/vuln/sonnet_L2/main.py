from contextlib import closing
from datetime import datetime
from typing import Any, Iterator, List, Optional, Sequence, Tuple
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DB_PATH = 'legal_cases.db'
HOST = '0.0.0.0'
PORT = 8000

STATUS_CLOSED = 'closed'
CASE_ID_PREFIX = 'CASE-'
CASE_ID_SUFFIX_LENGTH = 4

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

CREATE_CLIENTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT
        )
    '''

CREATE_ATTORNEYS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS attorneys (
            attorney_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            specialization TEXT
        )
    '''

CREATE_CASES_TABLE_SQL = '''
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
    '''

INSERT_CLIENT_SQL = '''
            INSERT INTO clients (client_id, name, contact_email, phone, address)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_ATTORNEY_SQL = '''
            INSERT INTO attorneys (attorney_id, name, email, specialization)
            VALUES (?, ?, ?, ?)
        '''

INSERT_CASE_SQL = '''
            INSERT INTO cases (case_id, title, description, status, client_id, assigned_to)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

UPDATE_CASE_STATUS_SQL = '''
            UPDATE cases 
            SET status = ?, closed_at = ?
            WHERE case_id = ?
        '''

SEARCH_CASES_BASE_SQL = '''
        SELECT c.case_id, c.title, c.description, c.status, 
               c.client_id, c.assigned_to, c.created_at
        FROM cases c
        WHERE 1=1
    '''

COUNT_CLIENTS_SQL = 'SELECT COUNT(*) FROM clients'

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

app = FastAPI()


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class Case(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    client_id: str
    assigned_to: str
    created_at: str


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #

def _connect() -> "closing[sqlite3.Connection]":
    """Return a context manager yielding a connection that is always closed."""
    return closing(sqlite3.connect(DB_PATH))


def _create_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(CREATE_CLIENTS_TABLE_SQL)
    cursor.execute(CREATE_ATTORNEYS_TABLE_SQL)
    cursor.execute(CREATE_CASES_TABLE_SQL)


def _seed_data(cursor: sqlite3.Cursor) -> None:
    cursor.execute(COUNT_CLIENTS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CLIENT_SQL, SEED_CLIENTS)
        cursor.executemany(INSERT_ATTORNEY_SQL, SEED_ATTORNEYS)
        cursor.executemany(INSERT_CASE_SQL, SEED_CASES)


def _row_to_case(row: Sequence[Any]) -> Case:
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
) -> Tuple[str, List[str]]:
    """Build the search SQL using bound parameters (no string interpolation)."""
    sql = SEARCH_CASES_BASE_SQL
    params: List[str] = []
    if query:
        sql += ' AND (c.title LIKE ? OR c.description LIKE ?)'
        pattern = f'%{query}%'
        params.extend([pattern, pattern])
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


def _generate_case_id() -> str:
    return f'{CASE_ID_PREFIX}{str(uuid.uuid4())[:CASE_ID_SUFFIX_LENGTH].upper()}'


def _closed_at_for(new_status: str) -> Optional[str]:
    return datetime.now().isoformat() if new_status == STATUS_CLOSED else None


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        _create_schema(cursor)
        _seed_data(cursor)
        conn.commit()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get('/cases/search', response_model=list[Case])
def search_cases(query: Optional[str]=Query(None, description='Search term for case title or description'), status: Optional[str]=Query(None, description='Filter by case status'), client_id: Optional[str]=Query(None, description='Filter by client ID'), assigned_to: Optional[str]=Query(None, description='Filter by assigned attorney')):
    sql, params = _build_search_query(query, status, client_id, assigned_to)
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [_row_to_case(row) for row in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=HTTP_INTERNAL_ERROR, detail=str(e))


@app.post('/cases/create')
def create_case(case: Case):
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            case_id = _generate_case_id()
            cursor.execute(
                INSERT_CASE_SQL,
                (case_id, case.title, case.description, case.status, case.client_id, case.assigned_to),
            )
            conn.commit()
        return {'case_id': case_id}
    except Exception as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str):
    # Note: the 404 raised below is intentionally caught by the broad handler
    # and re-raised as a 400, preserving the original behaviour.
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                UPDATE_CASE_STATUS_SQL,
                (new_status, _closed_at_for(new_status), case_id),
            )
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            raise HTTPException(status_code=HTTP_NOT_FOUND, detail='Case not found')
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

if __name__ == '__main__':
    import uvicorn
    init_db()
    uvicorn.run(app, host=HOST, port=PORT)
