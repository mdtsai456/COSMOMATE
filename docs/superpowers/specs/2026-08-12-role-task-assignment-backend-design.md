# Design: Expert / Parent / Student 任務指派後端（MVP）

日期：2026-08-12  
狀態：待使用者審核

## 1. 目標

依既有 SQLite schema（`role_case_task_dbeaver.sql`）建立可執行的 FastAPI 後端，支援：

Home → Login → 角色分流 → Assign／Contract（同一能力）→ Student 執行 → Expert／Parent 看進度。

## 2. 角色與流程

| 角色 | 登入後入口語意 | 實際能力 |
|------|----------------|----------|
| Expert | Assign | 查看自己的 Case；對該 Case 派發任務；查看任務進度 |
| Parent | Contract | 與 Assign **相同**（僅 UI 名稱不同） |
| Student | Execute Assignment | 只能看到自己的 Case／Task；標記自己的任務完成 |

流程：

```
Login (JWT)
  ├─ Expert → GET /cases → POST /cases/{id}/assignments → GET /cases/{id}/tasks
  ├─ Parent → 同上（Contract = Assign）
  └─ Student → GET /cases → GET /cases/{id}/tasks → POST /tasks/{id}/complete
                                              ↓
                    Expert / Parent 以 GET /cases/{id}/tasks 看結果回流
```

領域規則（對齊 schema）：

- 一個 Case = 1 Student + 1 Parent + 1 Expert；每位 Expert 可管多個 Case。
- 一次派發 = 一筆 `task_assignments` + 多筆 `tasks`。
- 任務完成：只寫 `completed_at`；`is_done` 由 DB generated column 推導；不可反完成。
- 僅該 Case 的 Parent／Expert 可派發；`closed` Case 不可再派發。

## 3. 技術選擇

- Python + FastAPI + SQLite
- 啟動時執行既有 `role_case_task_dbeaver.sql`（`PRAGMA foreign_keys=ON`）
- 使用標準庫 `sqlite3` 薄封裝（不引入 ORM／Alembic）
- 認證：JWT Bearer（payload 含 `user_id`, `role`）；密碼 bcrypt
- 虛擬環境：專案內 `.venv`（不污染本機 Python）

不採用 SQLAlchemy／SQLModel：避免與既有 SQL 檔雙重維護；MVP 範圍不需要 migration 框架。

## 4. API

除登入外皆需 `Authorization: Bearer <token>`。

| Method | Path | 授權 | 說明 |
|--------|------|------|------|
| `POST` | `/auth/login` | 公開 | `username` + `password` → `{ access_token, token_type, role, user_id }` |
| `GET` | `/me` | 已登入 | 目前使用者 |
| `GET` | `/cases` | 已登入 | **只回與自己相關的 cases**（依 role 過濾） |
| `GET` | `/cases/{case_id}/tasks` | Case 成員 | 該 case 任務列表；非成員視為不可見 |
| `POST` | `/cases/{case_id}/assignments` | 該 Case 的 Parent 或 Expert | body：`{ tasks: [{ title, content?, deadline? }, ...] }`，transaction 建立 |
| `POST` | `/tasks/{task_id}/complete` | 該 task 所屬 Case 的 Student | 寫入 `completed_at`（僅首次） |

### 可見性與授權（硬性）

- **Student 永遠看不到其他學生的 case／task**：列表與明細查詢都以 `student_id = 目前使用者` 過濾。
- **非成員**存取 case／task（含猜 `task_id`／`case_id`）→ **`404`**（當不存在，避免洩漏）。
- **已是成員但角色不允許該動作**（例如 Student 派發、Parent／Expert 呼叫 complete）→ **`403`**。
- 業務狀態衝突：任務已完成再 complete → `409`；`closed` case 再派發 → `400`。

### Request／Response 要點

**Login**

```json
{ "username": "expert001", "password": "password123" }
```

**Create assignment**

```json
{
  "tasks": [
    { "title": "專注力訓練", "content": "完成今日 20 分鐘訓練", "deadline": "2026-08-20 18:00:00" }
  ]
}
```

回傳：`assignment_id`、建立的 tasks 列表。

**Task 列表項目**：`task_id`, `assignment_id`, `title`, `content`, `deadline`, `is_done`, `completed_at`, `assigned_by`, `assigned_by_role`, `assigned_at`。

## 5. 專案結構

```
Perfect_Co_parenting/
  role_case_task_dbeaver.sql
  backend/
    app/
      main.py
      db.py
      auth.py
      schemas.py
      routers/
        auth.py
        cases.py
        assignments.py
        tasks.py
    seed.py
    requirements.txt
  README.md
  docs/superpowers/specs/2026-08-12-role-task-assignment-backend-design.md
```

## 6. Seed 資料

僅在資料庫尚無 users 時執行一次：

| username | role | password |
|----------|------|----------|
| expert001 | Expert | password123 |
| parent001 | Parent | password123 |
| student001 | Student | password123 |

並建立：`student_parent_links`、一個 `active` Case（三人綁定）。

## 7. 錯誤處理摘要

| 情況 | HTTP |
|------|------|
| 帳密錯誤 | 401 |
| 未帶／無效 JWT | 401 |
| 資源對呼叫者不可見（非成員／猜 id） | 404 |
| 成員但角色不允許該動作 | 403 |
| closed case 派發 | 400 |
| 任務已完成 | 409 |
| 驗證失敗（空 tasks 等） | 422 |

## 8. 明確不做（MVP 外）

- 註冊、改密碼、停用帳號 API
- Parent／Student 綁定、建立／關閉 Case API（靠 seed）
- 任務反完成、編輯／刪除任務
- 推播／即時通知
- ORM、migration、多資料庫

## 9. 測試策略（實作階段）

- 手動／簡易 pytest：三角色登入；Expert／Parent 派發；Student 只看到自己的任務；完成後 Expert／Parent 可見 `completed_at`；非成員存取 → 404；成員但角色不符 → 403；重複 complete → 409。

## 10. 成功標準

1. 三個 seed 帳號可登入並依 role 分流使用上述 API。
2. Assign／Contract 行為相同，皆寫入 `task_assignments` + `tasks`。
3. Student 列表中不可能出現其他學生任務。
4. 完成結果可被該 Case 的 Expert／Parent 查回。
