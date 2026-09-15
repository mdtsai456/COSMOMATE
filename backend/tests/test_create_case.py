from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login


def test_expert_lists_students_and_parents(client: TestClient) -> None:
    expert = login(client, "expert001")
    students = client.get("/users", params={"role": "Student"}, headers=auth_header(expert))
    parents = client.get("/users", params={"role": "Parent"}, headers=auth_header(expert))
    assert students.status_code == 200
    assert parents.status_code == 200
    assert {u["username"] for u in students.json()} >= {"student001", "student002"}
    assert {u["username"] for u in parents.json()} >= {"parent001", "parent002"}


def test_student_cannot_list_users(client: TestClient) -> None:
    student = login(client, "student001")
    resp = client.get("/users", params={"role": "Student"}, headers=auth_header(student))
    assert resp.status_code == 403


def test_expert_creates_case_binding_parent_and_student(client: TestClient) -> None:
    expert = login(client, "expert001")
    users = client.get("/users", params={"role": "Student"}, headers=auth_header(expert)).json()
    parents = client.get("/users", params={"role": "Parent"}, headers=auth_header(expert)).json()
    student = next(u for u in users if u["username"] == "student003")
    parent = next(u for u in parents if u["username"] == "parent001")

    resp = client.post(
        "/cases",
        headers=auth_header(expert),
        json={
            "student_id": student["user_id"],
            "parent_id": parent["user_id"],
            "case_name": "Case-new",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_name"] == "Case-new"
    assert body["student_id"] == student["user_id"]
    assert body["parent_id"] == parent["user_id"]
    assert body["expert_name"]

    listed = client.get("/cases", headers=auth_header(expert))
    assert any(c["case_id"] == body["case_id"] for c in listed.json())

    dup = client.post(
        "/cases",
        headers=auth_header(expert),
        json={
            "student_id": student["user_id"],
            "parent_id": parent["user_id"],
            "case_name": "dup",
        },
    )
    assert dup.status_code == 409


def test_parent_cannot_create_case(client: TestClient) -> None:
    parent = login(client, "parent001")
    resp = client.post(
        "/cases",
        headers=auth_header(parent),
        json={"student_id": 1, "parent_id": 1},
    )
    assert resp.status_code == 403
