from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.routers.assignments import expand_recurring_dates
from tests.conftest import auth_header, login, primary_case_id


def test_expand_recurring_dates_spacing() -> None:
    start = date(2026, 8, 18)
    dates = expand_recurring_dates(start, times_per_week=3, weeks=2)
    assert dates == [
        start,
        start + timedelta(days=2),
        start + timedelta(days=4),
        start + timedelta(days=7),
        start + timedelta(days=9),
        start + timedelta(days=11),
    ]


def test_recurring_plan_creates_periodic_tasks(client: TestClient) -> None:
    expert = login(client, "expert001")
    case_id = primary_case_id(client, expert)
    resp = client.post(
        f"/cases/{case_id}/assignments",
        headers=auth_header(expert),
        json={
            "tasks": [{"title": "專注訓練", "content": "練習", "deadline": "2026-08-18"}],
            "recurring": {
                "daily_duration": "30分鐘",
                "times_per_week": 3,
                "weeks": 2,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    tasks = resp.json()["tasks"]
    assert len(tasks) == 6
    assert all(t["is_periodic"] == 1 for t in tasks)
    assert all(t["title"] == "專注訓練" for t in tasks)
    deadlines = sorted(t["deadline"] for t in tasks)
    assert deadlines[0].startswith("2026-08-18")
    assert len(set(deadlines)) == 6
    assert any("每次 30分鐘" in (t["content"] or "") for t in tasks)
    assert any("第 1/6 次" in (t["content"] or "") for t in tasks)
    assert all("一週" not in (t["content"] or "") for t in tasks)


def test_recurring_plan_in_frontend(client: TestClient) -> None:
    js = client.get("/app.js").text
    assert "週期性計畫" in js
    assert "一天多久" in js
    assert "has-periodic" in js
    css = client.get("/styles.css").text
    assert ".has-periodic" in css
    assert "#8ecae6" in css
