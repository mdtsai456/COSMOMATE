# Design: 簡易前端（靜態頁 + FastAPI 同伺服）

日期：2026-08-12  
狀態：已核准（A+C）

## 目標

純 HTML／CSS／JS 單頁，由 FastAPI 一併提供靜態檔，對接既有 JWT API。

## 架構

- `frontend/index.html` + `styles.css` + `app.js`
- FastAPI：API routes 優先；再提供 `/`、`/styles.css`、`/app.js`（或 `StaticFiles`）
- 同源呼叫 API（無需 CORS）；`localStorage` 存 JWT

## 畫面

1. 登入（未登入）
2. 已登入殼：品牌、使用者、角色、登出；Case 列表；任務列表
3. Expert：Assign 新增／改／刪
4. Parent：Contract（同 Assign API）
5. Student：完成任務

## 不做

打包工具、路由套件、註冊、建 Case UI。
