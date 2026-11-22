import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI()

DB_PATH = 'legal_cases.db'

CREATE_CLIENTS_SQL = '''
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact_email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT
    )
'''

CREATE_ATTORNEYS_SQL = '''
    CREATE TABLE IF NOT EXISTS attorneys (
        attorney_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        specialization TEXT
    )
'''

CREATE_CASES_SQL = '''
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

SEARCH_BASE_SQL = '''
    SELECT c.case_id, c.title, c.description, c.status,
           c.client_id, c.assigned_to, c.created_at
    FROM cases c
    WHERE 1=1
'''

UPDATE_STATUS_SQL = '''
    UPDATE cases
    SET status = ?, closed_at = ?
    WHERE case_id = ?
'''


class Case(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    client_id: str
    assigned_to: str
    created_at: str


def _connect():
    return closing(sqlite3.connect(DB_PATH))


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_CLIENTS_SQL)
        cursor.execute(CREATE_ATTORNEYS_SQL)
        cursor.execute(CREATE_CASES_SQL)

        cursor.execute('SELECT COUNT(*) FROM clients')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_CLIENT_SQL, SEED_CLIENTS)
            cursor.executemany(INSERT_ATTORNEY_SQL, SEED_ATTORNEYS)
            cursor.executemany(INSERT_CASE_SQL, SEED_CASES)
        conn.commit()


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


@app.get('/cases/search', response_model=list[Case])
def search_cases(
    query: Optional[str] = Query(None, description='Search term for case title or description'),
    status: Optional[str] = Query(None, description='Filter by case status'),
    client_id: Optional[str] = Query(None, description='Filter by client ID'),
    assigned_to: Optional[str] = Query(None, description='Filter by assigned attorney'),
):
    sql = SEARCH_BASE_SQL
    params = []

    if query:
        sql += ' AND (c.title LIKE ? OR c.description LIKE ?)'
        like = f'%{query}%'
        params.extend([like, like])
    if status:
        sql += ' AND c.status = ?'
        params.append(status)
    if client_id:
        sql += ' AND c.client_id = ?'
        params.append(client_id)
    if assigned_to:
        sql += ' AND c.assigned_to = ?'
        params.append(assigned_to)

    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [_row_to_case(row) for row in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/cases/create')
def create_case(case: Case):
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            case_id = f'CASE-{str(uuid.uuid4())[:4].upper()}'
            cursor.execute(
                INSERT_CASE_SQL,
                (case_id, case.title, case.description, case.status,
                 case.client_id, case.assigned_to),
            )
            conn.commit()
        return {'case_id': case_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str):
    try:
        closed_at = datetime.now().isoformat() if new_status == 'closed' else None
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(UPDATE_STATUS_SQL, (new_status, closed_at, case_id))
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    init_db()
    uvicorn.run(app, host='0.0.0.0', port=8000)
