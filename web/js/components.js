// UI building blocks. Everything returns HTML strings; `refreshIcons()` swaps <i data-lucide> for SVGs.

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
export const icon = (name, cls = "") => `<i data-lucide="${name}" class="${cls}" aria-hidden="true"></i>`;
export function refreshIcons(root) {
  if (window.lucide && window.lucide.createIcons) {
    try { window.lucide.createIcons({ attrs: { "stroke-width": 2 }, nameAttr: "data-lucide", root: root || document }); }
    catch { window.lucide.createIcons(); }
  }
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export const fmtNum = (n) => (n === null || n === undefined ? "—" :
  Math.round(Number(n)).toLocaleString("en-US").replace(/,/g, " "));
export const fmtMg = (n) => {
  if (n === null || n === undefined) return "—";
  const x = Math.round(Number(n) * 10) / 10;
  return Number.isInteger(x) ? fmtNum(x) : String(x).replace(".", ",");
};
export const fmtMoney = (n) => `${fmtNum(n)} so'm`;
export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "hozirgina";
  if (s < 3600) return `${Math.floor(s / 60)} daqiqa oldin`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat oldin`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} kun oldin`;
  return d.toLocaleDateString("uz-UZ");
}

export const COLOR_WORD = { green: "Yashil", amber: "Sariq", red: "Qizil", gray: "Kulrang" };
export const COLOR_ICON = { green: "shield-check", amber: "triangle-alert", red: "shield-alert", gray: "circle-help" };
export const SEV = {
  danger: { word: "Xavfli", icon: "octagon-alert", cls: "sev-danger", tone: "red", group: "Xavfli" },
  warn: { word: "Ehtiyot bo'ling", icon: "triangle-alert", cls: "sev-warn", tone: "amber", group: "Ehtiyot bo'ling" },
  info: { word: "Ma'lumot", icon: "info", cls: "sev-info", tone: "gray", group: "Ma'lumot" },
  ok: { word: "Joyida", icon: "circle-check", cls: "sev-ok", tone: "green", group: "Joyida" },
};

export const demoBadge = (txt = "Demo ma'lumot") => `<span class="demo-badge" title="Bu ma'lumotlar namoyish uchun yaratilgan">${icon("flask-conical", "w-3 h-3")}${esc(txt)}</span>`;

export function trustPill(trust, { showWord = true } = {}) {
  if (!trust) return "";
  const c = trust.color;
  const label = c === "gray" ? "Ma'lumot kam" : `${trust.score}${showWord ? " · " + (trust.color_word || COLOR_WORD[c]) : ""}`;
  return `<span class="pill tone-${c}" aria-label="Ishonch indeksi ${esc(label)}">${icon(COLOR_ICON[c])}${esc(label)}</span>`;
}

export function banner(b) {
  return `<div class="banner banner-${b.color} fade-in" role="status">
    ${icon(b.icon)}
    <div class="min-w-0">
      <div class="t-12 font-semibold uppercase tracking-wide">${esc(b.word)}</div>
      <div class="t-18">${esc(b.title_uz)}</div>
      <div class="t-14 banner-sub">${esc(b.reason_uz)}</div>
    </div>
  </div>`;
}

export function gauge(score, color, { size = 132, label } = {}) {
  const r = 54, c = 2 * Math.PI * r;
  const pct = color === "gray" ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const id = "g" + Math.random().toString(36).slice(2, 8);
  return `<div class="gauge" style="width:${size}px;height:${size}px" role="img" aria-label="Ishonch indeksi ${color === "gray" ? "aniqlanmagan" : score} — ${COLOR_WORD[color]}">
    <svg viewBox="0 0 128 128" width="${size}" height="${size}">
      <circle class="g-track" cx="64" cy="64" r="${r}" fill="none" stroke-width="12"/>
      <circle id="${id}" class="g-val c-${color}" cx="64" cy="64" r="${r}" fill="none" stroke="currentColor" stroke-width="12"
        stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}" data-target="${(c * (1 - pct)).toFixed(1)}"/>
    </svg>
    <div class="g-center">
      <div class="g-num ct-${color}">${color === "gray" ? "—" : esc(score)}</div>
      <div class="t-12 font-semibold ct-${color}">${esc(label || COLOR_WORD[color])}</div>
    </div>
  </div>`;
}
export function animateGauges(root = document) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $$(".g-val[data-target]", root).forEach((el) => { el.style.strokeDashoffset = el.dataset.target; });
  }));
}

export function scoreColor(s) { return s >= 80 ? "green" : s >= 60 ? "amber" : "red"; }

