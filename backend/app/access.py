from __future__ import annotations

import sqlite3
from typing import Any, Mapping


def fetch_case(conn: sqlite3.Connection, case_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            c.case_id,
            c.case_name,
            c.status,
            c.student_id,
            s.display_name AS student_name,
            c.parent_id,
            p.display_name AS parent_name,
            c.expert_id,
            e.display_name AS expert_name,
            c.created_at,
            c.updated_at
        FROM cases c
        JOIN users s ON s.user_id = c.student_id
        JOIN users p ON p.user_id = c.parent_id
        JOIN users e ON e.user_id = c.expert_id
        WHERE c.case_id = ?
        """,
        (case_id,),
    ).fetchone()


def is_case_member(case: Mapping[str, Any], user: dict[str, Any]) -> bool:
    uid = user["user_id"]
    return uid in (case["student_id"], case["parent_id"], case["expert_id"])


def can_view_case(case: Mapping[str, Any], user: dict[str, Any]) -> bool:
    role = user["role"]
    uid = user["user_id"]
    if role == "Student":
        return case["student_id"] == uid
    if role == "Parent":
        return case["parent_id"] == uid
    if role == "Expert":
        return case["expert_id"] == uid
    return False


TASK_OUT_SELECT = """
        SELECT
            t.task_id,
            ta.assignment_id,
            t.title,
            t.content,
            t.deadline,
            t.is_done,
            t.completed_at,
            ta.assigned_by,
            a.display_name AS assigned_by_name,
            a.role AS assigned_by_role,
            ta.created_at AS assigned_at,
            t.created_at,
            t.updated_at,
            t.is_periodic,
            (SELECT COUNT(*) FROM task_comments tc WHERE tc.task_id = t.task_id) AS comment_count,
            (
                SELECT COUNT(*)
                FROM task_comments tc
                WHERE tc.task_id = t.task_id
                  AND tc.author_id != ?
                  AND tc.comment_id > COALESCE(
                    (
                        SELECT r.last_read_comment_id
                        FROM task_comment_reads r
                        WHERE r.user_id = ? AND r.task_id = t.task_id
                    ),
                    0
                  )
            ) AS unread_comment_count
        FROM tasks t
        JOIN task_assignments ta ON ta.assignment_id = t.assignment_id
        JOIN users a ON a.user_id = ta.assigned_by
"""


def fetch_tasks_for_case(
    conn: sqlite3.Connection, case_id: int, user_id: int
) -> list[sqlite3.Row]:
    return conn.execute(
        TASK_OUT_SELECT + " WHERE ta.case_id = ? ORDER BY t.task_id DESC",
        (user_id, user_id, case_id),
    ).fetchall()


def fetch_task_with_case(
    conn: sqlite3.Connection, task_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            t.task_id,
            t.assignment_id,
            t.completed_at,
            ta.case_id,
            ta.assigned_by,
            c.student_id,
            c.parent_id,
            c.expert_id,
            c.status AS case_status
        FROM tasks t
        JOIN task_assignments ta ON ta.assignment_id = t.assignment_id
        JOIN cases c ON c.case_id = ta.case_id
        WHERE t.task_id = ?
        """,
        (task_id,),
    ).fetchone()
