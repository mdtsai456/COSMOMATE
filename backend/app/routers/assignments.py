from __future__ import annotations

from datetime import date, timedelta
from re import match
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.access import can_view_case, fetch_case, fetch_tasks_for_case
from app.auth import get_current_user
from app.db import get_connection
from app.notifications import notify_task_assigned
from app.schemas import AssignmentCreateRequest, AssignmentCreateResponse, RecurringPlanIn, TaskItemIn, TaskOut

router = APIRouter(prefix="/cases", tags=["assignments"])


def parse_start_date(deadline: str | None) -> date:
    if deadline:
        found = match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", deadline.strip())
        if found:
            return date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
    return date.today()


def expand_recurring_dates(start: date, times_per_week: int, weeks: int) -> list[date]:
    dates: list[date] = []
    for week in range(weeks):
        for session in range(times_per_week):
            offset = week * 7 + (session * 7) // times_per_week
            dates.append(start + timedelta(days=offset))
    return dates


def expand_recurring_tasks(template: TaskItemIn, plan: RecurringPlanIn) -> list[tuple[str, str | None, str, int]]:
    start = parse_start_date(template.deadline)
    dates = expand_recurring_dates(start, plan.times_per_week, plan.weeks)
    total = len(dates)
    duration = plan.daily_duration.strip()
    rows: list[tuple[str, str | None, str, int]] = []
    for index, day in enumerate(dates, start=1):
        note = f"每次 {duration}（第 {index}/{total} 次）"
        rows.append(
            (
                template.title,
                note,
                f"{day.isoformat()} 18:00:00",
                1,
            )
        )
    return rows


@router.post("/{case_id}/assignments", response_model=AssignmentCreateResponse)
def create_assignment(
    case_id: int,
    body: AssignmentCreateRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> AssignmentCreateResponse:
    conn = get_connection()
    try:
        case = fetch_case(conn, case_id)
        if case is None or not can_view_case(case, user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

        if user["role"] not in ("Parent", "Expert"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Parent or Expert can assign tasks",
            )

        if user["user_id"] not in (case["parent_id"], case["expert_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only this case's Parent or Expert can assign",
            )

        if case["status"] == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign tasks to a closed case",
            )

        cur = conn.execute(
            """
            INSERT INTO task_assignments (case_id, assigned_by)
            VALUES (?, ?)
            """,
            (case_id, user["user_id"]),
        )
        assignment_id = cur.lastrowid

        if body.recurring is not None:
            to_insert = expand_recurring_tasks(body.tasks[0], body.recurring)
        else:
            to_insert = [
                (task.title, task.content, task.deadline, 0) for task in body.tasks
            ]

        task_ids: list[int] = []
        for title, content, deadline, is_periodic in to_insert:
            cur_task = conn.execute(
                """
                INSERT INTO tasks (assignment_id, title, content, deadline, is_periodic)
                VALUES (?, ?, ?, ?, ?)
                """,
                (assignment_id, title, content, deadline, is_periodic),
            )
            task_ids.append(int(cur_task.lastrowid))

        notify_task_assigned(
            conn,
            case=case,
            task_ids=task_ids,
            actor_id=user["user_id"],
            actor_role=user["role"],
        )

        conn.commit()
        rows = [
            r
            for r in fetch_tasks_for_case(conn, case_id, user["user_id"])
            if r["assignment_id"] == assignment_id
        ]
    finally:
        conn.close()

    return AssignmentCreateResponse(
        assignment_id=assignment_id,
        case_id=case_id,
        tasks=[TaskOut(**dict(r)) for r in rows],
    )
