import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE users(user_id INTEGER PRIMARY KEY, cohort_week INTEGER NOT NULL); CREATE TABLE activity(user_id INTEGER NOT NULL, activity_week INTEGER NOT NULL);'
SEED = 'INSERT INTO users VALUES (1,10),(2,10),(3,11); INSERT INTO activity VALUES (1,11),(1,12),(3,12);'
EXPECTED = [[10, 2, 1], [11, 1, 1]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
