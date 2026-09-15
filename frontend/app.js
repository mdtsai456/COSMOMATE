(() => {
  const TOKEN_KEY = "pcp_token";
  const root = document.getElementById("app");

  const MAX_STUDENT_LEVEL = 30;

  const FILTERS = [
    { id: "open", label: "任務清單", icon: "tasks" },
    { id: "history", label: "歷史紀錄", icon: "history" },
  ];

  const EXPERT_FILTERS = [
    ...FILTERS,
    { id: "status", label: "狀態追蹤", icon: "status" },
  ];

  const STUDENT_FILTERS = [
    { id: "open", label: "任務清單", icon: "tasks" },
    { id: "achievements", label: "達成成就", icon: "trophy" },
  ];

  // 依角色變更主題色
  const ROLE_BODY_CLASSES = [
    "role-expert",
    "role-parent",
    "role-student",
    "role-admin",
  ];

  function syncRoleBodyClass(role) {
    document.body.classList.remove(...ROLE_BODY_CLASSES);
    const byRole = {
      Expert: "role-expert",
      Parent: "role-parent",
      Student: "role-student",
      Admin: "role-admin",
    };
    const cls = byRole[role];
    if (cls) document.body.classList.add(cls);
  }

  const MOODS = [
    { id: "happy", label: "開心" },
    { id: "calm", label: "平靜" },
    { id: "okay", label: "還好" },
    { id: "sad", label: "難過" },
    { id: "angry", label: "生氣" },
  ];

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    user: null,
    cases: [],
    selectedCaseId: null,
    tasks: [],
    moods: [],
    moodPick: null,
    moodNote: "",
    moodDraftDate: null,
    filter: "open",
    error: "",
    showAssign: false,
    showNewCase: false,
    showClearHistory: false,
    commentTaskId: null,
    comments: [],
    replyingToId: null,
    editingTaskId: null,
    unreadCount: 0,
    notifications: [],
    showNotifPanel: false,
    calMonth: null,
    dayFilter: null,
    openTasksExpanded: false,
    doneTasksExpanded: false,
    expertTasksExpanded: false,
    parentTasksExpanded: false,
    statusRangeDays: 14,
    appEntered: false,
    sidebarOpen: false,
  };

  function assignLabel(role) {
    return role === "Parent" ? "Contract" : "Assign";
  }

  function filterLabel(id) {
    return (
      FILTERS.find((f) => f.id === id)?.label ||
      EXPERT_FILTERS.find((f) => f.id === id)?.label ||
      STUDENT_FILTERS.find((f) => f.id === id)?.label ||
      id
    );
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (state.token) {
      headers.Authorization = `Bearer ${state.token}`;
    }
    const resp = await fetch(path, { ...options, headers });
    if (resp.status === 204) {
      return null;
    }
    const text = await resp.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!resp.ok) {
      const detail = data && data.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
            : `請求失敗 (${resp.status})`;
      const err = new Error(message);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  function setError(message) {
    state.error = message || "";
    const el = document.querySelector("[data-error]");
    if (el) el.textContent = state.error;
  }

  function ensureCalMonth() {
    if (!state.calMonth) {
      const now = new Date();
      state.calMonth = { y: now.getFullYear(), m: now.getMonth() };
    }
  }

  async function bootstrap() {
    if (!state.token) {
      renderIntro();
      return;
    }
    try {
      state.user = await api("/me");
      await loadCases();
      await refreshUnread();
      renderApp();
      startPolling();
    } catch {
      state.token = "";
      localStorage.removeItem(TOKEN_KEY);
      renderIntro();
    }
  }

  function renderIntro() {
    if (typeof window.stopLoginMotion === "function") {
      window.stopLoginMotion();
    }
    document.title = "CosmoMate 共育星球";
    document.body.classList.add("intro-active");
    document.body.classList.remove("login-active", "app-active");
    syncRoleBodyClass(null);

    root.innerHTML = `
      <main class="stage is-intro" aria-label="CosmoMate 開場頁">
        <div class="stars stars-far" aria-hidden="true"></div>
        <div class="stars stars-near" aria-hidden="true"></div>
        <div class="hero">
          <img class="planet" src="/landing/assets/planet.png" alt="" />
          <div class="brand">
            <img class="logo" src="/landing/assets/logo.png" alt="COSMOMATE" />
            <p class="tagline">共育星球</p>
            <button type="button" class="login-btn" id="intro-login">登入</button>
          </div>
        </div>
        <div class="intro-veil" aria-hidden="true"></div>
      </main>
    `;

    if (typeof window.initLandingIntro === "function") {
      window.initLandingIntro();
    }

    const stage = root.querySelector(".stage");
    const veil = root.querySelector(".intro-veil");
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const zoomMs = 1000;

    function finishIntro() {
      if (stage) {
        stage.classList.add("is-zoom", "is-ready");
      }
      if (veil && veil.isConnected) {
        veil.remove();
      }
    }

    if (prefersReduced) {
      finishIntro();
    } else {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          if (veil) {
            veil.classList.add("is-clear");
          }
          if (stage) {
            stage.classList.add("is-zoom");
          }
        });
      });
      window.setTimeout(() => {
        if (stage) {
          stage.classList.add("is-ready");
        }
        if (veil && veil.isConnected) {
          veil.remove();
        }
      }, zoomMs);
    }

    document.getElementById("intro-login").addEventListener("click", () => {
      renderLogin();
    });
  }

  async function loadCases() {
    if (state.user?.role === "Admin") {
      state.cases = [];
      state.tasks = [];
      state.moods = [];
      state.selectedCaseId = null;
      return;
    }
    state.cases = await api("/cases");
    if (
      state.selectedCaseId &&
      !state.cases.some((c) => c.case_id === state.selectedCaseId)
    ) {
      state.selectedCaseId = null;
    }
    if (!state.selectedCaseId && state.cases.length) {
      state.selectedCaseId = state.cases[0].case_id;
    }
    if (state.selectedCaseId) {
      await loadTasks(state.selectedCaseId);
    } else {
      state.tasks = [];
      state.moods = [];
    }
  }

  async function loadTasks(caseId) {
    const [tasks, moods] = await Promise.all([
      api(`/cases/${caseId}/tasks`),
      api(`/cases/${caseId}/moods`).catch(() => []),
    ]);
    state.tasks = tasks;
    state.moods = Array.isArray(moods) ? moods : [];
    state.moodDraftDate = null;
  }

  async function refreshUnread() {
    try {
      const data = await api("/notifications/unread-count");
      const next = Number(data.count) || 0;
      const grew = next > state.unreadCount;
      state.unreadCount = next;
      // 有新通知時重載任務，讓日曆橘點／列表即時更新
      if (grew && state.selectedCaseId) {
        await loadTasks(state.selectedCaseId);
        return true;
      }
    } catch {
      state.unreadCount = 0;
    }
    return false;
  }

  function startPolling() {
    if (state._pollTimer) clearInterval(state._pollTimer);
    state._pollTimer = setInterval(async () => {
      if (!state.token || !state.user) return;
      try {
        const changed = await refreshUnread();
        if (changed && !state.showAssign && !state.editingTaskId && !state.commentTaskId) {
          renderApp();
        } else {
          const badge = document.querySelector(".dash-badge");
          const btn = document.getElementById("notif-btn");
          if (btn) {
            const existing = btn.querySelector(".dash-badge");
            if (state.unreadCount > 0) {
              const text = state.unreadCount > 99 ? "99+" : String(state.unreadCount);
              if (existing) existing.textContent = text;
              else {
                const span = document.createElement("span");
                span.className = "dash-badge";
                span.textContent = text;
                btn.appendChild(span);
              }
            } else if (existing) {
              existing.remove();
            }
          }
          void badge;
        }
      } catch {
        /* ignore poll errors */
      }
    }, 8000);
  }

  async function loadNotifications() {
    state.notifications = await api("/notifications");
  }

  function todayKey() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(
      2,
      "0"
    )}-${String(now.getDate()).padStart(2, "0")}`;
  }

  function moodLabel(id) {
    return MOODS.find((m) => m.id === id)?.label || id;
  }

  function moodImg(id) {
    return `/img/mood-${id}.png`;
  }

  function formatMoodDay(key) {
    const parts = String(key).split("-");
    if (parts.length !== 3) return key;
    return `${Number(parts[1])}/${Number(parts[2])}`;
  }

  function syncMoodDraft(viewDate) {
    if (state.moodDraftDate === viewDate) return;
    const entry = state.moods.find((m) => m.entry_date === viewDate);
    state.moodDraftDate = viewDate;
    state.moodPick = entry?.mood || null;
    state.moodNote = entry?.note || "";
  }

  function weekMoodDays() {
    const end = new Date();
    end.setHours(0, 0, 0, 0);
    const days = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(end);
      d.setDate(end.getDate() - i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(
        2,
        "0"
      )}-${String(d.getDate()).padStart(2, "0")}`;
      const entry = state.moods.find((m) => m.entry_date === key);
      days.push({
        key,
        dow: ["日", "一", "二", "三", "四", "五", "六"][d.getDay()],
        mood: entry?.mood || null,
      });
    }
    return days;
  }

  function paintMoodWeek() {
    weekMoodDays().forEach((d) => {
      const el = root.querySelector(`[data-mood-day="${d.key}"]`);
      if (!el) return;
      el.title = d.mood ? moodLabel(d.mood) : "尚未紀錄";
      const img = el.querySelector("img");
      const empty = el.querySelector(".mood-week-empty");
      if (d.mood) {
        const alt = moodLabel(d.mood);
        const src = moodImg(d.mood);
        if (img) {
          img.src = src;
          img.alt = alt;
        } else if (empty) {
          empty.replaceWith(
            Object.assign(document.createElement("img"), { src, alt })
          );
        }
      }
    });
  }

  function renderMoodHtml({ isStudent, selected }) {
    if (!selected) {
      return `
        <article class="stat-card stat-card--mood">
          <div class="mood-head"><h3>心情札記</h3></div>
          <p class="mood-empty">請先選擇 Case</p>
        </article>`;
    }

    const viewDate = state.dayFilter || todayKey();
    syncMoodDraft(viewDate);
    const saved = state.moods.find((m) => m.entry_date === viewDate);
    const recent = state.moods
      .filter((m) => m.entry_date !== viewDate)
      .slice(0, 3);
    const week = weekMoodDays();
    const dateLabel = viewDate === todayKey() ? "今天" : formatMoodDay(viewDate);

    const weekHtml = `
      <div class="mood-week" aria-label="本週心情">
        ${week
          .map(
            (d) => `
          <div class="mood-week-day${
            d.key === todayKey() ? " is-today" : ""
          }" data-mood-day="${d.key}" title="${escapeHtml(
            d.mood ? moodLabel(d.mood) : "尚未紀錄"
          )}">
            <span>${d.dow}</span>
            ${
              d.mood
                ? `<img src="${moodImg(d.mood)}" alt="${escapeHtml(
                    moodLabel(d.mood)
                  )}" />`
                : `<span class="mood-week-empty" aria-hidden="true"></span>`
            }
          </div>`
          )
          .join("")}
      </div>`;

    const picksHtml = isStudent
      ? `<div class="mood-picks">
          ${MOODS.map(
            (m) => `
            <button type="button" class="mood-pick${
              state.moodPick === m.id ? " active" : ""
            }" data-mood="${m.id}" aria-pressed="${
              state.moodPick === m.id ? "true" : "false"
            }" aria-label="${m.label}">
              <img src="${moodImg(m.id)}" alt="" />
              <small>${m.label}</small>
            </button>`
          ).join("")}
        </div>
        <textarea class="mood-note" id="mood-note" maxlength="80" rows="2" placeholder="用一句話記下今天的感覺…">${escapeHtml(
          state.moodNote
        )}</textarea>
        <div class="mood-actions">
          <button type="button" class="dash-btn" id="mood-save">紀錄</button>
        </div>`
      : saved
        ? `<p class="mood-saved"><strong>${escapeHtml(
            moodLabel(saved.mood)
          )}</strong>${
            saved.note ? ` · ${escapeHtml(saved.note)}` : ""
          }</p>`
        : `<p class="mood-empty">這天還沒有心情紀錄</p>`;

    const recentHtml = recent.length
      ? `<ul class="mood-recent" aria-label="最近紀錄">
          ${recent
            .map(
              (m) => `
            <li>
              <img src="${moodImg(m.mood)}" alt="${escapeHtml(
                moodLabel(m.mood)
              )}" />
              <time datetime="${escapeHtml(m.entry_date)}">${formatMoodDay(
                m.entry_date
              )}</time>
              <p>${escapeHtml(m.note || moodLabel(m.mood))}</p>
            </li>`
            )
            .join("")}
        </ul>`
      : "";

    return `
      <article class="stat-card stat-card--mood">
        <div class="mood-head">
          <h3>心情札記</h3>
          <p class="mood-date">${dateLabel}</p>
        </div>
        ${weekHtml}
        ${picksHtml}
        ${recentHtml}
      </article>`;
  }

  function deadlineDateKey(deadline) {
    if (!deadline) return null;
    const m = String(deadline).trim().match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    if (!m) return null;
    return `${m[1]}-${String(m[2]).padStart(2, "0")}-${String(m[3]).padStart(2, "0")}`;
  }

  function isTaskDone(t) {
    if (t == null) return false;
    if (t.completed_at) return true;
    const done = t.is_done;
    return done === true || done === 1 || done === "1";
  }

  function periodicContentPreview(content) {
    const text = String(content || "").replace(/\s+/g, " ").trim();
    const duration = text.match(/每次\s*([^，,（(]+)/);
    const session = text.match(/（第\s*\d+(?:\/\d+)?\s*次）/);
    if (duration && session) {
      return `每次 ${duration[1].trim()}${session[0]}`;
    }
    return text;
  }

  const TASK_AVATARS = [
    "task1.jpg",
    "task2.jpg",
    "task3.jpg",
    "task4.jpg",
    "task5.jpg",
    "task6.jpg",
    "task7.jpg",
    "task8.jpg",
    "task9.jpg",
  ];

  function taskAvatarSrc(taskId) {
    const n = Math.abs(Number(taskId) || 0);
    const i = (n * 17 + 31) % TASK_AVATARS.length;
    return `/img/${TASK_AVATARS[i]}`;
  }

  function tasksForFilter(filterId, { applyDay = true } = {}) {
    let list = [...state.tasks];
    if (filterId === "open") {
      list = list.filter((t) => !isTaskDone(t));
    } else if (filterId === "done") {
      list = list.filter((t) => isTaskDone(t));
    } else if (filterId === "expert") {
      list = list.filter((t) => t.assigned_by_role === "Expert");
    } else if (filterId === "parent") {
      list = list.filter((t) => t.assigned_by_role === "Parent");
    } else if (filterId === "history") {
      list = list.filter(
        (t) => t.assigned_by_role === "Expert" || t.assigned_by_role === "Parent"
      );
    } else if (filterId === "assigned") {
      // Student: 不分 Expert／Parent，顯示全部指派任務
    }
    if (applyDay && state.dayFilter) {
      list = list.filter((t) => deadlineDateKey(t.deadline) === state.dayFilter);
    }
    return list;
  }

  function filteredTasks() {
    return tasksForFilter(state.filter);
  }

  function filterCounts() {
    const open = tasksForFilter("open", { applyDay: false }).length;
    const done = tasksForFilter("done", { applyDay: false }).length;
    return {
      open: open + done,
      done,
      expert: tasksForFilter("expert", { applyDay: false }).length,
      parent: tasksForFilter("parent", { applyDay: false }).length,
      history: tasksForFilter("history", { applyDay: false }).length,
      assigned: tasksForFilter("assigned", { applyDay: false }).length,
      achievements: studentLevel(done),
      status: open,
    };
  }

  function completionStats() {
    const total = state.tasks.length;
    const done = state.tasks.filter((t) => isTaskDone(t)).length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    return { total, done, pct };
  }

  function studentLevel(doneCount) {
    const n = Number(doneCount) || 0;
    return Math.min(MAX_STUDENT_LEVEL, Math.floor(n / 5) + 1);
  }

  function achievementLockSvg() {
    return `<span class="achievement-lock" aria-hidden="true">
      <svg viewBox="0 0 48 48">
        <path d="M16 22v-6a8 8 0 0 1 16 0v6" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"/>
        <rect x="12" y="21" width="24" height="20" rx="4.5" fill="currentColor"/>
        <circle cx="24" cy="29.5" r="2.4" fill="#eef1f4"/>
        <path d="M24 32v5" stroke="#eef1f4" stroke-width="2.2" stroke-linecap="round"/>
      </svg>
    </span>`;
  }

  function renderAchievementsHtml(level) {
    const cards = Array.from({ length: MAX_STUDENT_LEVEL }, (_, i) => {
      const n = i + 1;
      const unlocked = n <= level;
      return `
        <article class="achievement-card${unlocked ? "" : " is-locked"}">
          <div class="achievement-frame">
            ${
              unlocked
                ? `<img src="/img/level${n}.jpg" alt="Level ${n}" />`
                : achievementLockSvg()
            }
          </div>
          <p>Level ${n}</p>
          <small>${unlocked ? "已收集" : "未解鎖"}</small>
        </article>`;
    }).join("");
    return `
      <section class="achievement-section">
        <div class="task-section-head">
          <div>
            <h2>達成成就（${level} / ${MAX_STUDENT_LEVEL}）</h2>
            <p>完成任務可解鎖新的 Profile，目前已收集 ${level} 個</p>
          </div>
        </div>
        <div class="achievement-grid">${cards}</div>
      </section>`;
  }

  const MOOD_SCORE = {
    happy: 2,
    calm: 1,
    okay: 0,
    sad: -1,
    angry: -2,
  };

  function moodScore(id) {
    if (id == null || !Object.prototype.hasOwnProperty.call(MOOD_SCORE, id)) {
      return null;
    }
    return MOOD_SCORE[id];
  }

  function shiftDateKey(key, deltaDays) {
    const parts = String(key).split("-").map(Number);
    if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return key;
    const dt = new Date(parts[0], parts[1] - 1, parts[2]);
    dt.setDate(dt.getDate() + deltaDays);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(
      dt.getDate()
    ).padStart(2, "0")}`;
  }

  function dateKeysBack(days) {
    const end = todayKey();
    const keys = [];
    for (let i = days - 1; i >= 0; i -= 1) {
      keys.push(shiftDateKey(end, -i));
    }
    return keys;
  }

  function avg(nums) {
    if (!nums.length) return null;
    return nums.reduce((a, b) => a + b, 0) / nums.length;
  }

  function stdev(nums) {
    if (nums.length < 2) return 0;
    const m = avg(nums);
    const v = nums.reduce((s, n) => s + (n - m) * (n - m), 0) / (nums.length - 1);
    return Math.sqrt(v);
  }

  function signedNum(n, digits) {
    if (n == null || Number.isNaN(n)) return "—";
    const t = Number(n).toFixed(digits);
    return Number(t) > 0 ? `+${t}` : t;
  }

  function pctLabel(n) {
    if (n == null || Number.isNaN(n)) return "—";
    return `${Math.round(n * 100)}%`;
  }

  function deltaChip(delta, { invert = false, asPct = false } = {}) {
    if (delta == null || Number.isNaN(delta) || Math.abs(delta) < 0.015) {
      return `<span class="status-delta is-flat">持平</span>`;
    }
    const down = delta < 0;
    const bad = invert ? !down : down;
    const abs = asPct
      ? `${Math.round(Math.abs(delta) * 100)}%`
      : Math.abs(delta).toFixed(1);
    return `<span class="status-delta ${bad ? "is-down" : "is-up"}">${
      down ? "↓" : "↑"
    } ${abs}</span>`;
  }

  function windowTaskRate(keys) {
    const set = new Set(keys);
    const due = state.tasks.filter((t) => set.has(deadlineDateKey(t.deadline)));
    if (!due.length) return null;
    return due.filter((t) => isTaskDone(t)).length / due.length;
  }

  function buildStatusReport(days) {
    const keys = dateKeysBack(days);
    const prevKeys = dateKeysBack(days * 2).slice(0, days);
    const moodMap = new Map((state.moods || []).map((m) => [m.entry_date, m]));
    const series = [];
    let ewma = null;
    const alpha = 0.45;
    keys.forEach((key) => {
      const entry = moodMap.get(key);
      const score = entry ? moodScore(entry.mood) : null;
      if (score != null) {
        ewma = ewma == null ? score : alpha * score + (1 - alpha) * ewma;
      }
      series.push({
        key,
        score,
        ewma,
        mood: entry ? entry.mood : null,
      });
    });
    const scored = series.filter((d) => d.score != null);
    const last7 = scored.slice(-7).map((d) => d.score);
    const prev7 = scored.slice(-14, -7).map((d) => d.score);
    const avg7 = avg(last7);
    const prevAvg7 = avg(prev7);
    const ewmaPts = series.filter((d) => d.ewma != null);
    const ewmaFirst = ewmaPts.length ? ewmaPts[0].ewma : null;
    const ewmaLast = ewmaPts.length ? ewmaPts[ewmaPts.length - 1].ewma : null;
    const ewmaDelta =
      ewmaFirst == null || ewmaLast == null ? null : ewmaLast - ewmaFirst;
    const negRatio = scored.length
      ? scored.filter((d) => d.score < 0).length / scored.length
      : null;
    const prevMoods = prevKeys.map((k) => moodMap.get(k)).filter(Boolean);
    const prevNegRatio = prevMoods.length
      ? prevMoods.filter((m) => moodScore(m.mood) < 0).length / prevMoods.length
      : null;

    let recoveries = 0;
    let negEpisodes = 0;
    for (let i = 1; i < scored.length; i += 1) {
      if (scored[i - 1].score < 0) {
        negEpisodes += 1;
        if (scored[i].score >= 0) recoveries += 1;
      }
    }
    const recovery = negEpisodes ? recoveries / negEpisodes : null;
    const prevScored = prevKeys
      .map((k) => {
        const entry = moodMap.get(k);
        return entry ? moodScore(entry.mood) : null;
      })
      .filter((n) => n != null);
    let prevRecovery = null;
    if (prevScored.length > 1) {
      let rec = 0;
      let ep = 0;
      for (let i = 1; i < prevScored.length; i += 1) {
        if (prevScored[i - 1] < 0) {
          ep += 1;
          if (prevScored[i] >= 0) rec += 1;
        }
      }
      prevRecovery = ep ? rec / ep : null;
    }

    let changes = 0;
    for (let i = 1; i < scored.length; i += 1) {
      if (scored[i].score !== scored[i - 1].score) changes += 1;
    }
    const negDays = scored.filter((d) => d.score < 0).length;
    const vol = stdev(scored.map((d) => d.score));
    const volIndex = Math.min(1, vol / 2);
    const taskNow = windowTaskRate(keys);
    const taskPrev = windowTaskRate(prevKeys);
    const overall = completionStats();

    return {
      days,
      keys,
      series,
      scored,
      avg7,
      avg7Delta: avg7 == null || prevAvg7 == null ? null : avg7 - prevAvg7,
      ewmaFirst,
      ewmaLast,
      ewmaDelta,
      negRatio,
      negRatioDelta:
        negRatio == null || prevNegRatio == null ? null : negRatio - prevNegRatio,
      recovery,
      recoveryDelta:
        recovery == null || prevRecovery == null ? null : recovery - prevRecovery,
      changes,
      negSustain: scored.length ? negDays / scored.length : null,
      volIndex,
      volLabel: volIndex < 0.35 ? "低" : volIndex < 0.7 ? "中" : "高",
      dist: MOODS.map((m) => {
        const n = scored.filter((d) => d.mood === m.id).length;
        return {
          id: m.id,
          label: m.label,
          n,
          pct: scored.length ? n / scored.length : 0,
        };
      }),
      taskRate: taskNow != null ? taskNow : overall.total ? overall.pct / 100 : null,
      taskDelta: taskNow == null || taskPrev == null ? null : taskNow - taskPrev,
      dailyTasks: keys.map((key) => {
        const due = state.tasks.filter((t) => deadlineDateKey(t.deadline) === key);
        if (!due.length) return { key, pct: null };
        return { key, pct: due.filter((t) => isTaskDone(t)).length / due.length };
      }),
    };
  }

  function renderEwmaChart(report) {
    const w = 520;
    const h = 168;
    const left = 44;
    const right = 12;
    const top = 14;
    const bottom = 34;
    const iw = w - left - right;
    const ih = h - top - bottom;
    const n = report.series.length;
    const xAt = (i) => (n <= 1 ? left + iw / 2 : left + (i / (n - 1)) * iw);
    const yAt = (score) => top + ((2 - score) / 4) * ih;
    const grid = [-2, -1, 0, 1, 2]
      .map((s) => {
        const y = yAt(s);
        const lab = s > 0 ? `+${s}` : String(s);
        return `<line x1="${left}" x2="${w - right}" y1="${y}" y2="${y}" stroke="#edf0f3" />
          <text x="${left - 8}" y="${y + 4}" text-anchor="end" fill="#8a8a94" font-size="11">${lab}</text>`;
      })
      .join("");
    const ewmaPts = report.series
      .map((d, i) => (d.ewma == null ? null : `${xAt(i)},${yAt(d.ewma)}`))
      .filter(Boolean);
    const line = ewmaPts.length
      ? `<polyline fill="none" stroke="#27c4e8" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" points="${ewmaPts.join(
          " "
        )}" />`
      : "";
    const step = n > 16 ? 4 : n > 8 ? 2 : 1;
    const labels = report.series
      .map((d, i) => {
        if (i % step && i !== n - 1) return "";
        return `<text x="${xAt(i)}" y="${h - 8}" text-anchor="middle" fill="#8a8a94" font-size="11">${formatMoodDay(
          d.key
        )}</text>`;
      })
      .join("");
    return `<svg class="status-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="情緒趨勢 EWMA">${grid}${line}${labels}</svg>`;
  }

  function renderTaskBars(report) {
    const w = 520;
    const h = 168;
    const left = 44;
    const right = 12;
    const top = 14;
    const bottom = 34;
    const iw = w - left - right;
    const ih = h - top - bottom;
    const n = report.dailyTasks.length;
    const gap = n > 20 ? 2 : 6;
    const barW = n ? Math.max(4, iw / n - gap) : 8;
    const grid = [0, 0.25, 0.5, 0.75, 1]
      .map((p) => {
        const y = top + (1 - p) * ih;
        return `<line x1="${left}" x2="${w - right}" y1="${y}" y2="${y}" stroke="#edf0f3" />
          <text x="${left - 8}" y="${y + 4}" text-anchor="end" fill="#8a8a94" font-size="11">${Math.round(
          p * 100
        )}%</text>`;
      })
      .join("");
    const bars = report.dailyTasks
      .map((d, i) => {
        if (d.pct == null) return "";
        const x = left + (i + 0.5) * (iw / n) - barW / 2;
        const bh = d.pct * ih;
        const y = top + ih - bh;
        return `<rect x="${x}" y="${y}" width="${barW}" height="${Math.max(
          bh,
          0
        )}" rx="4" fill="#11365C" opacity="0.88" />`;
      })
      .join("");
    const step = n > 16 ? 4 : n > 8 ? 2 : 1;
    const labels = report.dailyTasks
      .map((d, i) => {
        if (i % step && i !== n - 1) return "";
        const x = left + (i + 0.5) * (iw / n);
        return `<text x="${x}" y="${h - 8}" text-anchor="middle" fill="#8a8a94" font-size="11">${formatMoodDay(
          d.key
        )}</text>`;
      })
      .join("");
    return `<svg class="status-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="任務完成度">${grid}${bars}${labels}</svg>`;
  }

  function renderStatusHtml({ selected, stats, level }) {
    if (!selected) {
      return `
        <section class="status-section">
          <div class="task-section-head">
            <div>
              <h2>狀態追蹤</h2>
              <p>請先選擇 Case</p>
            </div>
          </div>
        </section>`;
    }

    const days = Number(state.statusRangeDays) || 14;
    const report = buildStatusReport(days);
    const ewmaTrend = report.ewmaDelta == null
      ? { dir: "flat", label: "資料不足" }
      : Math.abs(report.ewmaDelta) < 0.15
        ? { dir: "flat", label: "持平" }
        : report.ewmaDelta < 0
          ? { dir: "down", label: "下降" }
          : { dir: "up", label: "上升" };
    const rangeOpts = [7, 14, 30]
      .map(
        (n) =>
          `<option value="${n}"${n === days ? " selected" : ""}>近 ${n} 天</option>`
      )
      .join("");
    const distHtml = report.dist
      .map((m) => {
        const pct = Math.max(0, Math.min(100, Math.round((m.pct || 0) * 100)));
        return `
        <li>
          <img src="${moodImg(m.id)}" alt="" />
          <span>${escapeHtml(m.label)}</span>
          <span class="status-dist-track" aria-hidden="true">
            <span class="status-dist-fill status-dist-fill--${escapeAttr(
              m.id
            )}" style="width:${pct}%"></span>
          </span>
          <strong>${pctLabel(m.pct)}</strong>
        </li>`;
      })
      .join("");
    const caseTitle = selected.case_name || ("Case #" + selected.case_id);

    return `
      <section class="status-section">
        <div class="task-section-head">
          <div class="status-title">
            <div class="status-title-avatar">
              <img src="/img/level${level}.jpg" alt="" />
            </div>
            <div>
              <h2>學生情緒與任務追蹤報表</h2>
              <p>學生：${escapeHtml(selected.student_name)} · ${escapeHtml(caseTitle)}</p>
            </div>
          </div>
          <div class="status-head-actions">
            <label class="status-range">
              <span class="sr-only">統計區間</span>
              <select id="status-range" aria-label="統計區間">${rangeOpts}</select>
            </label>
          </div>
        </div>
        <div class="status-kpi">
          <article class="status-card">
            <p class="stat-label">情緒趨勢</p>
            <p class="status-kpi-value is-${ewmaTrend.dir}">${
              ewmaTrend.dir === "down" ? "↓" : ewmaTrend.dir === "up" ? "↑" : "→"
            } ${ewmaTrend.label}</p>
            <p class="stat-sub">EWMA ${signedNum(report.ewmaLast, 1)}</p>
          </article>
          <article class="status-card">
            <p class="stat-label">7日平均情緒</p>
            <p class="status-kpi-value">${signedNum(report.avg7, 1)}</p>
            ${deltaChip(report.avg7Delta)}
          </article>
          <article class="status-card">
            <p class="stat-label">任務完成度</p>
            <p class="status-kpi-value">${pctLabel(report.taskRate)}</p>
            ${deltaChip(report.taskDelta, { asPct: true })}
          </article>
          <article class="status-card">
            <p class="stat-label">負向情緒比例</p>
            <p class="status-kpi-value">${pctLabel(report.negRatio)}</p>
            ${deltaChip(report.negRatioDelta, { invert: true, asPct: true })}
          </article>
          <article class="status-card">
            <p class="stat-label">情緒恢復率</p>
            <p class="status-kpi-value">${pctLabel(report.recovery)}</p>
            ${deltaChip(report.recoveryDelta, { asPct: true })}
          </article>
        </div>
        <div class="status-charts">
          <article class="status-card">
            <div class="status-chart-head">
              <div>
                <p class="stat-label">情緒趨勢</p>
                <p class="stat-sub">EWMA</p>
              </div>
              <p class="status-chart-note">EWMA：${signedNum(
                report.ewmaFirst,
                1
              )} → ${signedNum(report.ewmaLast, 1)}　趨勢：${
                ewmaTrend.dir === "down" ? "↓" : ewmaTrend.dir === "up" ? "↑" : "→"
              } ${ewmaTrend.label}</p>
            </div>
            ${
              report.scored.length
                ? renderEwmaChart(report)
                : `<p class="mood-empty">這段期間還沒有心情紀錄</p>`
            }
          </article>
          <article class="status-card">
            <div class="status-chart-head">
              <div>
                <p class="stat-label">任務完成度</p>
                <p class="stat-sub">依每日截止任務計算 · 整體 ${stats.pct}%</p>
              </div>
            </div>
            ${renderTaskBars(report)}
          </article>
        </div>
        <div class="status-split">
          <article class="status-card">
            <p class="stat-label">情緒狀態分布</p>
            ${
              report.scored.length
                ? `<ul class="status-dist">${distHtml}</ul>`
                : `<p class="mood-empty">尚無分布資料</p>`
            }
          </article>
          <article class="status-card">
            <p class="stat-label">情緒波動</p>
            <div class="status-vol">
              <p>波動程度：<strong>${escapeHtml(report.volLabel)}</strong></p>
              <p>波動指數：<strong>${
                report.scored.length > 1 ? report.volIndex.toFixed(2) : "—"
              }</strong></p>
              <p>情緒變化：<strong>↕ ${report.changes} 次</strong></p>
              <p>負向持續：<strong>${pctLabel(report.negSustain)}</strong></p>
              <p>情緒恢復：<strong>${pctLabel(report.recovery)}</strong></p>
            </div>
          </article>
        </div>
      </section>`;
  }

  function navIcon(kind) {
    const icons = {
      tasks: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/></svg>`,
      done: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 6 9 17l-5-5"/></svg>`,
      expert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.5"/><path d="M5 19a7 7 0 0 1 14 0"/></svg>`,
      parent: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M16 11a3 3 0 1 0-2.8-4"/><path d="M8 11a3 3 0 1 1 2.8-4"/><path d="M3.5 19a5.5 5.5 0 0 1 9.5-3.8"/><path d="M20.5 19a5.5 5.5 0 0 0-9.5-3.8"/></svg>`,
      trophy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 5h8v5a4 4 0 0 1-8 0V5Z"/><path d="M8 7H5a2 2 0 0 0 2 4"/><path d="M16 7h3a2 2 0 0 1-2 4"/><path d="M12 14v3"/><path d="M9 20h6"/></svg>`,
      status: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h4l2.5-6 5 12 2.5-6H21"/></svg>`,
      history: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 12a8 8 0 1 0 2.3-5.7"/><polyline points="4 5 4 9 8 9"/><path d="M12 8v5l3 2"/></svg>`,
    };
    return icons[kind] || icons.tasks;
  }

  function renderLogin() {
    if (typeof window.stopLoginMotion === "function") {
      window.stopLoginMotion();
    }
    document.title = "CosmoMate 共育星球";
    document.body.classList.add("login-active");
    document.body.classList.remove("app-active", "intro-active");
    syncRoleBodyClass(null);

    root.innerHTML = `
      <main class="shell">
        <section class="art" aria-hidden="true">
          <div class="crew" id="crew">
            <div class="char char--purple" data-char="purple">
              <div class="char__body"></div>
              <div class="char__face" data-face>
                <div class="eye eye--ball" data-eye data-max="5"><span class="pupil"></span></div>
                <div class="eye eye--ball" data-eye data-max="5"><span class="pupil"></span></div>
              </div>
            </div>
            <div class="char char--black" data-char="black">
              <div class="char__body"></div>
              <div class="char__face" data-face>
                <div class="eye eye--ball eye--tall" data-eye data-max="4.5"><span class="pupil"></span></div>
                <div class="eye eye--ball eye--tall" data-eye data-max="4.5"><span class="pupil"></span></div>
              </div>
            </div>
            <div class="char char--orange" data-char="orange">
              <div class="char__body"></div>
              <div class="char__face" data-face>
                <div class="eye eye--dot" data-eye data-max="5"><span class="pupil"></span></div>
                <div class="eye eye--dot" data-eye data-max="5"><span class="pupil"></span></div>
                <div class="mouth mouth--smile"></div>
              </div>
            </div>
            <div class="char char--yellow" data-char="yellow">
              <div class="char__body"></div>
              <div class="char__face" data-face>
                <div class="eye eye--dot" data-eye data-max="4.5"><span class="pupil"></span></div>
                <div class="eye eye--dot" data-eye data-max="4.5"><span class="pupil"></span></div>
                <div class="mouth mouth--wavy" data-mouth></div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <form class="form" id="loginForm" autocomplete="on">
            <h1 class="form__title">Welcome back!</h1>
            <p class="form__subtitle">Please enter your details</p>

            <label class="field" data-field="username">
              <span class="field__label">Username</span>
              <div class="field__control">
                <input type="text" id="username" name="username" placeholder="expert001" autocomplete="username" value="expert001" required />
              </div>
            </label>

            <label class="field" data-field="password">
              <span class="field__label">Password</span>
              <div class="field__control">
                <input type="password" id="password" name="password" placeholder="••••••••" autocomplete="current-password" value="password123" required />
                <button type="button" class="toggle-pw" id="togglePw" aria-label="顯示密碼" aria-pressed="false">
                  <svg class="icon-eye" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <svg class="icon-eye-off" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" hidden>
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a3 3 0 0 0 4.2 4.2" />
                    <path d="M9.9 5.1A11 11 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-3.1 4.1" />
                    <path d="M6.1 6.1A18 18 0 0 0 2 12s3.5 7 10 7a10.6 10.6 0 0 0 4.4-1" />
                  </svg>
                </button>
              </div>
            </label>

            <div class="form__row">
              <label class="remember">
                <input type="checkbox" name="remember" />
                <span>Remember for 30 days</span>
              </label>
            </div>

            <p class="form-error" data-error></p>
            <button type="submit" class="btn btn--primary">Log In</button>
            <p class="hint">示範：expert001／parent001／student001／admin001<br />密碼：password123</p>
          </form>
        </section>
      </main>
    `;

    if (typeof window.initLoginMotion === "function") {
      window.initLoginMotion();
    }

    document.getElementById("loginForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      setError("");
      const form = e.target;
      const btn = form.querySelector(".btn--primary");
      const prev = btn.textContent;
      btn.textContent = "Logging in…";
      btn.disabled = true;
      try {
        const data = await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({
            username: form.username.value.trim(),
            password: form.password.value,
          }),
        });
        if (typeof window.stopLoginMotion === "function") {
          window.stopLoginMotion();
        }
        state.token = data.access_token;
        localStorage.setItem(TOKEN_KEY, state.token);
        state.user = await api("/me");
        state.selectedCaseId = null;
        state.filter = "open";
        state.dayFilter = null;
        state.showNotifPanel = false;
        await loadCases();
        await refreshUnread();
        renderApp();
        startPolling();
      } catch (err) {
        setError(err.message);
        btn.textContent = prev;
        btn.disabled = false;
      }
    });
  }

  function renderCalendarHtml() {
    ensureCalMonth();
    const { y, m } = state.calMonth;
    const first = new Date(y, m, 1);
    const startPad = first.getDay();
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const title = `${y}年 ${m + 1}月`;
    const regularKeys = new Set(
      state.tasks
        .filter((t) => !t.is_periodic)
        .map((t) => deadlineDateKey(t.deadline))
        .filter(Boolean)
    );
    const periodicKeys = new Set(
      state.tasks
        .filter((t) => t.is_periodic)
        .map((t) => deadlineDateKey(t.deadline))
        .filter(Boolean)
    );
    const now = new Date();
    const todayKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(
      2,
      "0"
    )}-${String(now.getDate()).padStart(2, "0")}`;

    const dows = ["日", "一", "二", "三", "四", "五", "六"]
      .map((d) => `<div class="cal-dow">${d}</div>`)
      .join("");

    const cells = [];
    for (let i = 0; i < startPad; i += 1) {
      cells.push(`<div class="cal-day muted"></div>`);
    }
    for (let d = 1; d <= daysInMonth; d += 1) {
      const key = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const has = regularKeys.has(key);
      const hasPeriodic = periodicKeys.has(key);
      const isToday = key === todayKey;
      cells.push(
        `<div class="cal-day${has ? " has-deadline" : ""}${
          hasPeriodic ? " has-periodic" : ""
        }${isToday ? " today" : ""}"${isToday ? ' aria-current="date"' : ""}>${d}</div>`
      );
    }

    return `
      <div class="cal-head">
        <h3>${title}</h3>
        <div class="cal-nav">
          <button type="button" id="cal-prev" aria-label="上一月">‹</button>
          <button type="button" id="cal-next" aria-label="下一月">›</button>
        </div>
      </div>
      <div class="cal-grid">${dows}${cells.join("")}</div>
    `;
  }

  function renderApp() {
    if (typeof window.stopLoginMotion === "function") {
      window.stopLoginMotion();
    }
    document.body.classList.remove("login-active", "intro-active");
    document.body.classList.add("app-active");
    ensureCalMonth();

    const user = state.user;
    syncRoleBodyClass(user?.role);
    const canAssign = user.role === "Expert" || user.role === "Parent";
    const canCreateCase = user.role === "Expert";
    const isStudent = user.role === "Student";
    const isExpert = user.role === "Expert";
    if (isStudent && state.filter !== "open" && state.filter !== "achievements") {
      state.filter = "open";
    }
    if (!isExpert && state.filter === "status") {
      state.filter = "open";
    }
    if (state.filter === "done" || state.filter === "expert" || state.filter === "parent") {
      state.filter = state.filter === "done" ? "open" : "history";
    }
    const selected = state.cases.find((c) => c.case_id === state.selectedCaseId);
    const stats = completionStats();
    const tasks = filteredTasks();
    const counts = filterCounts();
    const isAdmin = user.role === "Admin";
    const level = studentLevel(stats.done);
    const navFilters = isStudent ? STUDENT_FILTERS : isExpert ? EXPERT_FILTERS : FILTERS;
    const showAchievements = isStudent && state.filter === "achievements";
    const showStatus = isExpert && state.filter === "status";
    const showHistory = !isStudent && state.filter === "history";
    const showTaskBoard = !showAchievements && !showStatus;

    const caseOptionsHtml = state.cases
      .map(
        (c) => `
                        <option value="${c.case_id}" ${
                          c.case_id === state.selectedCaseId ? "selected" : ""
                        }>
                          ${escapeHtml(c.case_name || `Case #${c.case_id}`)} · ${escapeHtml(
                            c.student_name
                          )}
                        </option>`
      )
      .join("");
    const newCaseOptionHtml = canCreateCase
      ? `<option value="__new__">＋ 新增 Case</option>`
      : "";
    const caseSelectHtml =
      isStudent
        ? ""
        : state.cases.length || canCreateCase
          ? `<select class="dash-case-select" id="case-select" aria-label="選擇 Case">
                      ${
                        state.cases.length
                          ? caseOptionsHtml
                          : `<option value="" disabled selected>尚無 Case</option>`
                      }
                      ${newCaseOptionHtml}
                    </select>`
          : `<span class="stat-sub">${
              isAdmin ? "Admin 請使用 /docs" : "尚無 Case"
            }</span>`;

    root.innerHTML = `
      <div class="dash${state.appEntered ? "" : " fade-in"}${
        state.sidebarOpen ? " sidebar-open" : ""
      }">
        <aside class="dash-sidebar${state.sidebarOpen ? " is-open" : ""}">
          <button
            type="button"
            class="dash-sidebar-toggle"
            id="sidebar-toggle"
            aria-label="${state.sidebarOpen ? "收起側邊欄" : "展開側邊欄"}"
            aria-expanded="${state.sidebarOpen ? "true" : "false"}"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              ${
                state.sidebarOpen
                  ? `<polyline points="15 18 9 12 15 6" />`
                  : `<polyline points="9 18 15 12 9 6" />`
              }
            </svg>
          </button>
          <nav class="dash-nav" aria-label="任務篩選">
            ${navFilters
              .map(
                (f) => `
              <button type="button" class="dash-nav-btn ${
                state.filter === f.id ? "active" : ""
              }" data-filter="${f.id}" aria-label="${escapeAttr(f.label)}">
                ${navIcon(f.icon)}
                <span class="dash-nav-label">${f.label}</span>
                <span class="dash-nav-count">${counts[f.id] ?? 0}</span>
              </button>`
              )
              .join("")}
          </nav>
        </aside>

        <div class="dash-main">
          <header class="dash-top">
            <div class="dash-top-left">
              <div class="dash-brand">
                <img class="dash-brand__logo" src="/img/cosmo-logo-dash.png" alt="COSMOMATE" />
              </div>
              ${caseSelectHtml}
            </div>
            <div class="dash-top-right">
              <span>${escapeHtml(user.display_name)}</span>
              <span class="role-pill">${escapeHtml(user.role)}</span>
              <button type="button" class="dash-icon-btn" id="notif-btn" aria-label="通知">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9"/>
                  <path d="M10 20a2 2 0 0 0 4 0"/>
                </svg>
                ${
                  state.unreadCount > 0
                    ? `<span class="dash-badge">${
                        state.unreadCount > 99 ? "99+" : state.unreadCount
                      }</span>`
                    : ""
                }
              </button>
              <button type="button" class="dash-icon-btn" id="logout-btn" aria-label="登出" title="登出">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
              </button>
            </div>
          </header>

          ${
            state.showNotifPanel
              ? `<div class="notif-panel" id="notif-panel">
                  <div class="notif-panel-head">
                    <strong>通知</strong>
                    <button type="button" class="dash-ghost small" id="mark-all-read">全部已讀</button>
                  </div>
                  <ul class="notif-list">
                    ${
                      state.notifications.length
                        ? state.notifications
                            .map(
                              (n) => `
                          <li class="notif-item ${n.is_read ? "" : "unread"}" data-notif-id="${
                            n.notification_id
                          }" data-case-id="${n.case_id}">
                            <div>${
                              n.type === "task_completed"
                                ? "任務已完成"
                                : "新任務指派"
                            }：${escapeHtml(n.task_title)}</div>
                            <small>${escapeHtml(n.actor_name)}（${escapeHtml(
                              n.actor_role
                            )}）· ${escapeHtml(n.created_at)}</small>
                          </li>`
                            )
                            .join("")
                        : `<li class="empty">目前沒有通知</li>`
                    }
                  </ul>
                </div>`
              : ""
          }

          <div class="dash-body">
            <p class="error" data-error>${escapeHtml(state.error)}</p>
            ${
              isStudent && !showAchievements
                ? `<div class="level-row">
                <article class="student-profile" aria-label="目前等級 ${level}">
                  <div class="stat-card stat-card--level">
                    <img src="/img/level${level}.jpg" alt="" />
                  </div>
                  <p class="student-level-label">Level ${level}</p>
                </article>
              </div>`
                : ""
            }
            ${
              showTaskBoard
                ? `${
                    showHistory
                      ? ""
                      : `<section class="dash-stats">
              <article class="stat-card stat-card--progress">
                <p class="stat-label">所有任務完成度</p>
                <p class="stat-value">${stats.pct}%</p>
                <p class="stat-sub">${stats.done} / ${stats.total} 已完成</p>
                <div class="progress-bar" aria-hidden="true"><span style="width:${
                  stats.pct
                }%"></span></div>
              </article>
              <article class="stat-card stat-card--calendar">
                ${renderCalendarHtml()}
              </article>
              ${renderMoodHtml({ isStudent, selected })}
            </section>`
                  }

            <section class="task-section">
              <div class="task-section-head">
                <div>
                  <h2>${filterLabel(state.filter)}（${
                    state.filter === "open"
                      ? tasksForFilter("open").length + tasksForFilter("done").length
                      : state.filter === "history"
                        ? tasksForFilter("expert").length + tasksForFilter("parent").length
                        : tasks.length
                  }）</h2>
                  <p>${
                    selected
                      ? `${escapeHtml(selected.case_name || `Case #${selected.case_id}`)} · 本案共 ${
                          stats.total
                        } 筆，已完成 ${stats.done}`
                      : "請選擇 Case"
                  }</p>
                </div>
                ${
                  canAssign && selected && !showHistory
                    ? `<button type="button" class="dash-btn" id="assign-btn">${assignLabel(
                        user.role
                      )}</button>`
                    : ""
                }
                ${
                  isExpert && showHistory && selected
                    ? `<button type="button" class="dash-btn danger" id="clear-history-btn">清空</button>`
                    : ""
                }
              </div>
              <div class="task-board" id="open-task-board">
                <h3 class="task-board-title" id="open-task-title">未完成</h3>
                <ul class="task-list" id="task-list"></ul>
              </div>
              <div class="task-board" id="done-task-board" hidden>
                <h3 class="task-board-title" id="done-task-title">已完成</h3>
                <ul class="task-list" id="task-list-done"></ul>
              </div>
            </section>`
                : ""
            }
            ${showAchievements ? renderAchievementsHtml(level) : ""}
            ${
              showStatus
                ? renderStatusHtml({ selected, stats, level })
                : ""
            }
          </div>
        </div>
      </div>
      <div id="modal-root"></div>
    `;

    bindAppEvents(canAssign);
    if (showTaskBoard) {
      renderTasks(tasks);
    }
    if (state.showAssign && canAssign && !showHistory) {
      renderAssignModal();
    }
    if (state.showClearHistory && isExpert && showHistory) {
      renderClearHistoryModal();
    }
    if (state.showNewCase && canCreateCase) {
      renderNewCaseModal();
    }
    state.appEntered = true;
  }

  function bindAppEvents(canAssign) {
    document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
      state.sidebarOpen = !state.sidebarOpen;
      renderApp();
    });

    document.getElementById("logout-btn")?.addEventListener("click", () => {
      if (state._notifOutsideClose) {
        document.removeEventListener("pointerdown", state._notifOutsideClose, true);
        state._notifOutsideClose = null;
      }
      if (state._pollTimer) clearInterval(state._pollTimer);
      state._pollTimer = null;
      state.token = "";
      state.user = null;
      state.cases = [];
      state.tasks = [];
      state.moods = [];
      state.moodPick = null;
      state.moodNote = "";
      state.moodDraftDate = null;
      state.selectedCaseId = null;
      state.notifications = [];
      state.unreadCount = 0;
      state.showNotifPanel = false;
      state.showNewCase = false;
      state.commentTaskId = null;
      state.comments = [];
      state.replyingToId = null;
      state.dayFilter = null;
      state.openTasksExpanded = false;
      state.doneTasksExpanded = false;
      state.expertTasksExpanded = false;
      state.parentTasksExpanded = false;
      state.sidebarOpen = false;
      state.appEntered = false;
      localStorage.removeItem(TOKEN_KEY);
      renderLogin();
    });

    document.getElementById("case-select")?.addEventListener("change", async (e) => {
      if (e.target.value === "__new__") {
        e.target.value = state.selectedCaseId != null ? String(state.selectedCaseId) : "";
        state.showNewCase = true;
        renderNewCaseModal();
        return;
      }
      state.selectedCaseId = Number(e.target.value);
      state.showAssign = false;
      state.editingTaskId = null;
      closeComments();
      state.dayFilter = null;
      state.openTasksExpanded = false;
      state.doneTasksExpanded = false;
      state.expertTasksExpanded = false;
      state.parentTasksExpanded = false;
      state.showClearHistory = false;
      setError("");
      try {
        await loadTasks(state.selectedCaseId);
        renderApp();
      } catch (err) {
        setError(err.message);
      }
    });

    root.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.filter = btn.getAttribute("data-filter");
        // 切換側欄時清掉日曆日期篩選
        state.dayFilter = null;
        closeComments();
        if (state.filter !== "open") {
          state.openTasksExpanded = false;
          state.doneTasksExpanded = false;
          state.showAssign = false;
        }
        if (state.filter !== "history") {
          state.expertTasksExpanded = false;
          state.parentTasksExpanded = false;
          state.showClearHistory = false;
        }
        renderApp();
      });
    });

    document.getElementById("status-range")?.addEventListener("change", (e) => {
      state.statusRangeDays = Number(e.target.value) || 14;
      renderApp();
    });

    document.getElementById("cal-prev")?.addEventListener("click", () => {
      ensureCalMonth();
      let { y, m } = state.calMonth;
      m -= 1;
      if (m < 0) {
        m = 11;
        y -= 1;
      }
      state.calMonth = { y, m };
      renderApp();
    });

    document.getElementById("cal-next")?.addEventListener("click", () => {
      ensureCalMonth();
      let { y, m } = state.calMonth;
      m += 1;
      if (m > 11) {
        m = 0;
        y += 1;
      }
      state.calMonth = { y, m };
      renderApp();
    });

    root.querySelectorAll("[data-mood]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.moodPick = btn.getAttribute("data-mood");
        root.querySelectorAll("[data-mood]").forEach((el) => {
          const on = el.getAttribute("data-mood") === state.moodPick;
          el.classList.toggle("active", on);
          el.setAttribute("aria-pressed", on ? "true" : "false");
        });
      });
    });

    document.getElementById("mood-note")?.addEventListener("input", (e) => {
      state.moodNote = e.target.value;
    });

    document.getElementById("mood-save")?.addEventListener("click", async () => {
      if (!state.selectedCaseId) return;
      if (!state.moodPick) {
        setError("請先選一個心情");
        return;
      }
      const btn = document.getElementById("mood-save");
      const prev = btn?.textContent;
      if (btn) {
        btn.disabled = true;
        btn.textContent = "儲存中…";
      }
      try {
        const saved = await api(`/cases/${state.selectedCaseId}/moods`, {
          method: "PUT",
          body: JSON.stringify({
            mood: state.moodPick,
            note: state.moodNote,
            entry_date: todayKey(),
          }),
        });
        const i = state.moods.findIndex((m) => m.entry_date === saved.entry_date);
        if (i >= 0) state.moods[i] = saved;
        else state.moods.unshift(saved);
        paintMoodWeek();
        setError("");
      } catch (err) {
        setError(err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = prev;
        }
      }
    });

    const openAssign = () => {
      closeComments();
      state.showAssign = true;
      renderAssignModal();
    };
    document.getElementById("assign-btn")?.addEventListener("click", openAssign);

    document.getElementById("clear-history-btn")?.addEventListener("click", () => {
      closeComments();
      state.showClearHistory = true;
      renderClearHistoryModal();
    });

    document.getElementById("notif-btn")?.addEventListener("click", async () => {
      state.showNotifPanel = !state.showNotifPanel;
      if (state.showNotifPanel) {
        try {
          await loadNotifications();
          if (state.selectedCaseId) await loadTasks(state.selectedCaseId);
          await refreshUnread();
        } catch (err) {
          setError(err.message);
        }
      }
      renderApp();
    });

    document.getElementById("mark-all-read")?.addEventListener("click", async () => {
      try {
        await api("/notifications/read", { method: "POST", body: "{}" });
        await refreshUnread();
        await loadNotifications();
        renderApp();
      } catch (err) {
        setError(err.message);
      }
    });

    root.querySelectorAll("[data-notif-id]").forEach((el) => {
      el.addEventListener("click", async () => {
        const id = Number(el.getAttribute("data-notif-id"));
        const caseId = Number(el.getAttribute("data-case-id"));
        try {
          await api("/notifications/read", {
            method: "POST",
            body: JSON.stringify({ ids: [id] }),
          });
          if (caseId && state.cases.some((c) => c.case_id === caseId)) {
            state.selectedCaseId = caseId;
            await loadTasks(caseId);
          }
          await refreshUnread();
          state.showNotifPanel = false;
          renderApp();
        } catch (err) {
          setError(err.message);
        }
      });
    });
    
    // 通知點窗外或面板空白／標題也能關閉
    if (state._notifOutsideClose) {
      document.removeEventListener("pointerdown", state._notifOutsideClose, true);
      state._notifOutsideClose = null;
    }
    if (state.showNotifPanel) {
      const bell = document.getElementById("notif-btn");
      const onDocPointer = (e) => {
        if (bell?.contains(e.target)) return;
        if (e.target.closest("#mark-all-read, [data-notif-id]")) return;
        document.removeEventListener("pointerdown", onDocPointer, true);
        state._notifOutsideClose = null;
        state.showNotifPanel = false;
        renderApp();
      };
      state._notifOutsideClose = onDocPointer;
      setTimeout(() => {
        document.addEventListener("pointerdown", onDocPointer, true);
      }, 0);
    }

    void canAssign;
  }

  function userOption(u) {
    return `<option value="${u.user_id}">${escapeHtml(u.display_name)}（${escapeHtml(
      u.username
    )} · id ${u.user_id}）</option>`;
  }

  async function renderNewCaseModal() {
    const slot = document.getElementById("modal-root");
    if (!slot || !state.showNewCase) {
      if (slot) slot.innerHTML = "";
      return;
    }

    slot.innerHTML = `
      <div class="modal-backdrop" id="new-case-backdrop">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="new-case-title">
          <h3 id="new-case-title">新增 Case</h3>
          <p class="stat-sub">綁定一位 Student 與一位 Parent，本案 Expert 為你。</p>
          <form class="assign-form" id="new-case-form">
            <label>Case 名稱（選填）
              <input name="case_name" placeholder="例如：Case-S004" />
            </label>
            <label>Student
              <select name="student_id" required>
                <option value="">載入中…</option>
              </select>
            </label>
            <label>Parent
              <select name="parent_id" required>
                <option value="">載入中…</option>
              </select>
            </label>
            <p class="error" data-error>${escapeHtml(state.error)}</p>
            <div class="modal-actions">
              <button type="button" class="dash-ghost" id="new-case-cancel">取消</button>
              <button type="submit" class="dash-btn">建立 Case</button>
            </div>
          </form>
        </div>
      </div>
    `;

    const close = () => {
      state.showNewCase = false;
      slot.innerHTML = "";
    };
    document.getElementById("new-case-cancel")?.addEventListener("click", close);
    document.getElementById("new-case-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "new-case-backdrop") close();
    });

    const studentSel = slot.querySelector('select[name="student_id"]');
    const parentSel = slot.querySelector('select[name="parent_id"]');
    try {
      const [students, parents] = await Promise.all([
        api("/users?role=Student"),
        api("/users?role=Parent"),
      ]);
      studentSel.innerHTML =
        `<option value="">請選擇 Student</option>` + students.map(userOption).join("");
      parentSel.innerHTML =
        `<option value="">請選擇 Parent</option>` + parents.map(userOption).join("");
    } catch (err) {
      studentSel.innerHTML = `<option value="">載入失敗</option>`;
      parentSel.innerHTML = `<option value="">載入失敗</option>`;
      const errEl = slot.querySelector("[data-error]");
      if (errEl) errEl.textContent = err.message;
    }

    document.getElementById("new-case-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      setError("");
      const form = new FormData(e.target);
      const studentId = Number(form.get("student_id"));
      const parentId = Number(form.get("parent_id"));
      const caseName = String(form.get("case_name") || "").trim();
      try {
        const created = await api("/cases", {
          method: "POST",
          body: JSON.stringify({
            student_id: studentId,
            parent_id: parentId,
            case_name: caseName || null,
          }),
        });
        state.showNewCase = false;
        state.selectedCaseId = created.case_id;
        await loadCases();
        renderApp();
      } catch (err) {
        setError(err.message);
        const errEl = slot.querySelector("[data-error]");
        if (errEl) errEl.textContent = err.message;
      }
    });
  }

  function renderClearHistoryModal() {
    const slot = document.getElementById("modal-root");
    if (!slot || !state.showClearHistory) {
      if (slot) slot.innerHTML = "";
      return;
    }
    const count =
      tasksForFilter("expert").length + tasksForFilter("parent").length;
    slot.innerHTML = `
      <div class="modal-backdrop" id="clear-history-backdrop">
        <div class="modal modal--confirm" role="dialog" aria-modal="true" aria-labelledby="clear-history-title">
          <h3 id="clear-history-title">清空歷史紀錄？</h3>
          <p class="stat-sub">將永久刪除本案目前 ${count} 筆任務，包含專家與家長指派，無法復原。</p>
          <p class="error" data-error></p>
          <div class="modal-actions">
            <button type="button" class="dash-ghost" id="clear-history-cancel">取消</button>
            <button type="button" class="dash-btn danger" id="clear-history-confirm">永久刪除</button>
          </div>
        </div>
      </div>
    `;

    const close = () => {
      state.showClearHistory = false;
      slot.innerHTML = "";
    };
    document.getElementById("clear-history-cancel")?.addEventListener("click", close);
    document.getElementById("clear-history-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "clear-history-backdrop") close();
    });
    document.getElementById("clear-history-confirm")?.addEventListener("click", async () => {
      const btn = document.getElementById("clear-history-confirm");
      const prev = btn ? btn.textContent : "";
      if (btn) {
        btn.disabled = true;
        btn.textContent = "刪除中…";
      }
      try {
        await api(`/cases/${state.selectedCaseId}/tasks`, { method: "DELETE" });
        state.showClearHistory = false;
        state.commentTaskId = null;
        state.comments = [];
        state.editingTaskId = null;
        await loadTasks(state.selectedCaseId);
        await refreshUnread();
        renderApp();
      } catch (err) {
        setError(err.message);
        const errEl = slot.querySelector("[data-error]");
        if (errEl) errEl.textContent = err.message;
        if (btn) {
          btn.disabled = false;
          btn.textContent = prev;
        }
      }
    });
  }

  function renderAssignModal() {
    const slot = document.getElementById("modal-root");
    if (!slot || !state.showAssign) {
      if (slot) slot.innerHTML = "";
      return;
    }
    const label = assignLabel(state.user.role);
    slot.innerHTML = `
      <div class="modal-backdrop" id="assign-backdrop">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="assign-title">
          <h3 id="assign-title">${label}：新增任務</h3>
          <form class="assign-form" id="assign-form">
            <label>標題
              <input name="title" required placeholder="例如：專注力訓練" />
            </label>
            <div class="row">
              <label>內容
                <textarea name="content" placeholder="說明（選填）"></textarea>
              </label>
              <label>
                <span id="assign-deadline-caption">截止</span>
                <input name="deadline" id="assign-deadline" placeholder="2026-08-20 18:00:00" />
              </label>
            </div>
            <label class="assign-check">
              <input type="checkbox" name="recurring" id="assign-recurring" />
              週期性計畫
            </label>
            <div class="recurring-fields" id="recurring-fields" hidden>
              <div class="row row-3">
                <label>一天多久
                  <input name="daily_duration" placeholder="例如：30 分鐘" />
                </label>
                <label>一周幾次
                  <input name="times_per_week" type="number" min="1" max="7" value="3" />
                </label>
                <label>幾周
                  <input name="weeks" type="number" min="1" max="12" value="4" />
                </label>
              </div>
            </div>
            <p class="error" data-error>${escapeHtml(state.error)}</p>
            <div class="modal-actions">
              <button type="button" class="dash-ghost" id="assign-cancel">取消</button>
              <button type="submit" class="dash-btn">送出 ${label}</button>
            </div>
          </form>
        </div>
      </div>
    `;

    document.getElementById("assign-cancel")?.addEventListener("click", () => {
      state.showAssign = false;
      slot.innerHTML = "";
    });
    document.getElementById("assign-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "assign-backdrop") {
        state.showAssign = false;
        slot.innerHTML = "";
      }
    });

    const recurringBox = document.getElementById("assign-recurring");
    const recurringFields = document.getElementById("recurring-fields");
    const deadlineCaption = document.getElementById("assign-deadline-caption");
    const deadlineInput = document.getElementById("assign-deadline");
    const syncRecurring = () => {
      const on = Boolean(recurringBox?.checked);
      if (recurringFields) recurringFields.hidden = !on;
      if (deadlineCaption) deadlineCaption.textContent = on ? "開始日期（選填）" : "截止";
      if (deadlineInput) {
        deadlineInput.placeholder = on ? "預設今天" : "2026-08-20 18:00:00";
      }
      recurringFields?.querySelectorAll("input").forEach((input) => {
        input.required = on;
      });
    };
    recurringBox?.addEventListener("change", syncRecurring);

    document.getElementById("assign-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      setError("");
      const form = new FormData(e.target);
      const title = String(form.get("title") || "").trim();
      const content = String(form.get("content") || "").trim();
      const deadline = String(form.get("deadline") || "").trim();
      const recurring = Boolean(form.get("recurring"));
      const payload = {
        tasks: [
          {
            title,
            content: content || null,
            deadline: deadline || null,
          },
        ],
      };
      if (recurring) {
        const dailyDuration = String(form.get("daily_duration") || "").trim();
        const timesPerWeek = Number(form.get("times_per_week") || 0);
        const weeks = Number(form.get("weeks") || 0);
        if (!dailyDuration) {
          setError("請填寫一天多久");
          return;
        }
        payload.recurring = {
          daily_duration: dailyDuration,
          times_per_week: timesPerWeek,
          weeks,
        };
      }
      try {
        await api(`/cases/${state.selectedCaseId}/assignments`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.showAssign = false;
        await loadTasks(state.selectedCaseId);
        await refreshUnread();
        renderApp();
      } catch (err) {
        setError(err.message);
        const errEl = slot.querySelector("[data-error]");
        if (errEl) errEl.textContent = err.message;
      }
    });
  }

  function renderTasks(tasks) {
    const openTitle = document.getElementById("open-task-title");
    const doneTitle = document.getElementById("done-task-title");
    const doneBoard = document.getElementById("done-task-board");
    const showOpenBoards = state.filter === "open";
    const showHistoryBoards = state.filter === "history";

    if (!state.selectedCaseId) {
      if (openTitle) openTitle.hidden = true;
      if (doneBoard) doneBoard.hidden = true;
      fillTaskList("task-list", [], null, "請選擇 Case");
      return;
    }

    if (showOpenBoards) {
      const openTasks = tasksForFilter("open");
      const doneTasks = tasksForFilter("done");
      if (openTitle) {
        openTitle.hidden = false;
        openTitle.textContent = `未完成（${openTasks.length}）`;
      }
      if (doneTitle) doneTitle.textContent = `已完成（${doneTasks.length}）`;
      if (doneBoard) doneBoard.hidden = doneTasks.length === 0;
      fillTaskList(
        "task-list",
        openTasks,
        "open",
        "目前沒有未完成任務"
      );
      if (doneTasks.length) {
        fillTaskList("task-list-done", doneTasks, "done");
      }
      return;
    }

    if (showHistoryBoards) {
      const expertTasks = tasksForFilter("expert");
      const parentTasks = tasksForFilter("parent");
      if (openTitle) {
        openTitle.hidden = false;
        openTitle.textContent = `專家指派（${expertTasks.length}）`;
      }
      if (doneTitle) doneTitle.textContent = `家長指派（${parentTasks.length}）`;
      if (doneBoard) doneBoard.hidden = false;
      fillTaskList("task-list", expertTasks, "expert", "目前沒有專家指派任務");
      fillTaskList("task-list-done", parentTasks, "parent", "目前沒有家長指派任務");
      return;
    }

    if (openTitle) openTitle.hidden = true;
    if (doneBoard) doneBoard.hidden = true;
    fillTaskList("task-list", tasks, null);
  }

  function fillTaskList(listId, tasks, stackKind, emptyText) {
    const existing = document.getElementById(listId);
    if (!existing) return;
    const list = existing.cloneNode(false);
    existing.replaceWith(list);
    const isStudent = state.user.role === "Student";
    const myId = state.user.user_id;
    const expandedKey =
      stackKind === "done"
        ? "doneTasksExpanded"
        : stackKind === "expert"
          ? "expertTasksExpanded"
          : stackKind === "parent"
            ? "parentTasksExpanded"
            : "openTasksExpanded";
    const stackLabel =
      stackKind === "done"
        ? "已完成任務"
        : stackKind === "expert"
          ? "專家指派任務"
          : stackKind === "parent"
            ? "家長指派任務"
            : "未完成任務";

    if (!tasks.length) {
      list.className = "task-list";
      list.removeAttribute("data-stack-count");
      list.removeAttribute("role");
      list.removeAttribute("tabindex");
      list.removeAttribute("aria-expanded");
      list.removeAttribute("aria-label");
      list.onclick = null;
      list.onkeydown = null;
      list.innerHTML = `<li class="empty">${emptyText || "此篩選條件下沒有任務"}</li>`;
      return;
    }

    const stackable = Boolean(stackKind) && tasks.length > 1;
    const activeInList = tasks.some(
      (t) => t.task_id === state.commentTaskId || t.task_id === state.editingTaskId
    );
    if (stackable && activeInList) {
      state[expandedKey] = true;
    }
    const collapsed = stackable && !state[expandedKey];
    list.className = `task-list${stackable ? " is-stack" : ""}${
      collapsed ? " is-collapsed" : ""
    }`;
    if (stackable) list.dataset.stackCount = String(tasks.length);
    else list.removeAttribute("data-stack-count");

    const collapseId = `collapse-${stackKind}-tasks`;
    list.innerHTML = `${
      stackable
        ? `<li class="task-stack-bar">
            <button type="button" class="dash-ghost small" id="${collapseId}">收起任務</button>
          </li>`
        : ""
    }${tasks
      .map((t, index) => {
        const done = isTaskDone(t);
        const editing = state.editingTaskId === t.task_id;
        const commentsOpen = state.commentTaskId === t.task_id;
        const count = Number(t.comment_count) || 0;
        const unread = Number(t.unread_comment_count) || 0;
        const roleClass = t.assigned_by_role === "Parent" ? "parent" : "expert";
        const badge =
          unread > 0
            ? `<span class="task-comment-badge">${unread > 99 ? "99+" : unread}</span>`
            : "";
        return `
        <li class="task-row ${done ? "done" : ""}${
          commentsOpen ? " comments-open" : ""
        }" data-task-id="${t.task_id}" style="--stack-i: ${index}">
          <div class="task-row-main">
          <button type="button" class="task-dot ${roleClass}" data-comments="${
            t.task_id
          }" aria-label="留言 ${count} 則" aria-expanded="${commentsOpen ? "true" : "false"}">
            <img src="${taskAvatarSrc(t.task_id)}" alt="" />
            ${badge}
          </button>
          <div class="task-main">
            <h3>${escapeHtml(t.title)}</h3>
            ${
              t.content
                ? `<p>${escapeHtml(
                    t.is_periodic ? periodicContentPreview(t.content) : t.content
                  )}</p>`
                : ""
            }
            <div class="task-meta">
              ${
                isStudent
                  ? ""
                  : `<span class="task-tag task-assigner">${escapeHtml(t.assigned_by_role)}</span>`
              }
              ${t.is_periodic ? `<span class="task-tag periodic">週期</span>` : ""}
              <span>${done ? "已完成" : "未完成"}</span>
              ${t.deadline ? `<span class="task-deadline">截止 ${escapeHtml(t.deadline)}</span>` : ""}
              ${
                isStudent
                  ? ""
                  : `<span class="task-assigner">${escapeHtml(t.assigned_by_name)}</span>`
              }
            </div>
            ${
              editing
                ? `<form class="edit-form" data-edit-form="${t.task_id}">
                    <input name="title" value="${escapeAttr(t.title)}" required />
                    <textarea name="content">${escapeHtml(t.content || "")}</textarea>
                    <input name="deadline" value="${escapeAttr(t.deadline || "")}" placeholder="deadline" />
                    <div class="task-actions">
                      <button type="submit" class="dash-btn small">儲存</button>
                      <button type="button" class="dash-ghost small" data-cancel-edit>取消</button>
                    </div>
                  </form>`
                : ""
            }
          </div>
          <div class="task-side">
            <button type="button" class="task-comment-icon" data-comments="${t.task_id}" aria-label="${count > 0 ? `查看留言 ${count} 則` : "留言"}" title="留言">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M21 12a8.5 8.5 0 0 1-8.5 8.5H8l-4 3v-3.5A8.5 8.5 0 1 1 21 12Z"/>
              </svg>
            </button>
            <div class="task-actions">
              ${
                isStudent && !done
                  ? `<button type="button" class="dash-btn small" data-complete="${t.task_id}">完成</button>`
                  : ""
              }
              ${
                t.assigned_by === myId && !done
                  ? `<button type="button" class="dash-ghost small" data-edit="${t.task_id}">編輯</button>
                     <button type="button" class="dash-btn danger small" data-delete="${t.task_id}">刪除</button>`
                  : ""
              }
            </div>
          </div>
          </div>
          ${commentsOpen ? renderCommentPanelHtml() : ""}
        </li>`;
      })
      .join("")}`;

    if (stackable) {
      const applyStackState = (isCollapsed) => {
        list.classList.toggle("is-collapsed", isCollapsed);
        list.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
        if (isCollapsed) {
          list.setAttribute("role", "button");
          list.setAttribute("tabindex", "0");
          list.setAttribute("aria-label", `${stackLabel}，點一下展開 ${tasks.length} 筆`);
        } else {
          list.removeAttribute("role");
          list.removeAttribute("tabindex");
          list.setAttribute("aria-label", `${stackLabel}已展開，點任務空白處可收起`);
        }
      };

      const toggleStack = (e) => {
        const isCollapsed = list.classList.contains("is-collapsed");
        if (
          !isCollapsed &&
          e.target.closest("button, a, input, textarea, select, form, .task-comments, .edit-form")
        ) {
          return;
        }
        if (isCollapsed) {
          state[expandedKey] = true;
          applyStackState(false);
          return;
        }
        closeComments();
        state.editingTaskId = null;
        state[expandedKey] = false;
        list.querySelectorAll(".comments-open").forEach((row) => {
          row.classList.remove("comments-open");
        });
        list.querySelectorAll(".task-comments, .edit-form").forEach((el) => el.remove());
        applyStackState(true);
      };

      applyStackState(collapsed);
      list.onclick = toggleStack;
      list.onmousedown = (e) => {
        if (list.classList.contains("is-collapsed")) e.preventDefault();
      };
      list.onkeydown = (e) => {
        if (!list.classList.contains("is-collapsed")) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleStack(e);
        }
      };
    } else {
      list.removeAttribute("role");
      list.removeAttribute("tabindex");
      list.removeAttribute("aria-expanded");
      list.removeAttribute("aria-label");
      list.onclick = null;
      list.onkeydown = null;
    }

    document.getElementById(collapseId)?.addEventListener("click", (e) => {
      e.stopPropagation();
      closeComments();
      state.editingTaskId = null;
      state[expandedKey] = false;
      list.querySelectorAll(".comments-open").forEach((row) => {
        row.classList.remove("comments-open");
      });
      list.querySelectorAll(".task-comments, .edit-form").forEach((el) => el.remove());
      list.classList.add("is-collapsed");
      list.setAttribute("aria-expanded", "false");
      list.setAttribute("role", "button");
      list.setAttribute("tabindex", "0");
      list.setAttribute("aria-label", `${stackLabel}，點一下展開 ${tasks.length} 筆`);
    });

    list.querySelectorAll("[data-comments]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const taskId = Number(btn.getAttribute("data-comments"));
        await toggleComments(taskId);
      });
    });

    bindCommentPanel(list);

    list.querySelectorAll("[data-complete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        setError("");
        try {
          await api(`/tasks/${btn.getAttribute("data-complete")}/complete`, {
            method: "POST",
          });
          await loadTasks(state.selectedCaseId);
          await refreshUnread();
          renderApp();
        } catch (err) {
          setError(err.message);
        }
      });
    });

    list.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("確定刪除此任務？")) return;
        setError("");
        try {
          await api(`/tasks/${btn.getAttribute("data-delete")}`, { method: "DELETE" });
          await loadTasks(state.selectedCaseId);
          renderApp();
        } catch (err) {
          setError(err.message);
        }
      });
    });

    list.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.editingTaskId = Number(btn.getAttribute("data-edit"));
        renderApp();
      });
    });

    list.querySelectorAll("[data-cancel-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.editingTaskId = null;
        renderApp();
      });
    });

    list.querySelectorAll("[data-edit-form]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        setError("");
        const taskId = form.getAttribute("data-edit-form");
        const fd = new FormData(form);
        try {
          await api(`/tasks/${taskId}`, {
            method: "PATCH",
            body: JSON.stringify({
              title: String(fd.get("title") || "").trim(),
              content: String(fd.get("content") || "").trim() || null,
              deadline: String(fd.get("deadline") || "").trim() || null,
            }),
          });
          state.editingTaskId = null;
          await loadTasks(state.selectedCaseId);
          renderApp();
        } catch (err) {
          setError(err.message);
        }
      });
    });
  }

  function canWriteComments() {
    const role = state.user?.role;
    return role === "Expert" || role === "Parent";
  }

  function closeComments() {
    state.commentTaskId = null;
    state.comments = [];
    state.replyingToId = null;
  }

  async function toggleComments(taskId) {
    if (state.commentTaskId === taskId) {
      closeComments();
      renderTasks(filteredTasks());
      return;
    }
    setError("");
    state.showAssign = false;
    state.showNewCase = false;
    state.showClearHistory = false;
    state.commentTaskId = taskId;
    state.replyingToId = null;
    try {
      state.comments = await api(`/tasks/${taskId}/comments`);
      const task = state.tasks.find((item) => item.task_id === taskId);
      if (task) task.unread_comment_count = 0;
      renderTasks(filteredTasks());
    } catch (err) {
      closeComments();
      setError(err.message);
    }
  }

  function formatCommentTime(value) {
    const text = String(value || "");
    return text.replace("T", " ").slice(0, 16);
  }

  function renderCommentItem(comment, canWrite, isReply) {
    const replyOpen = canWrite && !isReply && state.replyingToId === comment.comment_id;
    const replies = (comment.replies || [])
      .map((reply) => renderCommentItem(reply, canWrite, true))
      .join("");
    return `
      <li class="comment-item${isReply ? " is-reply" : ""}">
        <div class="comment-head">
          <span class="task-tag">${escapeHtml(comment.author_role)}</span>
          <strong>${escapeHtml(comment.author_name)}</strong>
          <small>${escapeHtml(formatCommentTime(comment.created_at))}</small>
        </div>
        <p class="comment-body">${escapeHtml(comment.content)}</p>
        ${
          canWrite && !isReply
            ? `<button type="button" class="dash-ghost small" data-reply="${comment.comment_id}">回覆</button>`
            : ""
        }
        ${
          replyOpen
            ? `<form class="comment-form" data-reply-form="${comment.comment_id}">
                <textarea name="content" required placeholder="回覆這則留言"></textarea>
                <div class="modal-actions">
                  <button type="button" class="dash-ghost small" data-cancel-reply>取消</button>
                  <button type="submit" class="dash-btn small">送出回覆</button>
                </div>
              </form>`
            : ""
        }
        ${replies ? `<ul class="comment-replies">${replies}</ul>` : ""}
      </li>`;
  }

  function renderCommentPanelHtml() {
    const canWrite = canWriteComments();
    const thread = state.comments.length
      ? `<ul class="comment-thread">${state.comments
          .map((c) => renderCommentItem(c, canWrite, false))
          .join("")}</ul>`
      : `<p class="empty">尚無留言</p>`;
    return `
      <div class="task-comments">
        ${
          canWrite
            ? `<p class="stat-sub">專家與家長可互相查看與回覆；學生只能閱讀。</p>`
            : `<p class="stat-sub">僅供閱讀，無法留言或回覆。</p>`
        }
        ${thread}
        ${
          canWrite
            ? `<form class="comment-form" id="comment-form">
                <label>新增留言
                  <textarea name="content" required placeholder="寫下給對方看的留言"></textarea>
                </label>
                <p class="error" data-error>${escapeHtml(state.error)}</p>
                <div class="modal-actions">
                  <button type="submit" class="dash-btn small">送出留言</button>
                </div>
              </form>`
            : `<p class="error" data-error>${escapeHtml(state.error)}</p>`
        }
      </div>`;
  }

  function bindCommentPanel(rootEl) {
    const panel = rootEl.querySelector(".task-comments");
    if (!panel) return;

    const refreshTasks = async () => {
      closeComments();
      if (state.selectedCaseId) await loadTasks(state.selectedCaseId);
      renderTasks(filteredTasks());
    };

    const postComment = async (content, parentId) => {
      setError("");
      await api(`/tasks/${state.commentTaskId}/comments`, {
        method: "POST",
        body: JSON.stringify({
          content,
          parent_comment_id: parentId || null,
        }),
      });
      await refreshTasks();
    };

    document.getElementById("comment-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = new FormData(e.target);
      const content = String(form.get("content") || "").trim();
      if (!content) return;
      try {
        await postComment(content, null);
      } catch (err) {
        setError(err.message);
      }
    });

    panel.querySelectorAll("[data-reply]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.replyingToId = Number(btn.getAttribute("data-reply"));
        renderTasks(filteredTasks());
      });
    });

    panel.querySelectorAll("[data-cancel-reply]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.replyingToId = null;
        renderTasks(filteredTasks());
      });
    });

    panel.querySelectorAll("[data-reply-form]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const parentId = Number(form.getAttribute("data-reply-form"));
        const fd = new FormData(form);
        const content = String(fd.get("content") || "").trim();
        if (!content) return;
        try {
          await postComment(content, parentId);
        } catch (err) {
          setError(err.message);
        }
      });
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("'", "&#39;");
  }

  bootstrap();
})();
