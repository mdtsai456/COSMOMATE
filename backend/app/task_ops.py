from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException, status

from app.access import TASK_OUT_SELECT, fetch_task_with_case, is_case_member


def require_case_assigner(row: sqlite3.Row, user: dict[str, Any]) -> None:
    """404 if not a member; 403 unless caller is the original assigned_by."""
    case_like = {
        "student_id": row["student_id"],
        "parent_id": row["parent_id"],
        "expert_id": row["expert_id"],
    }
    if not is_case_member(case_like, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if user["user_id"] != row["assigned_by"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the original assigner can modify this task",
        )


def fetch_task_out(
    conn: sqlite3.Connection, task_id: int, user_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        TASK_OUT_SELECT + " WHERE t.task_id = ?",
        (user_id, user_id, task_id),
    ).fetchone()


def mark_comments_read(conn: sqlite3.Connection, task_id: int, user_id: int) -> None:
    conn.execute(
        """
        INSERT INTO task_comment_reads (user_id, task_id, last_read_comment_id)
        SELECT ?, ?, COALESCE(MAX(comment_id), 0)
        FROM task_comments
        WHERE task_id = ?
        ON CONFLICT(user_id, task_id) DO UPDATE SET
            last_read_comment_id = excluded.last_read_comment_id
        """,
        (user_id, task_id, task_id),
    )


def get_task_row_or_404(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    row = fetch_task_with_case(conn, task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return row
