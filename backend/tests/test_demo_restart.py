from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app
from tests.conftest import auth_header, login, primary_case_id


@pytest.mark.parametrize("change", ["rename", "delete"])
def test_restart_preserves_edited_demo_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "persistent.db"))
    # Exercise the demo timeline that is normally skipped in test fixtures.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with TestClient(app) as client:
        parent = login(client, "parent001")
        case_id = primary_case_id(client, parent)
        assigned = client.post(
            f"/cases/{case_id}/assignments",
            headers=auth_header(parent),
            json={"tasks": [{"title": "家長自訂任務"}]},
        )
        assert assigned.status_code == 200, assigned.text
        task_id = assigned.json()["tasks"][0]["task_id"]

    with closing(get_connection()) as conn:
        title = "穩定作息練習"
        if change == "rename":
            changed = conn.execute("UPDATE tasks SET title = ? WHERE title = ?", ("新名稱", title))
        else:
            changed = conn.execute("DELETE FROM tasks WHERE title = ?", (title,))
        assert changed.rowcount == 1
        conn.commit()
        tasks = conn.execute("SELECT * FROM tasks ORDER BY task_id").fetchall()
        notifications = conn.execute("SELECT * FROM notifications ORDER BY notification_id").fetchall()
        assert any(row["task_id"] == task_id for row in notifications)

    # A new lifespan opens the same on-disk database, as on a Railway redeploy.
    with TestClient(app), closing(get_connection()) as conn:
        assert conn.execute("SELECT * FROM tasks ORDER BY task_id").fetchall() == tasks
        assert conn.execute("SELECT * FROM notifications ORDER BY notification_id").fetchall() == notifications
