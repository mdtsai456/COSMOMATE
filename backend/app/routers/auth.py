from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import create_access_token, get_current_user, verify_password
from app.db import get_connection
from app.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id, role, password_hash, is_active
            FROM users
            WHERE username = ?
            """,
            (body.username,),
        ).fetchone()
    finally:
        conn.close()

    if (
        row is None
        or not row["is_active"]
        or not row["password_hash"]
        or not verify_password(body.password, row["password_hash"])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(row["user_id"], row["role"])
    return LoginResponse(
        access_token=token,
        user_id=row["user_id"],
        role=row["role"],
    )


@router.get("/me", response_model=UserOut)
def me(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> UserOut:
    return UserOut(**user)


@router.get("/users", response_model=list[UserOut])
def list_users_by_role(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    role: Annotated[Literal["Student", "Parent"], Query()],
) -> list[UserOut]:
    if user["role"] not in ("Expert", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Expert or Admin can list users",
        )

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT user_id, username, display_name, role
            FROM users
            WHERE role = ? AND is_active = 1
            ORDER BY user_id ASC
            """,
            (role,),
        ).fetchall()
    finally:
        conn.close()

    return [UserOut(**dict(r)) for r in rows]
