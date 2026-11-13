import os

os.environ.setdefault("BCRYPT_ROUNDS", "4")  # fast hashing in tests

from datetime import date  # noqa: E402

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import clock
from app.database import Base, get_db, make_engine
from app.main import app


class FakeClock:
    def __init__(self):
        self.value = date(2026, 1, 5)

    def __call__(self):
        return self.value


@pytest.fixture
def fake_today(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(clock, "today", fake)
    return fake


@pytest.fixture
def client():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, email, name="User", password="password123"):
    res = client.post("/auth/register", json={"email": email, "name": name, "password": password})
    assert res.status_code == 201, res.text
    token = client.post("/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"id": res.json()["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def alice(client):
    return register(client, "alice@example.com", "Alice")


@pytest.fixture
def bob(client):
    return register(client, "bob@example.com", "Bob")


@pytest.fixture
def team(client, alice):
    res = client.post("/teams", json={"name": "Web Team"}, headers=alice["headers"])
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def sprint(client, alice, team):
    res = client.post(
        f"/teams/{team['id']}/sprints",
        json={"name": "Sprint 1", "goal": "Launch MVP", "start_date": "2026-01-05", "end_date": "2026-01-09", "capacity": 20},
        headers=alice["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()
