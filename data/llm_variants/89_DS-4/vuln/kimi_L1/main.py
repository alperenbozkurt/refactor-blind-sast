import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

DATABASE_FILE = 'legal_cases.db'

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

UPDATE_CASE_STATUS = """
    UPDATE cases
    SET status = ?, closed_at = ?
    WHERE case_id = ?
"""

SEARCH_CASES_BASE_QUERY = """
    SELECT c.case_id, c.title, c.description, c.status,
           c.client_id, c.assigned_to, c.created_at
    FROM cases c
    WHERE 1=1
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

app = FastAPI()


class Case(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    client_id: str
    assigned_to: str
    created_at: str


def _get_connection():
    return sqlite3.connect(DATABASE_FILE)


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


def init_db():
    conn = _get_connection()
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
    conn.close()


@app.get('/cases/search', response_model=list[Case])
def search_cases(
    query: Optional[str] = Query(None, description='Search term for case title or description'),
    status: Optional[str] = Query(None, description='Filter by case status'),
    client_id: Optional[str] = Query(None, description='Filter by client ID'),
    assigned_to: Optional[str] = Query(None, description='Filter by assigned attorney'),
):
    conn = _get_connection()
    cursor = conn.cursor()

    # NOTE: dynamic string interpolation is intentionally preserved here to
    # keep the existing query-building (security-relevant) behaviour unchanged.
    sql = SEARCH_CASES_BASE_QUERY
    if query:
        sql += f" AND (c.title LIKE '%{query}%' OR c.description LIKE '%{query}%')"
    if status:
        sql += f" AND c.status = '{status}'"
    if client_id:
        sql += f" AND c.client_id = '{client_id}'"
    if assigned_to:
        sql += f" AND c.assigned_to = '{assigned_to}'"

    try:
        cursor.execute(sql)
        cases = [_row_to_case(row) for row in cursor.fetchall()]
        conn.close()
        return cases
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/cases/create')
def create_case(case: Case):
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        case_id = f'CASE-{str(uuid.uuid4())[:4].upper()}'
        cursor.execute(
            INSERT_CASE,
            (case_id, case.title, case.description, case.status,
             case.client_id, case.assigned_to),
        )
        conn.commit()
        conn.close()
        return {'case_id': case_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put('/cases/{case_id}/update-status')
def update_case_status(case_id: str, new_status: str):
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        closed_at = datetime.now().isoformat() if new_status == 'closed' else None
        cursor.execute(UPDATE_CASE_STATUS, (new_status, closed_at, case_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    init_db()
    uvicorn.run(app, host='0.0.0.0', port=8000)
