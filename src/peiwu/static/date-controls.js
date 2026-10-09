(() => {
  const ids = ["as-of", "ledger-recorded-at", "valid-from", "valid-until"];
  const dateFields = new Map();
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
  const pad = value => String(value).padStart(2, "0");
  const civil = value => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!match) return null;
    const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
    const date = new Date(0); date.setUTCHours(0, 0, 0, 0); date.setUTCFullYear(year, month - 1, day);
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
    return { year, month, day };
  };
  const iso = ({ year, month, day }) => `${String(year).padStart(4, "0")}-${pad(month)}-${pad(day)}`;
  const addDays = (part, amount) => {
    const date = new Date(0); date.setUTCHours(0, 0, 0, 0); date.setUTCFullYear(part.year, part.month - 1, part.day + amount);
    return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1, day: date.getUTCDate() };
  };
  const monthDays = (year, month) => { const date = new Date(0); date.setUTCHours(0, 0, 0, 0); date.setUTCFullYear(year, month, 0); return date.getUTCDate(); };
  let openState = null;

  function sync(field) {
    const entry = dateFields.get(field); if (!entry) return;
    entry.text.value = field.value;
    entry.text.setAttribute("aria-invalid", String(!field.validity.valid));
    entry.text.setAttribute("aria-describedby", field.getAttribute("aria-describedby") || "");
  }
  function syncAll() { for (const field of dateFields.keys()) sync(field); }
  function commit(field, value, dispatch = true) {
    const entry = dateFields.get(field); if (!entry) return;
    const changed = field.value !== value;
    field.value = value;
    field.setCustomValidity("");
    entry.text.value = value;
    entry.text.setAttribute("aria-invalid", String(!field.validity.valid));
    if (dispatch && changed) {
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  function available(field, value) { return (!field.min || value >= field.min) && (!field.max || value <= field.max); }
  function labelDate(value) {
    const part = civil(value);
    return part ? `${part.year}年${part.month}月${part.day}日` : "";
  }
  function setOpen(state) {
    if (openState === state) return;
    if (openState) close(false);
    openState = state; state.epoch++;
    const { panel, field, text, month, year } = state;
    state.trigger.setAttribute("aria-expanded", "true");
    panel.hidden = false; panel.dataset.state = "open";
    if (reducedMotion.matches) panel.getAnimations().forEach(animation => animation.cancel());
    panel.setAttribute("aria-label", `${field.labels?.[0]?.childNodes?.[0]?.textContent?.trim() || "日期"}选择器`);
    const current = civil(field.value) || civil(text.value) || civil(new Date().toISOString().slice(0, 10));
    state.viewYear = current.year; state.viewMonth = current.month; state.active = current.day;
    month.value = String(current.month); year.value = String(current.year);
    render(state);
    position(state);
    state.anchor = (() => { const rect = text.getBoundingClientRect(); return {
      left: rect.left, top: rect.top, width: rect.width, height: rect.height,
      viewportWidth: innerWidth, viewportHeight: innerHeight,
    }; })();
    if (!reducedMotion.matches) {
      const animation = panel.animate([{ opacity: 0, transform: "translateY(4px) scale(.98)" }, { opacity: 1, transform: "translateY(0) scale(1)" }], { duration: 160, easing: "cubic-bezier(.2,.8,.2,1)" });
      state.animation = animation; animation.onfinish = () => { if (openState === state && state.epoch === state.animationEpoch) panel.style.transform = ""; };
      state.animationEpoch = state.epoch;
    }
    const active = panel.querySelector(`[data-day="${state.active}"]`);
    (active || panel.querySelector(".date-day:not(:disabled)") || text).focus({ preventScroll: true });
  }
  function close(restore = true, immediate = false) {
    const state = openState; if (!state) return;
    openState = null; const epoch = ++state.epoch;
    state.trigger.setAttribute("aria-expanded", "false");
    state.animation?.cancel(); state.animation = null;
    state.panel.dataset.state = "closing";
    const finish = () => { if (state.epoch !== epoch || openState === state) return; state.panel.hidden = true; state.panel.dataset.state = "closed"; state.panel.style.transform = ""; };
    if (immediate || reducedMotion.matches) { state.panel.hidden = true; state.panel.dataset.state = "closed"; state.panel.style.transform = ""; }
    else {
      const animation = state.panel.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 100, easing: "ease-out" });
      state.animation = animation; animation.onfinish = finish;
    }
    if (restore && state.text.isConnected) queueMicrotask(() => state.text.focus({ preventScroll: true }));
  }
  function position(state) {
    const anchor = state.text.getBoundingClientRect(), panel = state.panel;
    const width = Math.min(328, window.innerWidth - 16);
    panel.style.width = `${width}px`;
    const left = Math.max(8, Math.min(anchor.left, window.innerWidth - width - 8));
    const height = Math.min(430, panel.scrollHeight || 390);
    const below = window.innerHeight - anchor.bottom;
    const top = below >= Math.min(height, 360) || below >= anchor.top ? anchor.bottom + 6 : Math.max(8, anchor.top - height - 6);
    panel.dataset.side = top < anchor.top ? "top" : "bottom";
    panel.style.left = `${left}px`; panel.style.top = `${top}px`;
  }
  function anchorChanged(state) {
    const rect = state.text.getBoundingClientRect();
    return !state.anchor || state.anchor.viewportWidth !== innerWidth || state.anchor.viewportHeight !== innerHeight
      || Math.abs(rect.left - state.anchor.left) > 1 || Math.abs(rect.top - state.anchor.top) > 1
      || Math.abs(rect.width - state.anchor.width) > 1 || Math.abs(rect.height - state.anchor.height) > 1;
  }
  function dismissIfAnchorChanged() {
    if (openState && anchorChanged(openState)) close(false, true);
  }
  function render(state) {
    const { grid, month, year, field } = state;
    month.value = String(state.viewMonth); year.value = String(state.viewYear);
    const first = { year: state.viewYear, month: state.viewMonth, day: 1 };
    const utc = new Date(0); utc.setUTCHours(0, 0, 0, 0); utc.setUTCFullYear(first.year, first.month - 1, 1);
    const mondayOffset = (utc.getUTCDay() + 6) % 7;
    const count = monthDays(first.year, first.month), selected = civil(field.value);
    grid.replaceChildren();
    for (const name of weekdays) { const heading = document.createElement("span"); heading.className = "date-weekday"; heading.textContent = name; grid.append(heading); }
    for (let index = 0; index < 42; index++) {
      const day = index - mondayOffset + 1;
      const button = document.createElement("button"); button.type = "button"; button.className = "date-day";
      if (day < 1 || day > count) { button.disabled = true; button.tabIndex = -1; button.setAttribute("aria-hidden", "true"); grid.append(button); continue; }
      const dateValue = iso({ year: first.year, month: first.month, day });
      button.dataset.day = String(day); button.textContent = String(day); button.tabIndex = day === state.active ? 0 : -1;
      button.setAttribute("aria-label", labelDate(dateValue)); button.setAttribute("aria-pressed", String(selected?.year === first.year && selected.month === first.month && selected.day === day));
      button.disabled = !available(field, dateValue);
      button.addEventListener("click", () => { if (!button.disabled) { commit(field, dateValue); close(true); } });
      grid.append(button);
    }
  }
  function shiftMonth(state, amount) {
    const absolute = state.viewYear * 12 + state.viewMonth - 1 + amount;
    state.viewYear = Math.floor(absolute / 12); state.viewMonth = ((absolute % 12) + 12) % 12 + 1;
    state.active = Math.min(state.active, monthDays(state.viewYear, state.viewMonth)); render(state);
  }
  function onKey(event, state) {
    if (event.key === "Escape") { event.preventDefault(); close(true); return; }
    if ((event.key === "Enter" || event.key === " ") && event.target.matches(".date-year,.date-month")) {
      event.preventDefault(); event.stopPropagation(); return;
    }
    if (event.key === "Tab") {
      const candidates = [...document.querySelectorAll("a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex='-1'])")].filter(el => !state.panel.contains(el) && el.getClientRects().length);
      const index = candidates.indexOf(state.text), target = candidates[index + (event.shiftKey ? -1 : 1)];
      event.preventDefault(); close(false); target?.focus(); return;
    }
    if ((event.key === "ArrowLeft" || event.key === "ArrowRight" || event.key === "ArrowUp" || event.key === "ArrowDown") && event.target.matches(".date-day")) {
      event.preventDefault(); const delta = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : event.key === "ArrowUp" ? -7 : 7;
      const next = addDays({ year: state.viewYear, month: state.viewMonth, day: state.active }, delta);
      state.viewYear = next.year; state.viewMonth = next.month; state.active = next.day; render(state); state.panel.querySelector(`[data-day="${next.day}"]`)?.focus({ preventScroll: true }); return;
    }
    if ((event.key === "Home" || event.key === "End") && event.target.matches(".date-day")) {
      event.preventDefault(); const weekday = (new Date(0)); weekday.setUTCHours(0, 0, 0, 0); weekday.setUTCFullYear(state.viewYear, state.viewMonth - 1, state.active);
      const mondayOffset = (weekday.getUTCDay() + 6) % 7;
      const next = addDays({ year: state.viewYear, month: state.viewMonth, day: state.active }, event.key === "Home" ? -mondayOffset : 6 - mondayOffset);
      state.viewYear = next.year; state.viewMonth = next.month; state.active = next.day; render(state); state.panel.querySelector(`[data-day="${next.day}"]`)?.focus({ preventScroll: true }); return;
    }
    if (event.key === "PageUp" || event.key === "PageDown") { event.preventDefault(); shiftMonth(state, (event.key === "PageUp" ? -1 : 1) * (event.shiftKey ? 12 : 1)); const day = state.panel.querySelector(`[data-day="${state.active}"]`); day?.focus({ preventScroll: true }); return; }
    if (event.key === "Enter" || event.key === " ") {
      const day = event.target.closest("[data-day]");
      if (day && !day.disabled) { event.preventDefault(); day.click(); }
    }
  }
  function enhance(field) {
    if (!field || dateFields.has(field)) return;
    const shell = document.createElement("span"); shell.className = "date-shell";
    const text = document.createElement("input"); text.type = "text"; text.className = "date-text"; text.inputMode = "numeric"; text.autocomplete = "off"; text.spellcheck = false;
    text.placeholder = "YYYY-MM-DD"; text.setAttribute("aria-label", `${field.labels?.[0]?.childNodes?.[0]?.textContent?.trim() || "日期"}，输入 YYYY-MM-DD`);
    const trigger = document.createElement("button"); trigger.type = "button"; trigger.className = "date-trigger"; trigger.setAttribute("aria-label", "打开日期日历"); trigger.setAttribute("aria-haspopup", "dialog"); trigger.setAttribute("aria-expanded", "false");
    trigger.innerHTML = "<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='3.5' y='5.5' width='17' height='15' rx='2'/><path d='M7.5 3.5v4M16.5 3.5v4M3.5 10h17'/></svg>";
    const panel = document.createElement("section"); panel.className = "date-panel"; panel.hidden = true; panel.dataset.state = "closed"; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "false");
    const header = document.createElement("div"); header.className = "date-header";
    const previous = document.createElement("button"); previous.type = "button"; previous.className = "date-nav"; previous.textContent = "‹"; previous.setAttribute("aria-label", "上个月");
    const next = document.createElement("button"); next.type = "button"; next.className = "date-nav"; next.textContent = "›"; next.setAttribute("aria-label", "下个月");
    const month = document.createElement("select"); month.className = "date-month"; month.setAttribute("aria-label", "月份");
    for (let index = 1; index <= 12; index++) { const option = document.createElement("option"); option.value = String(index); option.textContent = `${index}月`; month.append(option); }
    const year = document.createElement("input"); year.type = "number"; year.className = "date-year"; year.min = "0001"; year.max = "9999"; year.setAttribute("aria-label", "年份");
    header.append(previous, month, year, next);
    const grid = document.createElement("div"); grid.className = "date-grid";
    const actions = document.createElement("div"); actions.className = "date-actions";
    const today = document.createElement("button"); today.type = "button"; today.className = "date-today"; today.textContent = "今天";
    const clear = document.createElement("button"); clear.type = "button"; clear.className = "date-clear"; clear.textContent = "清除"; clear.hidden = field.required;
    actions.append(today, clear); panel.append(header, grid, actions);
    const parent = field.parentElement;
    parent.insertBefore(shell, field); shell.append(field, text, trigger, panel);
    field.classList.add("date-native"); field.tabIndex = -1; field.setAttribute("aria-hidden", "true"); field.required = field.required;
    const state = { field, shell, text, trigger, panel, month, year, grid, epoch: 0, animation: null, active: 1, viewYear: 2000, viewMonth: 1 };
    dateFields.set(field, state); sync(field);
    if (typeof ResizeObserver === "function") new ResizeObserver(() => { if (openState === state) close(false, true); }).observe(text);
    field.addEventListener("input", () => sync(field)); field.addEventListener("change", () => sync(field));
    text.addEventListener("input", () => {
      const value = text.value.trim();
      const previous = field.value;
      if (!value) { field.setCustomValidity(""); field.value = ""; sync(field); if (previous) field.dispatchEvent(new Event("input", { bubbles: true })); return; }
      const parsed = civil(value);
      if (parsed && available(field, value)) { field.setCustomValidity(""); if (field.value !== value) { field.value = value; field.dispatchEvent(new Event("input", { bubbles: true })); } text.setAttribute("aria-invalid", String(!field.validity.valid)); }
      else { field.value = ""; field.setCustomValidity("请输入有效且在允许范围内的日期（YYYY-MM-DD）。"); text.setAttribute("aria-invalid", "true"); }
    });
    text.addEventListener("change", () => { if (civil(text.value.trim()) && field.value) { field.dispatchEvent(new Event("change", { bubbles: true })); } });
    trigger.addEventListener("click", () => { trigger.setAttribute("aria-expanded", String(!panel.hidden)); if (panel.hidden) setOpen(state); else close(true); });
    text.addEventListener("keydown", event => { if (event.key === "ArrowDown" || event.key === "F4") { event.preventDefault(); setOpen(state); } });
    panel.addEventListener("keydown", event => onKey(event, state));
    previous.addEventListener("click", () => { shiftMonth(state, -1); panel.querySelector(`[data-day="${state.active}"]`)?.focus({ preventScroll: true }); });
    next.addEventListener("click", () => { shiftMonth(state, 1); panel.querySelector(`[data-day="${state.active}"]`)?.focus({ preventScroll: true }); });
    month.addEventListener("change", () => { state.viewMonth = Number(month.value); state.active = Math.min(state.active, monthDays(state.viewYear, state.viewMonth)); render(state); });
    const applyYear = () => { const value = Number(year.value); if (value >= 1 && value <= 9999) { state.viewYear = value; state.active = Math.min(state.active, monthDays(state.viewYear, state.viewMonth)); render(state); } else year.value = String(state.viewYear); };
    year.addEventListener("input", applyYear); year.addEventListener("change", applyYear);
    today.addEventListener("click", () => { const now = new Date(); const value = iso({ year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() }); if (available(field, value)) { commit(field, value); close(true); } else { const parsed = civil(value); state.viewYear = parsed.year; state.viewMonth = parsed.month; state.active = parsed.day; render(state); } });
    clear.addEventListener("click", () => { if (!field.required) { commit(field, ""); close(true); } });
    field.form?.addEventListener("submit", event => {
      const parsed = civil(text.value.trim());
      if ((!parsed && (field.required || text.value.trim())) || (parsed && !available(field, iso(parsed)))) {
        event.preventDefault(); text.setAttribute("aria-invalid", "true"); text.focus({ preventScroll: true }); queueMicrotask(() => text.focus({ preventScroll: true }));
      }
    }, true);
  }
  for (const id of ids) enhance(document.getElementById(id));
  document.addEventListener("pointerdown", event => { if (openState && !openState.shell.contains(event.target) && !openState.panel.contains(event.target)) close(false); });
  document.addEventListener("focusin", event => { if (openState && !openState.shell.contains(event.target) && !openState.panel.contains(event.target)) close(false); });
  window.addEventListener("resize", dismissIfAnchorChanged);
  window.addEventListener("scroll", event => {
    if (openState && !openState.panel.contains(event.target) && !openState.panel.contains(document.activeElement)) dismissIfAnchorChanged();
  }, true);
  window.addEventListener("wheel", () => { if (openState) close(false, true); }, true);
  window.visualViewport?.addEventListener("resize", dismissIfAnchorChanged);
  document.addEventListener("wheel", () => { if (openState) close(false, true); }, true);
  reducedMotion.addEventListener("change", () => { if (reducedMotion.matches && openState) { openState.animation?.cancel(); openState.animation = null; openState.panel.getAnimations().forEach(animation => animation.cancel()); } });
  window.OntoLensDates = { sync: syncAll, focus(field) { const text = dateFields.get(field)?.text; if (!text) return false; requestAnimationFrame(() => text.focus({ preventScroll: true })); return true; }, errorTarget(field) { return dateFields.get(field)?.shell || null; }, clear(field) { const text = dateFields.get(field)?.text; if (text) { text.removeAttribute("aria-describedby"); text.removeAttribute("aria-invalid"); } }, describe(field, id) { const text = dateFields.get(field)?.text; if (text) { text.setAttribute("aria-describedby", id); text.setAttribute("aria-invalid", "true"); } }, parse: civil };
})();
