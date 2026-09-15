from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id


def test_assign_notifies_student_and_other_adult(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    parent = login(client, "parent001")
    case_id = primary_case_id(client, expert)

    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert),
        json={"tasks": [{"title": "通知測試任務"}]},
    )
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["tasks"][0]["task_id"]

    student_notifs = client.get(
        "/notifications",
        params={"unread_only": True},
        headers=auth_header(student),
    )
    assert student_notifs.status_code == 200
    s_items = student_notifs.json()
    assert any(
        n["task_id"] == task_id and n["type"] == "task_assigned" for n in s_items
    )

    parent_notifs = client.get(
        "/notifications",
        params={"unread_only": True},
        headers=auth_header(parent),
    )
    assert parent_notifs.status_code == 200
    assert any(
        n["task_id"] == task_id and n["type"] == "task_assigned"
        for n in parent_notifs.json()
    )

    expert_count = client.get(
        "/notifications/unread-count",
        headers=auth_header(expert),
    )
    assert expert_count.status_code == 200
    # Expert should not get notified for own assignment
    before_complete = expert_count.json()["count"]

    complete = client.post(
        f"/tasks/{task_id}/complete",
        headers=auth_header(student),
    )
    assert complete.status_code == 200

    parent_after = client.get(
        "/notifications",
        params={"unread_only": True},
        headers=auth_header(parent),
    )
    assert any(
        n["task_id"] == task_id and n["type"] == "task_completed"
        for n in parent_after.json()
    )

    expert_after = client.get(
        "/notifications/unread-count",
        headers=auth_header(expert),
    )
    assert expert_after.json()["count"] == before_complete + 1


def test_mark_notifications_read(client: TestClient) -> None:
    expert = login(client, "expert001")
    student = login(client, "student001")
    case_id = primary_case_id(client, expert)

    client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert),
        json={"tasks": [{"title": "已讀測試"}]},
    )

    count_before = client.get(
        "/notifications/unread-count",
        headers=auth_header(student),
    ).json()["count"]
    assert count_before >= 1

    mark = client.post(
        "/notifications/read",
        headers=auth_header(student),
        json={},
    )
    assert mark.status_code == 200
    assert mark.json()["updated"] >= 1

    count_after = client.get(
        "/notifications/unread-count",
        headers=auth_header(student),
    ).json()["count"]
    assert count_after == 0
