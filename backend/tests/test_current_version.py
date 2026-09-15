from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id

MOODS = ("happy", "calm", "okay", "sad", "angry")


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_frontend_shell_served(client: TestClient) -> None:
    index = client.get("/")
    assert index.status_code == 200
    html = index.text
    assert "/styles.css" in html
    assert "/app.js" in html
    assert "/landing/css/style.css" in html
    assert "/landing/js/main.js" in html

    landing_css = client.get("/landing/css/style.css")
    assert landing_css.status_code == 200
    assert "--bg-center" in landing_css.text

    redirected = client.get("/app", follow_redirects=False)
    assert redirected.status_code == 307
    assert redirected.headers.get("location") == "/"

    css = client.get("/styles.css")
    assert css.status_code == 200
    assert ".progress-bar" in css.text
    assert ".stat-card--mood" in css.text
    assert ".student-level-label" in css.text
    assert "/fonts/SweiGothicCJKtc-Regular.woff2" in css.text

    font = client.get("/fonts/SweiGothicCJKtc-Regular.woff2")
    assert font.status_code == 200
    assert font.content[:4] == b"wOF2"

    js = client.get("/app.js")
    assert js.status_code == 200
    assert "心情札記" in js.text
    assert "student-level-label" in js.text
    assert "renderIntro" in js.text
    assert "intro-login" in js.text


def test_custom_mood_images_served(client: TestClient) -> None:
    png_sig = b"\x89PNG\r\n\x1a\n"
    for mood in MOODS:
        resp = client.get(f"/img/mood-{mood}.png")
        assert resp.status_code == 200, mood
        assert resp.content.startswith(png_sig)
        assert len(resp.content) > 100


def test_task_avatar_images_served(client: TestClient) -> None:
    jpg_sig = b"\xff\xd8\xff"
    for i in range(1, 10):
        resp = client.get(f"/img/task{i}.jpg")
        assert resp.status_code == 200, i
        assert resp.content.startswith(jpg_sig)
        assert len(resp.content) > 100

    js = client.get("/app.js").text
    assert "taskAvatarSrc" in js
    assert "task1.jpg" in js


def test_calendar_days_are_not_clickable(client: TestClient) -> None:
    js = client.get("/app.js").text
    assert '<div class="cal-day' in js
    assert "data-day=" not in js
    assert "querySelectorAll(\"[data-day]\")" not in js


def test_mood_pick_and_save_do_not_rerender_page(client: TestClient) -> None:
    js = client.get("/app.js").text
    assert 'el.classList.toggle("active", on)' in js
    assert "paintMoodWeek();" in js
    assert 'return `/img/mood-${id}.png`' in js
    save_block = js.split('getElementById("mood-save")')[1].split("const openAssign")[0]
    assert "renderApp()" not in save_block


def test_student_current_dashboard_flow(client: TestClient) -> None:
    student = login(client, "student001")
    me = client.get("/me", headers=auth_header(student))
    assert me.status_code == 200
    assert me.json()["role"] == "Student"
    assert me.json()["display_name"] == "學生 A"

    case_id = primary_case_id(client, student)
    empty = client.get(f"/cases/{case_id}/moods", headers=auth_header(student))
    assert empty.status_code == 200
    assert empty.json() == []

    tasks = client.get(f"/cases/{case_id}/tasks", headers=auth_header(student))
    assert tasks.status_code == 200

    today = date.today().isoformat()
    saved = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "happy", "note": "今天還不錯", "entry_date": today},
    )
    assert saved.status_code == 200, saved.text
    listed = client.get(f"/cases/{case_id}/moods", headers=auth_header(student))
    assert listed.json()[0]["mood"] == "happy"
    assert listed.json()[0]["note"] == "今天還不錯"
