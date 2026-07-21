import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE assignments(user_id INTEGER PRIMARY KEY, variant TEXT NOT NULL); CREATE TABLE conversions(user_id INTEGER NOT NULL, conversion_id INTEGER NOT NULL);'
SEED = "INSERT INTO assignments VALUES (1,'A'),(2,'A'),(3,'B'); INSERT INTO conversions VALUES (1,10),(1,11),(3,12);"
EXPECTED = [['A', 2, 1], ['B', 1, 1]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
