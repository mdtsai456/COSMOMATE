from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.db import get_connection
from app.schemas import (
    NotificationOut,
    NotificationsReadRequest,
    UnreadCountOut,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    unread_only: Annotated[bool, Query()] = False,
) -> list[NotificationOut]:
    sql = """
        SELECT
            n.notification_id,
            n.type,
            n.task_id,
            n.case_id,
            n.actor_id,
            a.display_name AS actor_name,
            a.role AS actor_role,
            t.title AS task_title,
            n.is_read,
            n.created_at
        FROM notifications n
        JOIN users a ON a.user_id = n.actor_id
        JOIN tasks t ON t.task_id = n.task_id
        WHERE n.user_id = ?
    """
    params: list[Any] = [user["user_id"]]
    if unread_only:
        sql += " AND n.is_read = 0"
    sql += " ORDER BY n.notification_id DESC LIMIT 100"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [NotificationOut(**dict(r)) for r in rows]


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> UnreadCountOut:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM notifications
            WHERE user_id = ? AND is_read = 0
            """,
            (user["user_id"],),
        ).fetchone()
    finally:
        conn.close()
    return UnreadCountOut(count=int(row["cnt"] if row else 0))


@router.post("/read")
def mark_notifications_read(
    body: NotificationsReadRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, int]:
    conn = get_connection()
    try:
        if body.ids:
            placeholders = ",".join("?" for _ in body.ids)
            cur = conn.execute(
                f"""
                UPDATE notifications
                SET is_read = 1
                WHERE user_id = ?
                  AND is_read = 0
                  AND notification_id IN ({placeholders})
                """,
                (user["user_id"], *body.ids),
            )
        else:
            cur = conn.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE user_id = ? AND is_read = 0
                """,
                (user["user_id"],),
            )
        conn.commit()
        updated = cur.rowcount
    finally:
        conn.close()
    return {"updated": int(updated)}
