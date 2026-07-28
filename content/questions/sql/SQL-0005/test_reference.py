import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE updates(entity_id INTEGER NOT NULL, source_version INTEGER NOT NULL, received_at INTEGER NOT NULL, value TEXT NOT NULL);'
SEED = "INSERT INTO updates VALUES (1,1,5,'old'),(1,2,3,'newer-source'),(1,2,7,'latest'),(2,1,4,'only');"
EXPECTED = [[1, 2, 'latest'], [2, 1, 'only']]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
