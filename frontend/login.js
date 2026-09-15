/**
 * Login character motion (from WeStud-style demo).
 * Call window.initLoginMotion() after login DOM is mounted.
 */
window.initLoginMotion = function initLoginMotion() {
  const art = document.querySelector(".art");
  const crew = document.getElementById("crew");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const togglePw = document.getElementById("togglePw");

  if (!art || !crew || !usernameInput || !passwordInput || !togglePw) {
    return;
  }

  const chars = {
    purple: document.querySelector('[data-char="purple"]'),
    black: document.querySelector('[data-char="black"]'),
    orange: document.querySelector('[data-char="orange"]'),
    yellow: document.querySelector('[data-char="yellow"]'),
  };

  const faces = {
    purple: chars.purple.querySelector("[data-face]"),
    black: chars.black.querySelector("[data-face]"),
    orange: chars.orange.querySelector("[data-face]"),
    yellow: chars.yellow.querySelector("[data-face]"),
  };

  const eyes = [...crew.querySelectorAll("[data-eye]")].map((eye) => ({
    el: eye,
    pupil: eye.querySelector(".pupil"),
    max: Number(eye.dataset.max) || 5,
  }));

  const ballEyes = eyes.filter(({ el }) => el.classList.contains("eye--ball"));

  const motion = {
    purple: { skew: 0, x: 0, stretch: 1, faceX: 0, faceY: 0 },
    black: { skew: 0, x: 0, faceX: 0, faceY: 0 },
    orange: { skew: 0, faceX: 0, faceY: 0 },
    yellow: { skew: 0, faceX: 0, faceY: 0 },
  };

  let mouseX = window.innerWidth * 0.35;
  let mouseY = window.innerHeight * 0.45;
  let mode = "idle";
  let lookingAtBuddy = false;
  let buddyTimer = 0;
  let peekTimer = 0;
  let peeking = false;
  let showPassword = false;
  let rafId = 0;
  let stopped = false;

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const lerp = (a, b, t) => a + (b - a) * t;

  function eyeOffset(el, max) {
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const dx = mouseX - cx;
    const dy = mouseY - cy;
    const angle = Math.atan2(dy, dx);
    const dist = Math.min(Math.hypot(dx, dy), max * 14) / 14;
    const mag = Math.min(dist, max);
    return { x: Math.cos(angle) * mag, y: Math.sin(angle) * mag };
  }

  function bodyFromMouse(el) {
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 3;
    const dx = mouseX - cx;
    const dy = mouseY - cy;
    return {
      faceX: clamp(dx / 20, -15, 15),
      faceY: clamp(dy / 30, -10, 10),
      skew: clamp(-dx / 120, -6, 6),
    };
  }

  function setPupils() {
    eyes.forEach(({ el, pupil, max }) => {
      const pos = eyeOffset(el, max);
      pupil.style.transform = `translate(${pos.x}px, ${pos.y}px)`;
    });
  }

  function setFieldFocus(name) {
    document.querySelectorAll(".field").forEach((field) => {
      field.classList.toggle("is-focused", !!name && field.dataset.field === name);
    });
  }

  function resolveMode() {
    const pwdFocused = document.activeElement === passwordInput;
    const userFocused = document.activeElement === usernameInput;
    const hasPwd = passwordInput.value.length > 0;

    if (pwdFocused || (hasPwd && showPassword)) {
      mode = showPassword && hasPwd ? "peek" : "password";
      art.dataset.mode = mode;
      setFieldFocus(pwdFocused ? "password" : userFocused ? "username" : "password");
      return;
    }

    if (userFocused) {
      mode = "email";
      art.dataset.mode = "email";
      setFieldFocus("username");
      return;
    }

    if (hasPwd && !showPassword) {
      mode = "shy";
      art.dataset.mode = "shy";
      setFieldFocus("");
      return;
    }

    mode = "idle";
    art.dataset.mode = "";
    setFieldFocus("");
  }

  function targetMotion() {
    const p = bodyFromMouse(chars.purple);
    const b = bodyFromMouse(chars.black);
    const o = bodyFromMouse(chars.orange);
    const y = bodyFromMouse(chars.yellow);

    const leanIn = mode === "email" || mode === "shy";

    if (leanIn) {
      return {
        purple: {
          skew: p.skew - 10,
          x: 28,
          stretch: 1.08,
          faceX: clamp(p.faceX * 1.4, -8, 18),
          faceY: p.faceY + 2,
        },
        black: {
          skew: b.skew * 1.4,
          x: 4,
          faceX: b.faceX + 4,
          faceY: b.faceY,
        },
        orange: { skew: o.skew + 2, faceX: o.faceX + 6, faceY: o.faceY },
        yellow: { skew: y.skew + 2, faceX: y.faceX + 6, faceY: y.faceY },
      };
    }

    return {
      purple: { skew: p.skew, x: 0, stretch: 1, faceX: p.faceX, faceY: p.faceY },
      black: { skew: b.skew, x: 0, faceX: b.faceX, faceY: b.faceY },
      orange: { skew: o.skew, faceX: o.faceX, faceY: o.faceY },
      yellow: { skew: y.skew, faceX: y.faceX, faceY: y.faceY },
    };
  }

  function applyTransforms(t) {
    const ease = 0.18;

    motion.purple.skew = lerp(motion.purple.skew, t.purple.skew, ease);
    motion.purple.x = lerp(motion.purple.x, t.purple.x, ease);
    motion.purple.stretch = lerp(motion.purple.stretch, t.purple.stretch, ease);
    motion.purple.faceX = lerp(motion.purple.faceX, t.purple.faceX, ease);
    motion.purple.faceY = lerp(motion.purple.faceY, t.purple.faceY, ease);

    motion.black.skew = lerp(motion.black.skew, t.black.skew, ease);
    motion.black.x = lerp(motion.black.x, t.black.x, ease);
    motion.black.faceX = lerp(motion.black.faceX, t.black.faceX, ease);
    motion.black.faceY = lerp(motion.black.faceY, t.black.faceY, ease);

    motion.orange.skew = lerp(motion.orange.skew, t.orange.skew, ease);
    motion.orange.faceX = lerp(motion.orange.faceX, t.orange.faceX, ease);
    motion.orange.faceY = lerp(motion.orange.faceY, t.orange.faceY, ease);

    motion.yellow.skew = lerp(motion.yellow.skew, t.yellow.skew, ease);
    motion.yellow.faceX = lerp(motion.yellow.faceX, t.yellow.faceX, ease);
    motion.yellow.faceY = lerp(motion.yellow.faceY, t.yellow.faceY, ease);

    chars.purple.style.transform = `translateX(${motion.purple.x}px) skewX(${motion.purple.skew}deg) scaleY(${motion.purple.stretch})`;
    chars.black.style.transform = `translateX(${motion.black.x}px) skewX(${motion.black.skew}deg)`;
    chars.orange.style.transform = `skewX(${motion.orange.skew}deg)`;
    chars.yellow.style.transform = `skewX(${motion.yellow.skew}deg)`;

    faces.purple.style.transform = `translate(${motion.purple.faceX}px, ${motion.purple.faceY}px)`;
    faces.black.style.transform = `translate(${motion.black.faceX}px, ${motion.black.faceY}px)`;
    faces.orange.style.transform = `translate(${motion.orange.faceX}px, ${motion.orange.faceY}px)`;
    faces.yellow.style.transform = `translate(${motion.yellow.faceX}px, ${motion.yellow.faceY}px)`;
    setPupils();
  }

  function tick() {
    if (stopped || !document.getElementById("crew")) {
      stopped = true;
      return;
    }
    applyTransforms(targetMotion());
    rafId = requestAnimationFrame(tick);
  }

  function blink(eyeList) {
    eyeList.forEach(({ el }) => {
      const h = el.offsetHeight;
      el.style.transition = "height 0.08s ease";
      el.style.height = "2px";
      setTimeout(() => {
        el.style.height = `${h}px`;
      }, 90);
    });
  }

  function scheduleBlink(group, lo = 2800, hi = 5200) {
    const delay = lo + Math.random() * (hi - lo);
    setTimeout(() => {
      if (stopped) return;
      if (mode !== "password" && mode !== "peek") blink(group);
      scheduleBlink(group, lo, hi);
    }, delay);
  }

  function schedulePeek() {
    clearTimeout(peekTimer);
    if (mode !== "peek") {
      peeking = false;
      return;
    }
    peekTimer = setTimeout(() => {
      peeking = true;
      setTimeout(() => {
        peeking = false;
        schedulePeek();
      }, 700);
    }, 1800 + Math.random() * 2200);
  }

  function trackPointer(e) {
    if (stopped) return;
    if (typeof e.clientX !== "number") return;
    mouseX = e.clientX;
    mouseY = e.clientY;
  }

  const trackOpts = { capture: true, passive: true };
  document.addEventListener("mousemove", trackPointer, trackOpts);
  document.addEventListener("pointermove", trackPointer, trackOpts);
  document.addEventListener("pointerdown", trackPointer, trackOpts);
  window.addEventListener("mousemove", trackPointer, trackOpts);

  usernameInput.addEventListener("focus", () => {
    resolveMode();
    lookingAtBuddy = true;
    clearTimeout(buddyTimer);
    buddyTimer = setTimeout(() => {
      lookingAtBuddy = false;
    }, 750);
  });

  usernameInput.addEventListener("input", () => {
    resolveMode();
    lookingAtBuddy = true;
    clearTimeout(buddyTimer);
    buddyTimer = setTimeout(() => {
      lookingAtBuddy = false;
    }, 600);
  });

  usernameInput.addEventListener("blur", () => {
    lookingAtBuddy = false;
    resolveMode();
  });

  passwordInput.addEventListener("focus", () => {
    resolveMode();
    schedulePeek();
  });

  passwordInput.addEventListener("input", () => {
    resolveMode();
    schedulePeek();
  });

  passwordInput.addEventListener("blur", () => {
    resolveMode();
    schedulePeek();
  });

  togglePw.addEventListener("click", () => {
    showPassword = passwordInput.type === "password";
    passwordInput.type = showPassword ? "text" : "password";
    togglePw.setAttribute("aria-pressed", String(showPassword));
    togglePw.setAttribute("aria-label", showPassword ? "隱藏密碼" : "顯示密碼");
    togglePw.querySelector(".icon-eye").hidden = showPassword;
    togglePw.querySelector(".icon-eye-off").hidden = !showPassword;
    resolveMode();
    schedulePeek();
  });

  const purpleBalls = ballEyes.filter(({ el }) => chars.purple.contains(el));
  const blackBalls = ballEyes.filter(({ el }) => chars.black.contains(el));
  scheduleBlink(purpleBalls);
  scheduleBlink(blackBalls, 3200, 6000);
  resolveMode();
  cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(tick);

  window.stopLoginMotion = () => {
    stopped = true;
    cancelAnimationFrame(rafId);
    document.removeEventListener("mousemove", trackPointer, trackOpts);
    document.removeEventListener("pointermove", trackPointer, trackOpts);
    document.removeEventListener("pointerdown", trackPointer, trackOpts);
    window.removeEventListener("mousemove", trackPointer, trackOpts);
  };
};
