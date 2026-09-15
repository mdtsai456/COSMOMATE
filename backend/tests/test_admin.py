from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login


def test_admin_lists_all_users(client: TestClient) -> None:
    token = login(client, "admin001")
    resp = client.get("/admin/users", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    users = resp.json()
    usernames = {u["username"] for u in users}
    assert {
        "admin001",
        "expert001",
        "expert002",
        "parent001",
        "student001",
    } <= usernames
    admin = next(u for u in users if u["username"] == "admin001")
    assert admin["role"] == "Admin"
    assert "email" in admin
    assert "is_active" in admin
    assert "created_at" in admin
    assert "password_hash" not in admin


def test_admin_filter_users_by_role(client: TestClient) -> None:
    token = login(client, "admin001")
    resp = client.get(
        "/admin/users",
        params={"role": "Expert"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    users = resp.json()
    assert users
    assert all(u["role"] == "Expert" for u in users)


def test_admin_lists_all_cases_with_relationships(client: TestClient) -> None:
    token = login(client, "admin001")
    resp = client.get("/admin/cases", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    cases = resp.json()
    assert len(cases) >= 3
    by_name = {c["case_name"]: c for c in cases}
    assert {"Case-S001", "Case-S002", "Case-S003"} <= set(by_name)

    expert_cases = [c for c in cases if c["case_name"] in ("Case-S001", "Case-S002")]
    assert len(expert_cases) == 2
    assert expert_cases[0]["expert_id"] == expert_cases[1]["expert_id"]

    case = by_name["Case-S001"]
    assert case["expert_id"]
    assert case["expert_name"]
    assert case["student_id"]
    assert case["student_name"]
    assert case["parent_id"]
    assert case["parent_name"]


def test_non_admin_forbidden_on_admin_endpoints(client: TestClient) -> None:
    token = login(client, "expert001")
    for path in ("/admin/users", "/admin/cases"):
        resp = client.get(path, headers=auth_header(token))
        assert resp.status_code == 403, (path, resp.text)
