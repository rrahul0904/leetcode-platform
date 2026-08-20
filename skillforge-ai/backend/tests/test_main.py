from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_sql_runner_returns_seeded_result():
    response = client.post("/runner/sql", json={"query": "select carrier_id, count(*) as n from facts where status='completed' group by carrier_id order by carrier_id"})
    assert response.status_code == 200
    assert "carrier_id" in response.json()["output"]
    assert "101" in response.json()["output"]

def test_sql_runner_blocks_mutation():
    response = client.post("/runner/sql", json={"query": "delete from facts"})
    assert response.status_code == 400

def test_python_runner_executes_safe_code():
    response = client.post("/runner/python", json={"code": "print(sum([1,2,3]))", "stdin": ""})
    assert response.status_code == 200
    assert response.json()["output"].strip() == "6"
