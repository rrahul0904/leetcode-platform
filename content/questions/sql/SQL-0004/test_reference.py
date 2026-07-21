import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE events(user_id INTEGER NOT NULL, minute INTEGER NOT NULL);'
SEED = 'INSERT INTO events VALUES (1,0),(1,10),(1,50),(1,55),(2,4);'
EXPECTED = [[1, 1, 0, 10], [1, 2, 50, 55], [2, 1, 4, 4]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
