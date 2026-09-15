from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, primary_case_id

MOODS = ("happy", "calm", "okay", "sad", "angry")


def test_student_can_upsert_mood_and_others_can_read(client: TestClient) -> None:
    student = login(client, "student001")
    parent = login(client, "parent001")
    expert = login(client, "expert001")
    case_id = primary_case_id(client, student)
    today = date.today().isoformat()

    created = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "happy", "note": "今天練習很順利", "entry_date": today},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["mood"] == "happy"
    assert body["note"] == "今天練習很順利"
    assert body["entry_date"] == today

    updated = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "calm", "note": "晚上比較平靜", "entry_date": today},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["mood"] == "calm"
    assert updated.json()["journal_id"] == body["journal_id"]

    listed = client.get(f"/cases/{case_id}/moods", headers=auth_header(parent))
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["mood"] == "calm"

    expert_list = client.get(f"/cases/{case_id}/moods", headers=auth_header(expert))
    assert expert_list.status_code == 200
    assert expert_list.json()[0]["note"] == "晚上比較平靜"


def test_parent_cannot_write_mood(client: TestClient) -> None:
    parent = login(client, "parent001")
    case_id = primary_case_id(client, parent)
    today = date.today().isoformat()
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(parent),
        json={"mood": "sad", "note": "nope", "entry_date": today},
    )
    assert resp.status_code == 403


def test_expert_cannot_write_mood(client: TestClient) -> None:
    expert = login(client, "expert001")
    case_id = primary_case_id(client, expert)
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(expert),
        json={"mood": "okay", "note": "nope", "entry_date": date.today().isoformat()},
    )
    assert resp.status_code == 403


def test_all_five_moods_accepted(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    start = date.today() - timedelta(days=4)
    for offset, mood in enumerate(MOODS):
        day = (start + timedelta(days=offset)).isoformat()
        resp = client.put(
            f"/cases/{case_id}/moods",
            headers=auth_header(student),
            json={"mood": mood, "note": f"mood-{mood}", "entry_date": day},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["mood"] == mood

    listed = client.get(f"/cases/{case_id}/moods", headers=auth_header(student))
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 5
    assert [r["mood"] for r in rows] == list(reversed(MOODS))


def test_mood_note_optional_and_stripped(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    today = date.today().isoformat()
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "okay", "note": "   ", "entry_date": today},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["note"] is None


def test_mood_note_too_long_rejected(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={
            "mood": "happy",
            "note": "x" * 81,
            "entry_date": date.today().isoformat(),
        },
    )
    assert resp.status_code == 422


def test_invalid_mood_rejected(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "excited", "note": "no", "entry_date": date.today().isoformat()},
    )
    assert resp.status_code == 422


def test_future_mood_date_rejected(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    future = (date.today() + timedelta(days=2)).isoformat()
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "happy", "note": "future", "entry_date": future},
    )
    assert resp.status_code == 400


def test_too_old_mood_date_rejected(client: TestClient) -> None:
    student = login(client, "student001")
    case_id = primary_case_id(client, student)
    old = (date.today() - timedelta(days=367)).isoformat()
    resp = client.put(
        f"/cases/{case_id}/moods",
        headers=auth_header(student),
        json={"mood": "sad", "note": "old", "entry_date": old},
    )
    assert resp.status_code == 400


def test_outsider_cannot_read_moods(client: TestClient) -> None:
    student = login(client, "student001")
    other = login(client, "student002")
    case_id = primary_case_id(client, student)
    resp = client.get(f"/cases/{case_id}/moods", headers=auth_header(other))
    assert resp.status_code == 404


def test_moods_require_login(client: TestClient) -> None:
    resp = client.get("/cases/1/moods")
    assert resp.status_code == 401
