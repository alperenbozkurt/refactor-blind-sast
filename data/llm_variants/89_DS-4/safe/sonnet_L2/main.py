from contextlib import contextmanager
from datetime import datetime
import sqlite3
import uuid
from typing import Any, Iterator, List, Optional, Sequence, Tuple

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DB_PATH = 'legal_cases.db'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

CASE_ID_PREFIX = 'CASE-'
CASE_ID_SUFFIX_LENGTH = 4

VALID_STATUSES = ['open', 'active', 'closed']
STATUS_CLOSED = 'closed'
STATUS_PATTERN = '^(open|active|closed)$'

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #

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

SEARCH_CASES_BASE_SQL = """
        SELECT c.case_id, c.title, c.description, c.status, 
               c.client_id, c.assigned_to, c.created_at
        FROM cases c
        WHERE 1=1
    """

CLIENT_EXISTS_SQL = 'SELECT 1 FROM clients WHERE client_id = ?'
ATTORNEY_EXISTS_SQL = 'SELECT 1 FROM attorneys WHERE attorney_id = ?'

UPDATE_CASE_STATUS_SQL = """
            UPDATE cases 
            SET status = ?, closed_at = ?
            WHERE case_id = ?
        """

# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #

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

# --------------------------------------------------------------------------- #
# Application and models
# --------------------------------------------------------------------------- #

app = FastAPI()


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

@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    """Open a connection to the database and always close it afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


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


def init_db():
    with _connection() as conn:
        cursor = conn.cursor()
        _create_schema(cursor)
        _seed_data(cursor)
        conn.commit()


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
) -> Tuple[str, List[Any]]:
    sql = SEARCH_CASES_BASE_SQL
    params: List[Any] = []
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


def _generate_case_id() -> str:
    suffix = str(uuid.uuid4())[:CASE_ID_SUFFIX_LENGTH].upper()
    return f'{CASE_ID_PREFIX}{suffix}'


def _validate_new_case(case: Case) -> None:
    if not all([case.title, case.description, case.client_id, case.assigned_to]):
        raise HTTPException(status_code=400, detail='Missing required fields')
    if case.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail='Invalid status value')


def _ensure_references_exist(cursor: sqlite3.Cursor, case: Case) -> None:
    cursor.execute(CLIENT_EXISTS_SQL, (case.client_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=400, detail='Client not found')
    cursor.execute(ATTORNEY_EXISTS_SQL, (case.assigned_to,))
    if not cursor.fetchone():
        raise HTTPException(status_code=400, detail='Attorney not found')


def _closed_at_for(new_status: str) -> Optional[str]:
    return datetime.now().isoformat() if new_status == STATUS_CLOSED else None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get('/cases/search', response_model=list[Case])
def search_cases(query: Optional[str]=Query(None, description='Search term for case title or description'), status: Optional[str]=Query(None, description='Filter by case status'), client_id: Optional[str]=Query(None, description='Filter by client ID'), assigned_to: Optional[str]=Query(None, description='Filter by assigned attorney')):
    with _connection() as conn:
        cursor = conn.cursor()
        sql, params = _build_search_query(query, status, client_id, assigned_to)
        try:
            cursor.execute(sql, params)
            return [_row_to_case(row) for row in cursor.fetchall()]
        except Exception:
            raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/cases/create')
def create_case(case: Case):
    try:
        _validate_new_case(case)
        with _connection() as conn:
            cursor = conn.cursor()
            _ensure_references_exist(cursor, case)
            case_id = _generate_case_id()
            cursor.execute(
                INSERT_CASE_SQL,
                (case_id, case.title, case.description, case.status, case.client_id, case.assigned_to),
            )
            conn.commit()
        return {'case_id': case_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail='Failed to create case')


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str=Query(..., regex=STATUS_PATTERN)):
    try:
        if not case_id.startswith(CASE_ID_PREFIX):
            raise HTTPException(status_code=400, detail='Invalid case ID format')
        with _connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                UPDATE_CASE_STATUS_SQL,
                (new_status, _closed_at_for(new_status), case_id),
            )
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'status': 'success'}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail='Failed to update case status')


if __name__ == '__main__':
    import uvicorn
    init_db()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