export function compBar(c) {
  const col = scoreColor(c.score);
  return `<details class="comp">
    <summary class="flex items-center gap-3">
      <span class="w-6 t-14 font-bold muted num">${esc(c.key)}</span>
      <span class="flex-1 min-w-0">
        <span class="flex justify-between t-14"><span class="font-semibold">${esc(c.label)}</span><span class="num font-semibold ct-${col}">${esc(c.score)}</span></span>
        <span class="bar mt-1 block"><span class="bg-${col}" style="width:${c.score}%"></span></span>
      </span>
      ${icon("chevron-right", "chev")}
    </summary>
    <div class="pb-3 pl-9 t-14">
      <div>${esc(c.reason)}</div>
      <div class="t-12 muted mt-1">${icon("file-text", "inline w-3 h-3")} Manba: ${esc(c.source)} · ${esc(c.date)} · vazn ${Math.round(c.weight * 100)}%</div>
    </div>
  </details>`;
}

export function skeleton(lines = 3) {
  return `<div class="grid gap-3" aria-busy="true" aria-label="Yuklanmoqda">
    <div class="skel" style="height:84px"></div>
    ${Array.from({ length: lines }, (_, i) => `<div class="skel" style="height:${i % 2 ? 120 : 160}px"></div>`).join("")}
  </div>`;
}

export function empty(iconName, title, text = "", action = "") {
  return `<div class="card text-center py-8 fade-in">
    <div class="mx-auto mb-3 w-12 h-12 rounded-2xl grid place-items-center tone-primary">${icon(iconName, "w-6 h-6")}</div>
    <div class="t-16 font-semibold">${esc(title)}</div>
    ${text ? `<div class="t-14 muted mt-1">${esc(text)}</div>` : ""}
    ${action ? `<div class="mt-4">${action}</div>` : ""}
  </div>`;
}

export function errorCard(msg, retryLabel = "Qayta urinish") {
  return `<div class="card fade-in">
    <div class="flex gap-3 items-start">
      <div class="alert-ico sev-danger">${icon("wifi-off")}</div>
      <div class="flex-1"><div class="font-semibold">Ma'lumotni yuklab bo'lmadi</div><div class="t-14 muted">${esc(msg)}</div></div>
    </div>
    <button class="btn btn-soft btn-block mt-4" data-retry>${icon("rotate-cw")}${esc(retryLabel)}</button>
  </div>`;
}

// ---------- toast ----------
export function toast(message, type = "ok", ms = 3200) {
  let wrap = $(".toast-wrap");
  if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; wrap.setAttribute("aria-live", "polite"); document.body.appendChild(wrap); }
  const el = document.createElement("div");
  el.className = "toast" + (type === "err" ? " err" : "");
  el.innerHTML = `${icon(type === "err" ? "circle-x" : type === "info" ? "info" : "circle-check")}<div>${esc(message)}</div>`;
  wrap.appendChild(el);
  refreshIcons(el);
  setTimeout(() => { el.style.transition = "opacity 180ms"; el.style.opacity = "0"; setTimeout(() => el.remove(), 200); }, ms);
}

// ---------- bottom sheet ----------
export function openSheet({ title, body, wide = false, center = false, onMount, onClose } = {}) {
  const prevFocus = document.activeElement;
  const bd = document.createElement("div");
  bd.className = "backdrop";
  const sh = document.createElement("div");
  sh.className = "sheet" + (wide ? " wide" : "") + (center ? " center" : "");
  sh.setAttribute("role", "dialog");
  sh.setAttribute("aria-modal", "true");
  sh.setAttribute("aria-label", title || "Oyna");
  sh.innerHTML = `<div class="sheet-handle" aria-hidden="true"></div>
    <div class="flex items-center justify-between gap-3 mb-3">
      <h2 class="t-18">${esc(title || "")}</h2>
      <button class="icon-btn" data-close aria-label="Yopish">${icon("x")}</button>
    </div>
    <div class="sheet-body">${body || ""}</div>`;
  document.body.append(bd, sh);
  document.body.style.overflow = "hidden";
  refreshIcons(sh);
  requestAnimationFrame(() => { bd.classList.add("on"); sh.classList.add("on"); });
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    bd.classList.remove("on"); sh.classList.remove("on");
    document.removeEventListener("keydown", onKey);
    document.body.style.overflow = "";
    setTimeout(() => { bd.remove(); sh.remove(); }, 210);
    if (prevFocus && prevFocus.focus) prevFocus.focus();
    onClose && onClose();
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  bd.addEventListener("click", close);
  sh.querySelector("[data-close]").addEventListener("click", close);
  setTimeout(() => { const f = sh.querySelector("[autofocus], textarea, input, button:not([data-close])"); f && f.focus({ preventScroll: true }); }, 220);
  const api = { el: sh, body: sh.querySelector(".sheet-body"), close, setBody(html) { api.body.innerHTML = html; refreshIcons(api.body); } };
  onMount && onMount(api);
  return api;
}

