import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE identities(identity_id INTEGER PRIMARY KEY, normalized_email TEXT NOT NULL, verified INTEGER NOT NULL, updated_at INTEGER NOT NULL);'
SEED = "INSERT INTO identities VALUES (1,'a@example.com',0,9),(2,'a@example.com',1,5),(3,'b@example.com',1,3),(4,'b@example.com',1,7);"
EXPECTED = [['a@example.com', 2], ['b@example.com', 4]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
