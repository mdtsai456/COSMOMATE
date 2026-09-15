from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id


def _case_id(client: TestClient, token: str) -> int:
    return primary_case_id(client, token)


def _create_task(
    client: TestClient,
    token: str,
    case_id: int,
    title: str = "新任務",
) -> int:
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(token),
        json={"tasks": [{"title": title, "content": "內容", "deadline": "2026-08-30 12:00:00"}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["tasks"][0]["task_id"]


# ---------- 查 (Read) ----------


def test_expert_list_cases(client: TestClient) -> None:
    token = login(client, "expert001")
    resp = client.get("/cases", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    names = {c["case_name"] for c in body}
    assert names == {"Case-S001", "Case-S002"}
    assert all(c["expert_name"] for c in body)
    assert all(c["status"] == "active" for c in body)


def test_parent_list_cases(client: TestClient) -> None:
    token = login(client, "parent001")
    resp = client.get("/cases", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["parent_name"]


def test_expert_list_tasks_empty_then_with_data(client: TestClient) -> None:
    token = login(client, "expert001")
    case_id = _case_id(client, token)

    empty = client.get(f"/cases/{case_id}/tasks", headers=auth_header(token))
    assert empty.status_code == 200
    assert empty.json() == []

    _create_task(client, token, case_id, "Expert 任務")
    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["title"] == "Expert 任務"
    assert listed.json()[0]["assigned_by_role"] == "Expert"


def test_parent_list_tasks_after_expert_assign(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = _case_id(client, expert)
    task_id = _create_task(client, expert, case_id, "給 Parent 看")

    resp = client.get(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    assert resp.status_code == 200
    assert resp.json()[0]["task_id"] == task_id


# ---------- 增 (Create) ----------


def test_expert_create_multi_tasks(client: TestClient) -> None:
    token = login(client, "expert001")
    case_id = _case_id(client, token)
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(token),
        json={
            "tasks": [
                {"title": "任務 A"},
                {"title": "任務 B", "content": "B 內容"},
                {"title": "任務 C", "deadline": "2026-09-01 09:00:00"},
            ]
        },
    )
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert len(tasks) == 3
    assert {t["title"] for t in tasks} == {"任務 A", "任務 B", "任務 C"}
    assert [t["title"] for t in tasks] == ["任務 C", "任務 B", "任務 A"]


def test_parent_create_assignment(client: TestClient) -> None:
    token = login(client, "parent001")
    case_id = _case_id(client, token)
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(token),
        json={"tasks": [{"title": "Contract 派發"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["tasks"][0]["assigned_by_role"] == "Parent"


def test_create_assignment_empty_tasks_422(client: TestClient) -> None:
    token = login(client, "expert001")
    case_id = _case_id(client, token)
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(token),
        json={"tasks": []},
    )
    assert resp.status_code == 422


# ---------- 改 (Update) ----------


def test_expert_update_task(client: TestClient) -> None:
    token = login(client, "expert001")
    case_id = _case_id(client, token)
    task_id = _create_task(client, token, case_id, "舊標題")

    resp = client.patch(
        f"/tasks/{task_id}",
        headers=auth_header(token),
        json={"title": "新標題", "content": "已更新"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新標題"
    assert resp.json()["content"] == "已更新"

    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(token))
    assert listed.json()[0]["title"] == "新標題"


def test_parent_update_task(client: TestClient) -> None:
    parent = login(client, "parent001")
    case_id = _case_id(client, parent)
    task_id = _create_task(client, parent, case_id, "Parent 原標題")

    resp = client.patch(
        f"/tasks/{task_id}",
        headers=auth_header(parent),
        json={"deadline": "2026-10-01 18:00:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["deadline"] == "2026-10-01 18:00:00"


def test_student_cannot_update_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    case_id = _case_id(client, expert)
    task_id = _create_task(client, expert, case_id)

    resp = client.patch(
        f"/tasks/{task_id}",
        headers=auth_header(student),
        json={"title": "學生亂改"},
    )
    assert resp.status_code == 403


def test_parent_cannot_update_expert_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = _case_id(client, expert)
    task_id = _create_task(client, expert, case_id, "Expert 派的")

    resp = client.patch(
        f"/tasks/{task_id}",
        headers=auth_header(parent),
        json={"title": "Parent 想改"},
    )
    assert resp.status_code == 403


def test_expert_cannot_delete_parent_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = _case_id(client, parent)
    task_id = _create_task(client, parent, case_id, "Parent 派的")

    resp = client.delete(f"/tasks/{task_id}", headers=auth_header(expert))
    assert resp.status_code == 403


def test_cannot_update_completed_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    case_id = _case_id(client, expert)
    task_id = _create_task(client, expert, case_id)
    assert (
        client.post(f"/tasks/{task_id}/complete", headers=auth_header(student)).status_code
        == 200
    )

    resp = client.patch(
        f"/tasks/{task_id}",
        headers=auth_header(expert),
        json={"title": "想改已完成"},
    )
    assert resp.status_code == 409


def test_update_unknown_task_404(client: TestClient) -> None:
    token = login(client, "expert001")
    resp = client.patch(
        "/tasks/99999",
        headers=auth_header(token),
        json={"title": "不存在"},
    )
    assert resp.status_code == 404


# ---------- 刪 (Delete) ----------


def test_expert_delete_task(client: TestClient) -> None:
    token = login(client, "expert001")
    case_id = _case_id(client, token)
    task_id = _create_task(client, token, case_id, "待刪除")

    resp = client.delete(f"/tasks/{task_id}", headers=auth_header(token))
    assert resp.status_code == 204

    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(token))
    assert listed.json() == []


def test_parent_delete_task(client: TestClient) -> None:
    parent = login(client, "parent001")
    case_id = _case_id(client, parent)
    task_id = _create_task(client, parent, case_id, "Parent 刪")

    resp = client.delete(f"/tasks/{task_id}", headers=auth_header(parent))
    assert resp.status_code == 204

    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    assert all(t["task_id"] != task_id for t in listed.json())


def test_student_cannot_delete_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    case_id = _case_id(client, expert)
    task_id = _create_task(client, expert, case_id)

    resp = client.delete(f"/tasks/{task_id}", headers=auth_header(student))
    assert resp.status_code == 403


def test_delete_unknown_task_404(client: TestClient) -> None:
    token = login(client, "parent001")
    resp = client.delete("/tasks/99999", headers=auth_header(token))
    assert resp.status_code == 404


def test_expert_can_clear_case_history(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = _case_id(client, expert)
    _create_task(client, expert, case_id, "專家歷史")
    _create_task(client, parent, case_id, "家長歷史")

    resp = client.delete(f"/cases/{case_id}/tasks", headers=auth_header(expert))
    assert resp.status_code == 204, resp.text

    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(expert))
    assert listed.status_code == 200
    assert listed.json() == []


def test_parent_cannot_clear_case_history(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = _case_id(client, parent)
    _create_task(client, expert, case_id, "不可清空")

    resp = client.delete(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    assert resp.status_code == 403

    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    assert len(listed.json()) >= 1


def test_student_cannot_clear_case_history(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    case_id = _case_id(client, expert)
    _create_task(client, expert, case_id, "學生不可清空")

    resp = client.delete(f"/cases/{case_id}/tasks", headers=auth_header(student))
    assert resp.status_code == 403
