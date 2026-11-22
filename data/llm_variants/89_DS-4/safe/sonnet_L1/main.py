import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

DB_PATH = 'legal_cases.db'
VALID_STATUSES = ['open', 'active', 'closed']

app = FastAPI()


class Case(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    client_id: str
    assigned_to: str
    created_at: str


CREATE_CLIENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact_email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT
    )
"""

CREATE_ATTORNEYS_TABLE = """
    CREATE TABLE IF NOT EXISTS attorneys (
        attorney_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        specialization TEXT
    )
"""

CREATE_CASES_TABLE = """
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

INSERT_CLIENT = """
    INSERT INTO clients (client_id, name, contact_email, phone, address)
    VALUES (?, ?, ?, ?, ?)
"""

INSERT_ATTORNEY = """
    INSERT INTO attorneys (attorney_id, name, email, specialization)
    VALUES (?, ?, ?, ?)
"""

INSERT_CASE = """
    INSERT INTO cases (case_id, title, description, status, client_id, assigned_to)
    VALUES (?, ?, ?, ?, ?, ?)
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

SEARCH_BASE_QUERY = """
    SELECT c.case_id, c.title, c.description, c.status,
           c.client_id, c.assigned_to, c.created_at
    FROM cases c
    WHERE 1=1
"""


def _connect():
    return closing(sqlite3.connect(DB_PATH))


def _row_to_case(row) -> Case:
    return Case(
        case_id=row[0],
        title=row[1],
        description=row[2],
        status=row[3],
        client_id=row[4],
        assigned_to=row[5],
        created_at=row[6],
    )


def _exists(cursor, sql: str, value: str) -> bool:
    cursor.execute(sql, (value,))
    return cursor.fetchone() is not None


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_CLIENTS_TABLE)
        cursor.execute(CREATE_ATTORNEYS_TABLE)
        cursor.execute(CREATE_CASES_TABLE)

        cursor.execute('SELECT COUNT(*) FROM clients')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_CLIENT, SEED_CLIENTS)
            cursor.executemany(INSERT_ATTORNEY, SEED_ATTORNEYS)
            cursor.executemany(INSERT_CASE, SEED_CASES)
        conn.commit()


def _build_search_query(query, status, client_id, assigned_to):
    sql = SEARCH_BASE_QUERY
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


@app.get('/cases/search', response_model=list[Case])
def search_cases(
    query: Optional[str] = Query(None, description='Search term for case title or description'),
    status: Optional[str] = Query(None, description='Filter by case status'),
    client_id: Optional[str] = Query(None, description='Filter by client ID'),
    assigned_to: Optional[str] = Query(None, description='Filter by assigned attorney'),
):
    sql, params = _build_search_query(query, status, client_id, assigned_to)
    with _connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            return [_row_to_case(row) for row in cursor.fetchall()]
        except Exception:
            raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/cases/create')
def create_case(case: Case):
    try:
        if not all([case.title, case.description, case.client_id, case.assigned_to]):
            raise HTTPException(status_code=400, detail='Missing required fields')
        if case.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail='Invalid status value')

        with _connect() as conn:
            cursor = conn.cursor()
            if not _exists(cursor, 'SELECT 1 FROM clients WHERE client_id = ?', case.client_id):
                raise HTTPException(status_code=400, detail='Client not found')
            if not _exists(cursor, 'SELECT 1 FROM attorneys WHERE attorney_id = ?', case.assigned_to):
                raise HTTPException(status_code=400, detail='Attorney not found')

            case_id = f'CASE-{str(uuid.uuid4())[:4].upper()}'
            cursor.execute(
                INSERT_CASE,
                (case_id, case.title, case.description, case.status,
                 case.client_id, case.assigned_to),
            )
            conn.commit()
        return {'case_id': case_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail='Failed to create case')


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str = Query(..., regex='^(open|active|closed)$')):
    try:
        if not case_id.startswith('CASE-'):
            raise HTTPException(status_code=400, detail='Invalid case ID format')

        closed_at = datetime.now().isoformat() if new_status == 'closed' else None
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE cases
                SET status = ?, closed_at = ?
                WHERE case_id = ?
                """,
                (new_status, closed_at, case_id),
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
    uvicorn.run(app, host='0.0.0.0', port=8000)
