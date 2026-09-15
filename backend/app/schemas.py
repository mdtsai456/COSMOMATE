from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["Student", "Parent", "Expert", "Admin"]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: Role


class UserOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: Role


class AdminUserOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: Role
    email: str | None
    is_active: int
    created_at: str


class CaseOut(BaseModel):
    case_id: int
    case_name: str | None
    status: str
    student_id: int
    student_name: str
    parent_id: int
    parent_name: str
    expert_id: int
    expert_name: str
    created_at: str
    updated_at: str


class CaseCreateRequest(BaseModel):
    student_id: int
    parent_id: int
    case_name: str | None = Field(default=None, min_length=1)


class TaskItemIn(BaseModel):
    title: str = Field(min_length=1)
    content: str | None = None
    deadline: str | None = None


class RecurringPlanIn(BaseModel):
    daily_duration: str = Field(min_length=1, max_length=40)
    times_per_week: int = Field(ge=1, le=7)
    weeks: int = Field(ge=1, le=12)


class AssignmentCreateRequest(BaseModel):
    tasks: list[TaskItemIn] = Field(min_length=1)
    recurring: RecurringPlanIn | None = None


class TaskOut(BaseModel):
    task_id: int
    assignment_id: int
    title: str
    content: str | None
    deadline: str | None
    is_done: int
    completed_at: str | None
    assigned_by: int
    assigned_by_name: str
    assigned_by_role: Role
    assigned_at: str
    created_at: str
    updated_at: str
    comment_count: int = 0
    unread_comment_count: int = 0
    is_periodic: int = 0


class AssignmentCreateResponse(BaseModel):
    assignment_id: int
    case_id: int
    tasks: list[TaskOut]


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    content: str | None = None
    deadline: str | None = None


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_comment_id: int | None = None


class CommentOut(BaseModel):
    comment_id: int
    task_id: int
    parent_comment_id: int | None
    author_id: int
    author_name: str
    author_role: Role
    content: str
    created_at: str
    replies: list["CommentOut"] = Field(default_factory=list)


NotificationType = Literal["task_assigned", "task_completed"]


class NotificationOut(BaseModel):
    notification_id: int
    type: NotificationType
    task_id: int
    case_id: int
    actor_id: int
    actor_name: str
    actor_role: Role
    task_title: str
    is_read: int
    created_at: str


class UnreadCountOut(BaseModel):
    count: int


class NotificationsReadRequest(BaseModel):
    ids: list[int] | None = None


MoodKind = Literal["happy", "calm", "okay", "sad", "angry"]


class MoodJournalOut(BaseModel):
    journal_id: int
    case_id: int
    student_id: int
    entry_date: str
    mood: MoodKind
    note: str | None
    created_at: str
    updated_at: str


class MoodUpsertRequest(BaseModel):
    mood: MoodKind
    note: str | None = Field(default=None, max_length=80)
    entry_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
