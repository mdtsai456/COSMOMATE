from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id


def _create_task(client: TestClient, token: str, case_id: int, title: str = "留言任務") -> int:
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(token),
        json={"tasks": [{"title": title}]},
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["tasks"][0]["task_id"])


def _complete(client: TestClient, student_token: str, task_id: int) -> None:
    resp = client.post(
        f"/tasks/{task_id}/complete",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200, resp.text


def test_expert_parent_comment_and_reply_student_read_only(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    student = login(client, "student001")
    case_id = primary_case_id(client, expert)
    task_id = _create_task(client, expert, case_id)
    _complete(client, student, task_id)

    created = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(expert),
        json={"content": "完成得很好"},
    )
    assert created.status_code == 201, created.text
    comment_id = created.json()["comment_id"]
    assert created.json()["author_role"] == "Expert"
    assert created.json()["parent_comment_id"] is None

    reply = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(parent),
        json={"content": "謝謝老師", "parent_comment_id": comment_id},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["author_role"] == "Parent"
    assert reply.json()["parent_comment_id"] == comment_id

    nested = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(expert),
        json={"content": "不可再回覆回覆", "parent_comment_id": reply.json()["comment_id"]},
    )
    assert nested.status_code == 400

    student_post = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(student),
        json={"content": "學生想留言"},
    )
    assert student_post.status_code == 403

    thread = client.get(
        f"/tasks/{task_id}/comments",
        headers=auth_header(student),
    )
    assert thread.status_code == 200
    body = thread.json()
    assert len(body) == 1
    assert body[0]["content"] == "完成得很好"
    assert len(body[0]["replies"]) == 1
    assert body[0]["replies"][0]["content"] == "謝謝老師"


def test_can_comment_on_open_task(client: TestClient) -> None:
    expert = login(client, "expert001")
    case_id = primary_case_id(client, expert)
    task_id = _create_task(client, expert, case_id, "未完成也可留言")
    resp = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(expert),
        json={"content": "先提醒一下"},
    )
    assert resp.status_code == 201, resp.text
    listed = client.get(f"/cases/{case_id}/tasks", headers=auth_header(expert))
    assert listed.status_code == 200
    task = next(t for t in listed.json() if t["task_id"] == task_id)
    assert task["comment_count"] == 1
    assert task["unread_comment_count"] == 0


def test_unread_clears_after_viewing_comments(client: TestClient) -> None:
    expert = login(client, "expert001")
    parent = login(client, "parent001")
    case_id = primary_case_id(client, expert)
    task_id = _create_task(client, expert, case_id, "未讀留言")

    created = client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(expert),
        json={"content": "請家長看一下"},
    )
    assert created.status_code == 201, created.text

    before = client.get(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    task = next(t for t in before.json() if t["task_id"] == task_id)
    assert task["comment_count"] == 1
    assert task["unread_comment_count"] == 1

    viewed = client.get(f"/tasks/{task_id}/comments", headers=auth_header(parent))
    assert viewed.status_code == 200

    after = client.get(f"/cases/{case_id}/tasks", headers=auth_header(parent))
    task = next(t for t in after.json() if t["task_id"] == task_id)
    assert task["comment_count"] == 1
    assert task["unread_comment_count"] == 0


def test_outsider_cannot_see_comments(client: TestClient) -> None:
    expert = login(client, "expert001")
    other = login(client, "expert002")
    student = login(client, "student001")
    case_id = primary_case_id(client, expert)
    task_id = _create_task(client, expert, case_id)
    _complete(client, student, task_id)
    client.post(
        f"/tasks/{task_id}/comments",
        headers=auth_header(expert),
        json={"content": "內部留言"},
    )
    hidden = client.get(
        f"/tasks/{task_id}/comments",
        headers=auth_header(other),
    )
    assert hidden.status_code == 404


def test_comment_button_in_frontend(client: TestClient) -> None:
    js = client.get("/app.js").text
    assert 'data-comments="' in js
    assert "task-comment-icon" in js
    assert "task-comment-badge" in js
    assert "task-comments" in js
    assert "僅供閱讀，無法留言或回覆。" in js
    css = client.get("/styles.css").text
    assert ".task-comment-icon" in css
    assert ".task-comment-badge" in css
    assert ".task-comments" in css
    assert ".comment-replies" in css
