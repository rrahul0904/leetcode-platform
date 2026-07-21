import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE postings(account_id INTEGER NOT NULL, sequence_no INTEGER NOT NULL, amount INTEGER NOT NULL);'
SEED = 'INSERT INTO postings VALUES (1,1,100),(1,2,-30),(1,3,5),(2,1,20),(2,2,-5);'
EXPECTED = [[1, 1, 100, 100], [1, 2, -30, 70], [1, 3, 5, 75], [2, 1, 20, 20], [2, 2, -5, 15]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
