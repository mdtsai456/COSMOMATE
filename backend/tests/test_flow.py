from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id


def test_login_success(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"username": "expert001", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "Expert"
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_bad_password(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"username": "expert001", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/me")
    assert resp.status_code == 401


def test_me_ok(client: TestClient) -> None:
    token = login(client, "parent001")
    resp = client.get("/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["username"] == "parent001"
    assert resp.json()["role"] == "Parent"


def test_full_assign_execute_flow(client: TestClient) -> None:
    expert_token = login(client, "expert001")
    parent_token = login(client, "parent001")
    student_token = login(client, "student001")

    cases = client.get("/cases", headers=auth_header(expert_token))
    assert cases.status_code == 200
    assert len(cases.json()) == 2
    case_id = primary_case_id(client, expert_token)

    assign = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert_token),
        json={
            "tasks": [
                {
                    "title": "專注力訓練",
                    "content": "完成今日 20 分鐘訓練",
                    "deadline": "2026-08-20 18:00:00",
                }
            ]
        },
    )
    assert assign.status_code == 200, assign.text
    task_id = assign.json()["tasks"][0]["task_id"]
    assert assign.json()["tasks"][0]["is_done"] == 0

    student_tasks = client.get(
        f"/cases/{case_id}/tasks",
        headers=auth_header(student_token),
    )
    assert student_tasks.status_code == 200
    assert len(student_tasks.json()) == 1
    assert student_tasks.json()[0]["task_id"] == task_id

    complete = client.post(
        f"/tasks/{task_id}/complete",
        headers=auth_header(student_token),
    )
    assert complete.status_code == 200
    assert complete.json()["is_done"] == 1
    assert complete.json()["completed_at"] is not None

    parent_tasks = client.get(
        f"/cases/{case_id}/tasks",
        headers=auth_header(parent_token),
    )
    assert parent_tasks.status_code == 200
    assert parent_tasks.json()[0]["is_done"] == 1
    assert parent_tasks.json()[0]["completed_at"] is not None


def test_student_cannot_assign(client: TestClient) -> None:
    student_token = login(client, "student001")
    case_id = client.get("/cases", headers=auth_header(student_token)).json()[0]["case_id"]
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(student_token),
        json={"tasks": [{"title": "x"}]},
    )
    assert resp.status_code == 403


def test_unknown_case_404(client: TestClient) -> None:
    token = login(client, "expert001")
    resp = client.get("/cases/99999/tasks", headers=auth_header(token))
    assert resp.status_code == 404


def test_parent_cannot_complete(client: TestClient) -> None:
    expert_token = login(client, "expert001")
    parent_token = login(client, "parent001")
    case_id = primary_case_id(client, expert_token)
    assign = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert_token),
        json={"tasks": [{"title": "量表"}]},
    )
    task_id = assign.json()["tasks"][0]["task_id"]
    resp = client.post(f"/tasks/{task_id}/complete", headers=auth_header(parent_token))
    assert resp.status_code == 403


def test_duplicate_complete_409(client: TestClient) -> None:
    expert_token = login(client, "expert001")
    student_token = login(client, "student001")
    case_id = primary_case_id(client, expert_token)
    assign = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert_token),
        json={"tasks": [{"title": "影片"}]},
    )
    task_id = assign.json()["tasks"][0]["task_id"]
    first = client.post(f"/tasks/{task_id}/complete", headers=auth_header(student_token))
    assert first.status_code == 200
    second = client.post(f"/tasks/{task_id}/complete", headers=auth_header(student_token))
    assert second.status_code == 409


def test_parent_can_assign_contract(client: TestClient) -> None:
    parent_token = login(client, "parent001")
    case_id = client.get("/cases", headers=auth_header(parent_token)).json()[0]["case_id"]
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(parent_token),
        json={"tasks": [{"title": "Contract 任務"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["tasks"][0]["assigned_by_role"] == "Parent"
