import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE latency(service TEXT NOT NULL, sample_no INTEGER NOT NULL, milliseconds INTEGER NOT NULL);'
SEED = "INSERT INTO latency VALUES ('api',1,10),('api',2,20),('api',3,30),('api',4,50),('db',1,8);"
EXPECTED = [['api', 1, 10.0], ['api', 2, 15.0], ['api', 3, 20.0], ['api', 4, 33.33], ['db', 1, 8.0]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
