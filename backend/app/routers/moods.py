from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.access import can_view_case, fetch_case
from app.auth import get_current_user
from app.db import get_connection
from app.schemas import MoodJournalOut, MoodUpsertRequest

router = APIRouter(prefix="/cases", tags=["moods"])


def _parse_entry_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entry_date must be YYYY-MM-DD",
        ) from exc
    today = date.today()
    if parsed > today + timedelta(days=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot write a future journal",
        )
    if parsed < today - timedelta(days=366):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date is too old",
        )
    return parsed.isoformat()


def _row_to_out(row: Any) -> MoodJournalOut:
    return MoodJournalOut(**dict(row))


@router.get("/{case_id}/moods", response_model=list[MoodJournalOut])
def list_moods(
    case_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[MoodJournalOut]:
    conn = get_connection()
    try:
        case = fetch_case(conn, case_id)
        if case is None or not can_view_case(case, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        rows = conn.execute(
            """
            SELECT
                journal_id, case_id, student_id, entry_date, mood, note,
                created_at, updated_at
            FROM mood_journals
            WHERE case_id = ?
            ORDER BY entry_date DESC
            LIMIT 60
            """,
            (case_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_out(r) for r in rows]


@router.put("/{case_id}/moods", response_model=MoodJournalOut)
def upsert_mood(
    case_id: int,
    body: MoodUpsertRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MoodJournalOut:
    entry_date = _parse_entry_date(body.entry_date)
    note = (body.note or "").strip() or None

    conn = get_connection()
    try:
        case = fetch_case(conn, case_id)
        if case is None or not can_view_case(case, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        if user["role"] != "Student" or user["user_id"] != case["student_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case Student can write a mood journal",
            )

        conn.execute(
            """
            INSERT INTO mood_journals (case_id, student_id, entry_date, mood, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(case_id, entry_date) DO UPDATE SET
                mood = excluded.mood,
                note = excluded.note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (case_id, user["user_id"], entry_date, body.mood, note),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT
                journal_id, case_id, student_id, entry_date, mood, note,
                created_at, updated_at
            FROM mood_journals
            WHERE case_id = ? AND entry_date = ?
            """,
            (case_id, entry_date),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save mood journal",
        )
    return _row_to_out(row)
