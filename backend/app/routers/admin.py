from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.db import get_connection
from app.schemas import AdminUserOut, CaseOut, Role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def list_all_users(
    _admin: Annotated[dict[str, Any], Depends(require_admin)],
    role: Annotated[Role | None, Query()] = None,
) -> list[AdminUserOut]:
    sql = """
        SELECT
            user_id,
            username,
            display_name,
            role,
            email,
            is_active,
            created_at
        FROM users
    """
    params: list[Any] = []
    if role is not None:
        sql += " WHERE role = ?"
        params.append(role)
    sql += " ORDER BY user_id ASC"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [AdminUserOut(**dict(r)) for r in rows]


@router.get("/cases", response_model=list[CaseOut])
def list_all_cases(
    _admin: Annotated[dict[str, Any], Depends(require_admin)],
) -> list[CaseOut]:
    conn = get_connection()
    try:
        rows = conn.execute(
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
            ORDER BY c.case_id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return [CaseOut(**dict(r)) for r in rows]
