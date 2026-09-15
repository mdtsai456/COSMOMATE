from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.access import can_view_case, fetch_case, fetch_tasks_for_case
from app.auth import get_current_user
from app.db import get_connection
from app.schemas import CaseCreateRequest, CaseOut, TaskOut

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
def list_cases(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[CaseOut]:
    role = user["role"]
    uid = user["user_id"]

    if role == "Expert":
        where = "c.expert_id = ?"
    elif role == "Parent":
        where = "c.parent_id = ?"
    elif role == "Student":
        where = "c.student_id = ?"
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown role")

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
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
            WHERE {where}
            ORDER BY c.case_id DESC
            """,
            (uid,),
        ).fetchall()
    finally:
        conn.close()

    return [CaseOut(**dict(r)) for r in rows]


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreateRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> CaseOut:
    if user["role"] != "Expert":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Expert can create a case",
        )

    conn = get_connection()
    try:
        student = conn.execute(
            """
            SELECT user_id, role, is_active FROM users WHERE user_id = ?
            """,
            (body.student_id,),
        ).fetchone()
        parent = conn.execute(
            """
            SELECT user_id, role, is_active FROM users WHERE user_id = ?
            """,
            (body.parent_id,),
        ).fetchone()

        if (
            student is None
            or not student["is_active"]
            or student["role"] != "Student"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id must be an active Student",
            )
        if parent is None or not parent["is_active"] or parent["role"] != "Parent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_id must be an active Parent",
            )

        existing = conn.execute(
            """
            SELECT case_id FROM cases
            WHERE student_id = ? AND parent_id = ?
            """,
            (body.student_id, body.parent_id),
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A case already exists for this student and parent",
            )

        link = conn.execute(
            """
            SELECT link_id FROM student_parent_links
            WHERE student_id = ? AND parent_id = ?
            """,
            (body.student_id, body.parent_id),
        ).fetchone()
        if link is None:
            conn.execute(
                """
                INSERT INTO student_parent_links (student_id, parent_id, relationship)
                VALUES (?, ?, ?)
                """,
                (body.student_id, body.parent_id, None),
            )

        case_name = (body.case_name or "").strip() or None
        try:
            cur = conn.execute(
                """
                INSERT INTO cases (case_name, student_id, parent_id, expert_id, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (case_name, body.student_id, body.parent_id, user["user_id"]),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A case already exists for this student and parent",
            ) from exc

        conn.commit()
        created = fetch_case(conn, int(cur.lastrowid))
    finally:
        conn.close()

    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created case",
        )
    return CaseOut(**dict(created))


@router.get("/{case_id}/tasks", response_model=list[TaskOut])
def list_case_tasks(
    case_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[TaskOut]:
    conn = get_connection()
    try:
        case = fetch_case(conn, case_id)
        if case is None or not can_view_case(case, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        rows = fetch_tasks_for_case(conn, case_id, user["user_id"])
    finally:
        conn.close()

    return [TaskOut(**dict(r)) for r in rows]


@router.delete("/{case_id}/tasks", status_code=status.HTTP_204_NO_CONTENT)
def clear_case_tasks(
    case_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> None:
    conn = get_connection()
    try:
        case = fetch_case(conn, case_id)
        if case is None or not can_view_case(case, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        if user["role"] != "Expert" or user["user_id"] != int(case["expert_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only this case's Expert can clear history",
            )
        conn.execute("DELETE FROM notifications WHERE case_id = ?", (case_id,))
        conn.execute(
            """
            DELETE FROM tasks
            WHERE assignment_id IN (
                SELECT assignment_id FROM task_assignments WHERE case_id = ?
            )
            """,
            (case_id,),
        )
        conn.execute("DELETE FROM task_assignments WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        conn.close()
