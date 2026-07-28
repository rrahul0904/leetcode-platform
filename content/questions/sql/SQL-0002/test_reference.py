import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE events(user_id INTEGER NOT NULL, event_time INTEGER NOT NULL, event_name TEXT NOT NULL);'
SEED = "INSERT INTO events VALUES (1,1,'view'),(1,2,'checkout'),(1,3,'pay'),(2,1,'view'),(2,3,'pay'),(3,2,'checkout');"
EXPECTED = [[2, 1, 1]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
