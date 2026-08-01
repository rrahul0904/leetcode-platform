import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE users(
    user_id INTEGER PRIMARY KEY,
    cohort_week INTEGER NOT NULL,
    is_test BOOLEAN NOT NULL
);
CREATE TABLE activity(
    source_event_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    activity_week INTEGER NOT NULL,
    event_name TEXT NOT NULL
);
"""
SEED = """
INSERT INTO users VALUES
    (1,10,FALSE),(2,10,FALSE),(3,11,FALSE),
    (4,10,TRUE),(5,11,FALSE),(6,12,FALSE);
INSERT INTO activity VALUES
    ('e1',1,11,'session_started'),
    ('e1',1,11,'session_started'),
    ('e2',1,11,'session_started'),
    ('e3',2,12,'session_started'),
    ('e4',3,12,'session_started'),
    ('e5',5,12,'page_view'),
    ('e6',4,11,'session_started');
"""
EXPECTED = [[10, 2, 1], [11, 2, 1], [12, 1, 0]]


def test_reference_query() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(DDL + SEED)
    query = (Path(__file__).parent / "reference.sql").read_text()
    rows = [list(row) for row in connection.execute(query).fetchall()]
    assert rows == EXPECTED
