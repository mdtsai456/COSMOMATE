from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.access import can_view_case, is_case_member
from app.auth import get_current_user
from app.db import get_connection
from app.notifications import notify_task_completed
from app.schemas import CommentCreateRequest, CommentOut, TaskOut, TaskUpdateRequest
from app.task_ops import (
    fetch_task_out,
    get_task_row_or_404,
    mark_comments_read,
    require_case_assigner,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    body: TaskUpdateRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> TaskOut:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    conn = get_connection()
    try:
        row = get_task_row_or_404(conn, task_id)
        require_case_assigner(row, user)

        if row["completed_at"] is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update a completed task",
            )

        fields: list[str] = []
        values: list[Any] = []
        for key in ("title", "content", "deadline"):
            if key in updates:
                fields.append(f"{key} = ?")
                values.append(updates[key])
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(task_id)

        conn.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?",
            values,
        )
        conn.commit()
        updated = fetch_task_out(conn, task_id, user["user_id"])
    finally:
        conn.close()

    return TaskOut(**dict(updated))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> None:
    conn = get_connection()
    try:
        row = get_task_row_or_404(conn, task_id)
        require_case_assigner(row, user)
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> TaskOut:
    conn = get_connection()
    try:
        row = get_task_row_or_404(conn, task_id)

        case_like = {
            "student_id": row["student_id"],
            "parent_id": row["parent_id"],
            "expert_id": row["expert_id"],
        }
        if not is_case_member(case_like, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        if user["role"] != "Student" or user["user_id"] != row["student_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case Student can complete this task",
            )

        if row["completed_at"] is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task already completed",
            )

        conn.execute(
            """
            UPDATE tasks
            SET completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
              AND completed_at IS NULL
            """,
            (task_id,),
        )
        notify_task_completed(
            conn,
            case_id=int(row["case_id"]),
            task_id=task_id,
            student_id=int(row["student_id"]),
            parent_id=int(row["parent_id"]),
            expert_id=int(row["expert_id"]),
        )
        conn.commit()
        updated = fetch_task_out(conn, task_id, user["user_id"])
    finally:
        conn.close()

    return TaskOut(**dict(updated))


COMMENT_SELECT_SQL = """
    SELECT
        tc.comment_id,
        tc.task_id,
        tc.parent_comment_id,
        tc.author_id,
        u.display_name AS author_name,
        u.role AS author_role,
        tc.content,
        tc.created_at
    FROM task_comments tc
    JOIN users u ON u.user_id = tc.author_id
"""


def _case_like(row: Any) -> dict[str, Any]:
    return {
        "student_id": row["student_id"],
        "parent_id": row["parent_id"],
        "expert_id": row["expert_id"],
    }


def _require_comment_viewer(row: Any, user: dict[str, Any]) -> None:
    if not can_view_case(_case_like(row), user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


def _require_comment_writer(row: Any, user: dict[str, Any]) -> None:
    _require_comment_viewer(row, user)
    if user["role"] not in ("Expert", "Parent"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Expert and Parent can comment",
        )


def _row_to_comment(row: Any, replies: list[CommentOut] | None = None) -> CommentOut:
    return CommentOut(
        comment_id=row["comment_id"],
        task_id=row["task_id"],
        parent_comment_id=row["parent_comment_id"],
        author_id=row["author_id"],
        author_name=row["author_name"],
        author_role=row["author_role"],
        content=row["content"],
        created_at=row["created_at"],
        replies=replies or [],
    )


def _fetch_comment_thread(conn: Any, task_id: int) -> list[CommentOut]:
    rows = conn.execute(
        COMMENT_SELECT_SQL + " WHERE tc.task_id = ? ORDER BY tc.comment_id ASC",
        (task_id,),
    ).fetchall()
    items = [_row_to_comment(r) for r in rows]
    by_id = {c.comment_id: c for c in items}
    roots: list[CommentOut] = []
    for comment in items:
        if comment.parent_comment_id is None:
            roots.append(comment)
            continue
        parent = by_id.get(comment.parent_comment_id)
        if parent is None:
            roots.append(comment)
        else:
            parent.replies.append(comment)
    return roots


def _fetch_comment_out(conn: Any, comment_id: int) -> CommentOut:
    row = conn.execute(
        COMMENT_SELECT_SQL + " WHERE tc.comment_id = ?",
        (comment_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load comment",
        )
    return _row_to_comment(row)


@router.get("/{task_id}/comments", response_model=list[CommentOut])
def list_comments(
    task_id: int,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[CommentOut]:
    conn = get_connection()
    try:
        row = get_task_row_or_404(conn, task_id)
        _require_comment_viewer(row, user)
        mark_comments_read(conn, task_id, user["user_id"])
        conn.commit()
        return _fetch_comment_thread(conn, task_id)
    finally:
        conn.close()


@router.post(
    "/{task_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    task_id: int,
    body: CommentCreateRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> CommentOut:
    content = body.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="content cannot be empty",
        )

    conn = get_connection()
    try:
        row = get_task_row_or_404(conn, task_id)
        _require_comment_writer(row, user)

        parent_id = body.parent_comment_id
        if parent_id is not None:
            parent = conn.execute(
                """
                SELECT comment_id, task_id, parent_comment_id
                FROM task_comments
                WHERE comment_id = ?
                """,
                (parent_id,),
            ).fetchone()
            if parent is None or int(parent["task_id"]) != task_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reply target not found",
                )
            if parent["parent_comment_id"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only reply to a top-level comment",
                )

        cur = conn.execute(
            """
            INSERT INTO task_comments (task_id, parent_comment_id, author_id, content)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, parent_id, user["user_id"], content),
        )
        mark_comments_read(conn, task_id, user["user_id"])
        conn.commit()
        return _fetch_comment_out(conn, int(cur.lastrowid))
    finally:
        conn.close()
