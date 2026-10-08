# tests/test_app.py – pytest tests for Employee Leave Management System
import os, tempfile, pytest

# Set DB_PATH BEFORE importing app – init_db() runs at import time
_fd, _db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DB_PATH"] = _db

from app import app
app.config["TESTING"] = True

@pytest.fixture
def client():
    with app.test_client() as c:
        yield c

def test_health_ok(client):                        # 1 – healthy DB → 200
    r = client.get("/health")
    assert r.status_code == 200 and r.json["status"] == "healthy"

def test_health_fail(client, monkeypatch):          # 2 – SIMULATE_FAILURE → 503
    monkeypatch.setenv("SIMULATE_FAILURE", "true")
    r = client.get("/health")
    assert r.status_code == 503

def test_login_success(client):                    # 3 – valid creds redirect
    r = client.post("/", data={"username": "asha", "password": "asha123"})
    assert r.status_code == 302

def test_login_fail(client):                       # 4 – bad password shows error
    r = client.post("/", data={"username": "asha", "password": "wrong"})
    assert b"Invalid" in r.data

def test_apply_leave(client):                      # 5 – leave saved (leave id=1)
    client.post("/", data={"username": "asha", "password": "asha123"})
    r = client.post("/apply", data={"type": "Sick Leave",
        "start_date": "2026-12-01", "end_date": "2026-12-02", "reason": "Fever"})
    assert r.status_code == 302

def test_manager_approve(client):                  # 6 – approve + balance drops
    # Vikram applies for 1 day → becomes leave id=2 (asha's is id=1)
    client.post("/", data={"username": "vikram", "password": "vikram123"})
    client.post("/apply", data={"type": "Casual Leave",
        "start_date": "2026-12-10", "end_date": "2026-12-10", "reason": "Personal"})
    # Manager sees both requests and approves vikram's (id=2)
    client.post("/", data={"username": "manager", "password": "manager123"})
    assert b"vikram" in client.get("/manager").data
    client.get("/action/2/approved")
    # Vikram used 1 approved day → balance = 20 - 1 = 19
    client.post("/", data={"username": "vikram", "password": "vikram123"})
    assert b"19 days" in client.get("/employee").data
