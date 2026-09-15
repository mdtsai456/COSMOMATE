from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

    from app.db import init_db, get_connection
    from seed import ensure_demo_data, seed_if_empty

    init_db(str(db_path))
    conn = get_connection(str(db_path))
    try:
        seed_if_empty(conn)
        ensure_demo_data(conn)
    finally:
        conn.close()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str = "password123") -> str:
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def primary_case_id(client: TestClient, token: str) -> int:
    """Return Case-S001 when visible, otherwise the first listed case."""
    resp = client.get("/cases", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    cases = resp.json()
    assert len(cases) >= 1
    for case in cases:
        if case["case_name"] == "Case-S001":
            return int(case["case_id"])
    return int(cases[0]["case_id"])
