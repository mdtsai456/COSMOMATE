# Role Task Assignment Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依 `docs/superpowers/specs/2026-08-12-role-task-assignment-backend-design.md` 實作 FastAPI + SQLite MVP，支援 Login → 角色分流 → Assign／Contract → Student 完成 → Expert／Parent 看進度。

**Architecture:** 啟動時執行既有 `role_case_task_dbeaver.sql`；`sqlite3` 薄封裝；JWT Bearer；權限在 router 層驗證（非成員 404、角色不符 403）。

**Tech Stack:** Python 3.11+、FastAPI、uvicorn、PyJWT、bcrypt、pytest、httpx

## Global Constraints

- 使用專案內 `backend/.venv`，不污染本機 Python
- Contract = Assign（同一 API）
- Student 看不到其他學生的 case／task
- 非成員 → 404；成員但角色不符 → 403；已完成再 complete → 409；closed 派發 → 400
- 不做註冊／建 Case／ORM／任務反完成
- 無 git 時略過 commit 步驟

## File Structure

```
backend/
  requirements.txt
  seed.py
  app/
    __init__.py
    main.py
    db.py
    auth.py
    schemas.py
    routers/
      __init__.py
      auth.py
      cases.py
      assignments.py
      tasks.py
  tests/
    conftest.py
    test_flow.py
README.md
```

---

### Task 1: Scaffold + DB init + Seed

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/db.py`
- Create: `backend/seed.py`
- Create: `backend/app/main.py`（最小 app + lifespan 初始化）

**Interfaces:**
- Produces: `get_connection() -> sqlite3.Connection`, `init_db(db_path: str) -> None`, `seed_if_empty(conn) -> None`, `DATABASE_PATH`

- [x] **Step 1: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
PyJWT>=2.9.0
bcrypt>=4.2.0
pydantic>=2.9.0
pytest>=8.3.0
httpx>=0.27.0
```

- [ ] **Step 2: Implement `backend/app/db.py`**

- DB 檔預設 `backend/data/app.db`
- `init_db`：讀專案根目錄 `role_case_task_dbeaver.sql` 並 `executescript`；`PRAGMA foreign_keys=ON`
- `get_connection`：回傳 `row_factory=sqlite3.Row` 的連線

- [ ] **Step 3: Implement `backend/seed.py`**

若 `users` 為空：建立 expert001／parent001／student001（密碼 `password123` bcrypt）、link、一個 active case。

- [ ] **Step 4: Minimal `main.py` lifespan 呼叫 init + seed**

- [ ] **Step 5: Create venv、安裝依賴、啟動確認 `/docs` 可開**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -c "from app.db import init_db; from pathlib import Path; init_db(str(Path('data/app.db'))); print('ok')"
```

Expected: `ok` 且產生 `backend/data/app.db`

---

### Task 2: Auth (JWT login + /me)

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`（include router）
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_flow.py`（login／me 測試）

**Interfaces:**
- Produces: `create_access_token(user_id: int, role: str) -> str`, `get_current_user(credentials) -> dict`（含 `user_id`, `username`, `display_name`, `role`）
- JWT secret：環境變數 `JWT_SECRET` 或預設 `dev-secret-change-me`
- Token 有效期：24h

- [ ] **Step 1: Write failing tests**（login 成功、錯誤密碼 401、/me 需 token）

- [ ] **Step 2: Implement auth + schemas + router**

- [ ] **Step 3: Run pytest；Expected PASS**

```powershell
.\.venv\Scripts\python -m pytest tests/test_flow.py -v
```

---

### Task 3: Cases + Assignments + Complete

**Files:**
- Create: `backend/app/routers/cases.py`
- Create: `backend/app/routers/assignments.py`
- Create: `backend/app/routers/tasks.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_flow.py`

**Interfaces:**
- `GET /cases`：依 role 過濾 `expert_id`／`parent_id`／`student_id`
- `GET /cases/{case_id}/tasks`：先確認成員，否則 404
- `POST /cases/{case_id}/assignments`：成員且 Parent／Expert；closed → 400；transaction
- `POST /tasks/{task_id}/complete`：先找 task+case；非學生本人且非成員 → 404；成員但非 Student → 403；已完成 → 409

- [ ] **Step 1: 擴充測試**

涵蓋：Expert 派發、Student 見任務並完成、Parent 見 completed_at、Student 派發 → 403、不存在 case → 404、重複 complete → 409

- [ ] **Step 2: 實作三個 routers**

- [ ] **Step 3: pytest 全過**

---

### Task 4: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 寫啟動、seed 帳號、主要 API、角色流程說明**

- [ ] **Step 2: 手動 smoke**（可選）

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir .
```

---

## Spec coverage checklist

- [x] Login JWT
- [x] Role-filtered cases
- [x] Assign = Contract
- [x] Student execute
- [x] Results visible to Expert/Parent
- [x] Visibility 404 / role 403 / 409 / 400
- [x] Seed accounts
- [x] No ORM; reuse SQL file
