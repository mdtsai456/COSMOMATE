from __future__ import annotations

import sqlite3
from typing import Any, Iterable


def create_notification(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    notif_type: str,
    task_id: int,
    case_id: int,
    actor_id: int,
) -> None:
    if user_id == actor_id:
        return
    conn.execute(
        """
        INSERT INTO notifications (user_id, type, task_id, case_id, actor_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, notif_type, task_id, case_id, actor_id),
    )


def notify_task_assigned(
    conn: sqlite3.Connection,
    *,
    case: Any,
    task_ids: Iterable[int],
    actor_id: int,
    actor_role: str,
) -> None:
    recipients: list[int] = [int(case["student_id"])]
    if actor_role == "Expert":
        recipients.append(int(case["parent_id"]))
    elif actor_role == "Parent":
        recipients.append(int(case["expert_id"]))

    for task_id in task_ids:
        for user_id in recipients:
            create_notification(
                conn,
                user_id=user_id,
                notif_type="task_assigned",
                task_id=int(task_id),
                case_id=int(case["case_id"]),
                actor_id=actor_id,
            )


def notify_task_completed(
    conn: sqlite3.Connection,
    *,
    case_id: int,
    task_id: int,
    student_id: int,
    parent_id: int,
    expert_id: int,
) -> None:
    for user_id in (parent_id, expert_id):
        create_notification(
            conn,
            user_id=int(user_id),
            notif_type="task_completed",
            task_id=int(task_id),
            case_id=int(case_id),
            actor_id=int(student_id),
        )
