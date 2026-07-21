import sqlite3
from pathlib import Path

DDL = 'CREATE TABLE teams(team_id INTEGER PRIMARY KEY, parent_team_id INTEGER, name TEXT NOT NULL);'
SEED = "INSERT INTO teams VALUES (1,NULL,'platform'),(2,1,'data'),(3,1,'runtime'),(4,2,'analytics'),(5,NULL,'sales');"
EXPECTED = [[1, 'platform', 0], [2, 'data', 1], [3, 'runtime', 1], [4, 'analytics', 2]]

def test_reference_query():
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