export function vibrate(pattern) {
  try {
    if (navigator.userActivation && !navigator.userActivation.hasBeenActive) return; // browsers block it before a tap
    navigator.vibrate && navigator.vibrate(pattern);
  } catch { /* ignore */ }
}

export function sourceTag(source, model) {
  if (source === "live") return `<span class="pill tone-primary">${icon("sparkles")}Jonli AI${model ? " · " + esc(model) : ""}</span>`;
  if (source === "cache") return `<span class="pill tone-primary">${icon("sparkles")}AI · keshdan${model ? " · " + esc(model) : ""}</span>`;
  return `<span class="pill tone-info">${icon("archive")}Tayyor natija (oflayn)</span>`;
}

export function sevGroupList(warnings) {
  if (!warnings.length) return "";
  const groups = ["danger", "warn", "info"].map((s) => [s, warnings.filter((w) => w.severity === s)]).filter(([, l]) => l.length);
  return groups.map(([s, list]) => `
    <div class="mt-3 first:mt-0">
      <div class="flex items-center gap-2 t-12 font-semibold uppercase tracking-wide ct-${SEV[s].tone}">${icon(SEV[s].icon, "w-4 h-4")}${SEV[s].group} · ${list.length}</div>
      <div class="mt-2 grid gap-2">${list.map(warningItem).join("")}</div>
    </div>`).join("");
}

export function warningItem(w) {
  const s = SEV[w.severity] || SEV.info;
  return `<details class="soft px-3 fade-in" ${w.severity === "danger" ? "open" : ""}>
    <summary class="flex items-center gap-3 py-3 cursor-pointer list-none" style="min-height:44px">
      <span class="alert-ico ${s.cls}">${icon(s.icon)}</span>
      <span class="flex-1 min-w-0">
        <span class="block t-14 font-semibold">${esc(w.title_uz)}</span>
        <span class="block t-12 muted">${esc(s.word)} · ${esc(levelName(w.kind))}</span>
      </span>
      ${icon("chevron-down", "w-4 h-4 muted")}
    </summary>
    <div class="pb-3 t-14">
      <p class="m-0">${esc(w.message_uz)}</p>
      <p class="m-0 mt-2 t-12 muted">${icon("book-open", "inline w-3 h-3")} Manba: ${esc(w.source)}</p>
    </div>
  </details>`;
}

export function levelName(kind) {
  return { duplicate: "1-daraja: takroriy modda", max_daily: "2-daraja: kunlik miqdor", drug_drug: "3-daraja: dori + dori",
    drug_condition: "4-daraja: dori + kasallik" }[kind] || kind;
}

export function meter(t, { showBefore = false } = {}) {
  if (!t.limit_mg) return "";
  const pct = Math.min(100, (t.total_mg / t.limit_mg) * 100);
  const bpct = showBefore ? Math.min(100, ((t.before_mg ?? t.total_mg) / t.limit_mg) * 100) : pct;
  const col = t.total_mg > t.limit_mg ? "red" : pct >= 80 ? "amber" : "green";
  const changed = showBefore && (t.before_mg ?? t.total_mg) !== t.total_mg;
  return `<div class="py-2">
    <div class="flex justify-between items-baseline gap-2 t-14">
      <span class="font-semibold">${esc(cap(t.inn))}</span>
      <span class="num"><b class="ct-${col}">${changed ? `${fmtMg(t.before_mg)} → ` : ""}${fmtMg(t.total_mg)}</b> / ${fmtMg(t.limit_mg)} mg</span>
    </div>
    <div class="meter mt-1" role="meter" aria-valuemin="0" aria-valuemax="${t.limit_mg}" aria-valuenow="${t.total_mg}" aria-label="${esc(cap(t.inn))} kunlik miqdori">
      ${changed ? `<span class="m-after bg-${col}" style="width:${pct}%"></span><span class="m-before bg-${col}" style="width:${bpct}%"></span>` : `<span class="m-before bg-${col}" style="width:${pct}%"></span>`}
      <span class="m-mark" style="left:80%"></span>
    </div>
    <div class="t-12 muted mt-1">${Math.round((t.total_mg / t.limit_mg) * 100)}% · chegara manbasi: ${esc(t.limit_source || "—")}${t.limit_note ? " · " + esc(t.limit_note) : ""}</div>
  </div>`;
}
