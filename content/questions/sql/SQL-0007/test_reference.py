import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE inventory_events(sku TEXT NOT NULL, event_sequence INTEGER NOT NULL, quantity INTEGER NOT NULL);'
SEED = "INSERT INTO inventory_events VALUES ('a',1,4),('a',3,8),('a',5,1),('b',2,7);"
EXPECTED = [['a', 8, 3], ['b', 7, 2]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
