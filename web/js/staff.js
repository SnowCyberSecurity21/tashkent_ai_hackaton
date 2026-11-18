// Staff console: pharmacist approvals, AI-proposed rules, maker dashboard.
import { api, setRole, getRole } from "./api.js";
import { route, fallback, onAfterRender, start, navigate, render } from "./router.js";
import { applyTheme, getTheme, setTheme, storageGet, storageSet, isDark } from "./theme.js";
import {
  $, $$, esc, icon, refreshIcons, toast, trustPill, timeAgo, fmtMoney, fmtNum, cap, empty, errorCard, openSheet,
  sourceTag, demoBadge, SEV,
} from "./components.js";

applyTheme();
const view = $("#view");
const ROLE_HOME = { pharmacist: "/approvals", maker: "/maker", admin: "/approvals" };
const ROLE_PAGES = { pharmacist: ["/approvals", "/rules", "/maker"], maker: ["/maker"], admin: ["/approvals", "/rules", "/maker"] };
setRole(storageGet("mezon.staffRole", "pharmacist"));
$("#role").value = getRole();
$("#role").addEventListener("change", (e) => {
  setRole(e.target.value); storageSet("mezon.staffRole", e.target.value);
  toast(`Rol: ${e.target.selectedOptions[0].textContent}`, "info", 1600);
  navigate(ROLE_HOME[e.target.value]);
});
function syncThemeButtons() { $$("[data-theme-opt]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeOpt === getTheme()))); }
$$("[data-theme-opt]").forEach((b) => b.addEventListener("click", () => { setTheme(b.dataset.themeOpt); syncThemeButtons(); }));
syncThemeButtons();

const KIND_UZ = { duplicate: "Takroriy modda", max_daily: "Kunlik chegara", drug_drug: "Dori + dori", drug_condition: "Dori + kasallik" };
const SEV_UZ = { danger: "Xavfli", warn: "Ehtiyot", info: "Ma'lumot" };
const tokenUz = (t) => {
  if (!t) return "—";
  if (t === "alcohol") return "spirtli ichimlik";
  if (t.startsWith("class:")) return { NSAID: "NYaQV (sinf)", beta_blocker: "beta-blokator (sinf)", MAOI: "MAO ingibitori (sinf)",
    sedating_antihistamine: "sedativ antigistamin (sinf)", tricyclic_antidepressant: "trisiklik antidepressant (sinf)" }[t.slice(6)] || t;
  return t.replace(/_/g, " ");
};

function roleGuard(path) {
  if (!ROLE_PAGES[getRole()].includes(path)) {
    view.innerHTML = empty("lock", "Bu bo'lim boshqa rol uchun", "Chap paneldan mos rolni tanlang.", `<button class="btn btn-primary" id="toHome">${icon("arrow-right")}O'z bo'limimga o'tish</button>`);
    refreshIcons(view);
    $("#toHome").addEventListener("click", () => navigate(ROLE_HOME[getRole()]));
    return false;
  }
  return true;
}

const resetBtn = () => getRole() === "maker" ? "" :
  `<button class="btn btn-sm btn-ghost" data-reset-demo title="Bemor, so'rovlar, skanlar va AI takliflarini boshlang'ich holatga qaytaradi">${icon("rotate-ccw")}Demoni qayta boshlash</button>`;
const header = (title, sub, right = "") => `<div class="flex items-end justify-between gap-4 flex-wrap mb-5">
  <div><h1 class="t-28">${esc(title)}</h1><div class="t-14 muted mt-1">${esc(sub)}</div></div><div class="flex items-center gap-2 flex-wrap">${right}${resetBtn()}</div></div>`;

// ------------------------------------------------------------------ demo reset (between mentor demos)
document.addEventListener("click", (e) => {
  if (!e.target.closest("[data-reset-demo]")) return;
  const sh = openSheet({
    title: "Demoni qayta boshlash", center: true,
    body: `<div class="banner banner-amber">${icon("rotate-ccw")}<div><div class="font-semibold">Demo boshlang'ich holatga qaytadi</div>
        <div class="t-14 banner-sub">Aziza: gipertoniya, faqat bisoprolol. Yangi so'rovlar, xabarlar, baholar, skanlar va AI taklif qilgan qoidalar o'chiriladi.
        AI keshi, mahsulotlar va tasdiqlangan boshlang'ich qoidalar saqlanadi.</div></div></div>
      <div class="flex gap-2 mt-4 justify-end flex-wrap">
        <button class="btn" id="resetCancel">Bekor qilish</button>
        <button class="btn btn-danger" id="resetGo">${icon("rotate-ccw")}Ha, qayta boshlash</button>
      </div>`,
  });
  sh.body.querySelector("#resetCancel").addEventListener("click", () => sh.close());
  sh.body.querySelector("#resetGo").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget; btn.disabled = true;
    try {
      await api("/api/admin/reset-demo", { method: "POST" });
      sh.close();
      toast("Demo boshlang'ich holatga qaytarildi");
      updateCount(1);
      render();
    } catch (err) { btn.disabled = false; toast(err.message, "err"); }
  });
});

// ------------------------------------------------------------------ approvals
async function approvalsPage() {
  if (!roleGuard("/approvals")) return;
  let alive = true;
  view.innerHTML = header("Almashtirish so'rovlari", "Bemorlar import dorini mahalliy analogga almashtirish uchun tasdiq so'ramoqda.", demoBadge()) +
    `<div id="pending"><div class="skel" style="height:160px"></div></div><h2 class="t-18 mt-8 mb-3">Ko'rib chiqilganlar</h2><div id="done"></div>`;
  let lastIds = null;
  async function load() {
    try {
      const all = await api("/api/approvals");
      if (!alive) return;
      const pending = all.filter((a) => a.status === "pending");
      const done = all.filter((a) => a.status !== "pending").slice(0, 10);
      const ids = pending.map((a) => a.id).join(",");
      if (lastIds !== null && ids !== lastIds && pending.length && pending[0].id > Math.max(0, ...lastIds.split(",").map(Number))) toast("Yangi so'rov keldi", "info");
      lastIds = ids;
      updateCount(pending.length);
      $("#pending").innerHTML = pending.length ? `<div class="card tbl-wrap" style="padding:8px 16px"><table class="tbl">
        <thead><tr><th>Bemor</th><th>Almashtirish</th><th>Ishonch indeksi</th><th>Tarkib</th><th class="text-right">Tejash</th><th>Vaqt</th><th class="text-right">Qaror</th></tr></thead>
        <tbody>${pending.map(row).join("")}</tbody></table></div>`
        : empty("inbox", "Kutilayotgan so'rov yo'q", "Bemor ilovasida \"Farmatsevtdan tasdiq so'rash\" bosilsa, shu yerda paydo bo'ladi (har 5 soniyada yangilanadi).");
      $("#done").innerHTML = done.length ? `<div class="card tbl-wrap" style="padding:8px 16px"><table class="tbl"><tbody>${done.map((a) => `<tr>
          <td>${esc(a.patient?.name)}</td><td>${esc(a.from.trade_name)} → <b>${esc(a.to.trade_name)}</b></td>
          <td>${a.status === "approved" ? `<span class="pill tone-green">${icon("check")}Tasdiqlandi</span>` : `<span class="pill tone-red">${icon("x")}Rad etildi</span>`}</td>
          <td class="t-14 muted">${esc(a.note || "")}</td><td class="t-12 muted">${esc(timeAgo(a.decided_at))}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="t-14 muted">Hali qaror qabul qilinmagan.</div>`;
      refreshIcons(view);
    } catch (e) {
      if (alive) { $("#pending").innerHTML = errorCard(e.message); refreshIcons(view); $("#pending [data-retry]")?.addEventListener("click", load); }
    }
  }
  const row = (a) => `<tr>
    <td><div class="font-semibold">${esc(a.patient?.name)}</div><div class="t-12 muted">${esc((a.patient?.conditions || []).join(", ") || "holat ko'rsatilmagan")}</div></td>
    <td><div class="t-14">${esc(a.from.trade_name)}</div><div class="t-14 font-semibold flex items-center gap-1">${icon("arrow-right", "w-4 h-4")}${esc(a.to.trade_name)}</div><div class="t-12 muted">${esc(a.to.manufacturer)}</div></td>
    <td><div class="flex items-center gap-1 flex-wrap">${trustPill(a.from.trust, { showWord: false })}${icon("arrow-right", "w-3 h-3 muted")}${trustPill(a.to.trust)}</div></td>
    <td>${a.composition_match ? `<span class="pill tone-green">${icon("circle-check")}To'liq mos</span>` : `<span class="pill tone-red">${icon("circle-x")}Mos emas</span>`}
      <div class="t-12 muted mt-1">${esc(a.from.inns_display)}</div></td>
    <td class="text-right num">${fmtMoney(a.savings_uzs)}</td>
    <td class="t-12 muted">${esc(timeAgo(a.ts))}</td>
    <td class="text-right"><div class="flex gap-2 justify-end">
      <button class="btn btn-primary btn-sm" data-dec="approved" data-id="${a.id}">${icon("check")}Tasdiqlash</button>
      <button class="btn btn-sm" data-dec="rejected" data-id="${a.id}">${icon("x")}Rad etish</button></div></td>
  </tr>`;
  view.addEventListener("click", onClick);
  function onClick(e) {
    const b = e.target.closest("[data-dec]");
    if (!b) return;
    const decision = b.dataset.dec, id = +b.dataset.id;
    const sh = openSheet({
      title: decision === "approved" ? "Almashtirishni tasdiqlash" : "So'rovni rad etish", center: true,
      body: `<label class="label" for="note">Bemorga izoh (ixtiyoriy)</label>
        <textarea id="note" class="textarea" style="font-family:inherit;font-size:15px" maxlength="300" placeholder="${decision === "approved" ? "Masalan: tarkibi bir xil, almashtirish mumkin." : "Masalan: shifokoringiz bilan maslahatlashing."}"></textarea>
        <button class="btn ${decision === "approved" ? "btn-primary" : "btn-danger"} btn-block mt-3" id="go">${icon(decision === "approved" ? "check" : "x")}${decision === "approved" ? "Tasdiqlash" : "Rad etish"}</button>`,
    });
    sh.body.querySelector("#go").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget; btn.disabled = true;
      try {
        await api(`/api/approvals/${id}/decide`, { method: "POST", body: { decision, note: sh.body.querySelector("#note").value.trim() || null } });
        sh.close(); toast(decision === "approved" ? "Tasdiqlandi — bemor ilovasida ko'rinadi" : "Rad etildi"); load();
      } catch (err) { btn.disabled = false; toast(err.message, "err"); }
    });
  }
  await load();
  const t = setInterval(load, 5000);
  return () => { alive = false; clearInterval(t); view.removeEventListener("click", onClick); };
}

function updateCount(n) {
  const el = $("#pendingCount");
  el.hidden = !n; el.textContent = n;
}

// ------------------------------------------------------------------ AI rules
async function rulesPage() {
  if (!roleGuard("/rules")) return;
  let alive = true;
  view.innerHTML = header("AI qoidalari", "AI yo'riqnomadan xavfsizlik qoidalarini taklif qiladi — farmatsevt tasdiqlamaguncha ular ishlamaydi.") + `
    <section class="card">
      <div class="flex items-start gap-4 flex-wrap">
        <div class="alert-ico tone-primary" style="width:48px;height:48px">${icon("file-text", "w-6 h-6")}</div>
        <div class="flex-1 min-w-[240px]">
          <div class="t-18">Tylol Hot — qisqa mahsulot ma'lumoti (KÜB, turkcha)</div>
          <div class="t-14 muted">data/leaflets/tylol-hot.pdf · 4.2–4.6 bo'limlar: dozalash, qarshi ko'rsatmalar, ehtiyot choralari, o'zaro ta'sirlar</div>
          <div class="t-12 muted mt-2">«Qayta tahlil qilish» keshni chetlab, yo'riqnomani hozir jonli AI'ga yuboradi.</div>
        </div>
        <div class="flex gap-2 flex-wrap">
          <button class="btn btn-primary" id="extract">${icon("sparkles")}Tylol Hot yo'riqnomasidan qoida chiqarish</button>
          <button class="btn btn-soft" id="reanalyze" title="Keshsiz, jonli AI chaqiruvi">${icon("refresh-cw")}Qayta tahlil qilish</button>
        </div>
      </div>
      <div id="status" class="mt-4" hidden></div>
    </section>
    <section class="mt-5" id="proposed"></section>
    <details class="card mt-5" id="active"><summary class="flex items-center gap-2 font-semibold cursor-pointer list-none">${icon("shield-check", "w-5 h-5")}Amaldagi (tasdiqlangan) qoidalar <span class="pill tone-info" id="activeN"></span><span class="flex-1"></span>${icon("chevron-down", "w-4 h-4 muted")}</summary><div id="activeBody" class="mt-3"></div></details>`;
  refreshIcons(view);

  // a slow list response must not overwrite a newer extraction result (seen over the network, not on localhost)
  let listGen = 0;
  async function loadLists() {
    const gen = ++listGen;
    try {
      const [proposed, active] = await Promise.all([api("/api/rules?approved=false"), api("/api/rules?approved=true")]);
      if (!alive) return;
      if (gen === listGen) renderProposed(proposed);
      $("#activeN").textContent = active.length;
      $("#activeBody").innerHTML = `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Turi</th><th>A</th><th>B</th><th>Daraja</th><th>Manba</th><th>Kelib chiqishi</th></tr></thead><tbody>
        ${active.map((r) => `<tr><td>${esc(KIND_UZ[r.kind])}</td><td>${esc(tokenUz(r.a))}</td><td>${esc(r.kind === "max_daily" ? `${fmtNum(r.threshold_mg)} mg${r.b ? " · " + tokenUz(r.b) : ""}` : tokenUz(r.b))}</td>
        <td><span class="pill tone-${SEV[r.severity].tone}">${esc(SEV_UZ[r.severity])}</span></td><td class="t-12">${esc(r.source)}</td>
        <td>${r.origin === "llm" ? `<span class="pill tone-primary">${icon("sparkles")}AI + farmatsevt</span>` : `<span class="pill tone-info">Boshlang'ich</span>`}</td></tr>`).join("")}</tbody></table></div>`;
      refreshIcons(view);
    } catch (e) { toast(e.message, "err"); }
  }

  function renderProposed(rules, meta) {
    const box = $("#proposed");
    if (!rules.length) {
      box.innerHTML = meta ? empty("check-check", "Barcha takliflar ko'rib chiqildi", "Tasdiqlangan qoidalar bemor xavfsizlik tekshiruvida darhol ishlaydi.") : "";
      refreshIcons(box);
      return;
    }
    box.innerHTML = `<div class="flex items-center justify-between gap-3 flex-wrap mb-3">
        <h2 class="t-18">Taklif qilingan qoidalar <span class="pill tone-amber">${rules.length} ta tasdiq kutmoqda</span></h2>
        <div class="flex gap-2"><button class="btn btn-sm" id="selAll">${icon("list-checks")}Hammasini belgilash</button>
        <button class="btn btn-primary btn-sm" id="apprSel">${icon("check")}Tanlanganlarni tasdiqlash</button></div>
      </div>
      <div class="card tbl-wrap" style="padding:8px 16px"><table class="tbl">
        <thead><tr><th style="width:36px"><span class="sr-only">Tanlash</span></th><th>Turi</th><th>A</th><th>B</th><th>Daraja</th><th style="min-width:280px">Bemorga xabar</th><th>Manba bo'limi</th><th class="text-right">Amal</th></tr></thead>
        <tbody>${rules.map((r) => `<tr data-rule="${r.id}" class="fade-in">
          <td><input type="checkbox" data-sel="${r.id}" aria-label="Qoidani tanlash" style="width:20px;height:20px"></td>
          <td class="t-14">${esc(KIND_UZ[r.kind])}</td>
          <td class="t-14 font-semibold">${esc(cap(tokenUz(r.a)))}</td>
          <td class="t-14">${esc(r.kind === "max_daily" ? `${fmtNum(r.threshold_mg)} mg${r.b ? " · " + tokenUz(r.b) : ""}` : tokenUz(r.b))}</td>
          <td><span class="pill tone-${SEV[r.severity].tone}">${icon(SEV[r.severity].icon)}${esc(SEV_UZ[r.severity])}</span></td>
          <td class="t-14">${esc(r.message_uz)}</td>
          <td class="t-12">${esc(r.source)}</td>
          <td class="text-right"><div class="flex gap-1 justify-end">
            <button class="btn btn-soft btn-sm" data-appr="${r.id}">${icon("check")}Tasdiqlash</button>
            <button class="icon-btn" data-rej="${r.id}" aria-label="Rad etish" style="width:36px;height:36px">${icon("x")}</button></div></td>
        </tr>`).join("")}</tbody></table></div>`;
    refreshIcons(box);
  }

  async function approve(ids) {
    let ok = 0;
    for (const id of ids) {
      try { await api(`/api/rules/${id}/approve`, { method: "POST" }); ok++; } catch (e) { toast(e.message, "err"); }
    }
    if (ok) toast(`${ok} ta qoida tasdiqlandi — xavfsizlik tekshiruvida darhol ishlaydi`);
    loadLists();
  }

  view.addEventListener("click", onClick);
  async function onClick(e) {
    const a = e.target.closest("[data-appr]"), r = e.target.closest("[data-rej]");
    if (a) { a.disabled = true; await approve([+a.dataset.appr]); }
    if (r) {
      r.disabled = true;
      try { await api(`/api/rules/${r.dataset.rej}/reject`, { method: "POST" }); toast("Taklif rad etildi", "info"); loadLists(); }
      catch (err) { r.disabled = false; toast(err.message, "err"); }
    }
    if (e.target.closest("#selAll")) $$("[data-sel]").forEach((c) => { c.checked = true; });
    if (e.target.closest("#apprSel")) {
      const ids = $$("[data-sel]:checked").map((c) => +c.dataset.sel);
      if (!ids.length) toast("Avval qoidalarni belgilang", "info"); else approve(ids);
    }
  }

  $("#extract").addEventListener("click", () => runExtract(false));
  $("#reanalyze").addEventListener("click", () => runExtract(true));
  async function runExtract(fresh) {
    const btns = [$("#extract"), $("#reanalyze")]; btns.forEach((b) => { b.disabled = true; });
    const st = $("#status"); st.hidden = false;
    const t0 = Date.now();
    const tick = () => { st.innerHTML = `<div class="banner banner-gray">${icon("loader-circle", "spin")}<div><div class="font-semibold">AI yo'riqnomani o'qimoqda… <span class="num">${Math.round((Date.now() - t0) / 1000)} s</span></div>
      <div class="t-14 banner-sub">Asosiy model → zaxira model (har biri 20 s gacha) → tayyor natija. PII avtomatik yashiriladi.</div></div></div>`; refreshIcons(st); };
    tick();
    const timer = setInterval(tick, 1000);
    try {
      const res = await api(`/api/admin/llm/leaflet-rules?fresh=${fresh}`, { method: "POST" });
      clearInterval(timer);
      if (!alive) return;
      const why = res.error ? (res.error === "cooldown" ? "AI vaqtincha javob bermadi" : res.error.includes("429") ? "so'rovlar limiti (429)" : res.error.includes("timeout") ? "vaqt tugadi (20 s)" : "AI xatosi") : "";
      st.innerHTML = `<div class="banner banner-green fade-in">${icon("sparkles")}<div><div class="font-semibold">${res.rules.length} ta qoida taklif qilindi · ${(res.elapsed_ms / 1000).toFixed(1)} s</div>
        <div class="t-14 banner-sub flex items-center gap-2 flex-wrap mt-1">${sourceTag(res.source, res.model)}${res.source === "precomputed" && why ? `<span class="t-12">Sabab: ${esc(why)} — oldindan tayyorlangan natija ko'rsatildi</span>` : ""}
        <span class="t-12">${esc(res.note_uz)}</span></div></div></div>`;
      refreshIcons(st);
      listGen++;
      renderProposed(res.rules, true);
    } catch (err) {
      clearInterval(timer);
      st.innerHTML = `<div class="banner banner-red">${icon("circle-x")}<div><div class="font-semibold">Qoidalarni chiqarib bo'lmadi</div><div class="t-14 banner-sub">${esc(err.message)}</div></div></div>`;
      refreshIcons(st);
    } finally { btns.forEach((b) => { b.disabled = false; }); }
  }

  await loadLists();
  return () => { alive = false; view.removeEventListener("click", onClick); };
}

// ------------------------------------------------------------------ maker dashboard
let charts = [];
function tokens() {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return { text: v("--text"), muted: v("--muted"), border: v("--border"), surface: v("--surface"), primary: v("--primary"),
    green: v("--success"), amber: v("--warning"), red: v("--danger"), gray: v("--gray-score") };
}

async function makerPage() {
  if (!roleGuard("/maker")) return;
  let alive = true;
  const makers = await api("/api/maker/manufacturers").catch(() => []);
  let current = storageGet("mezon.maker", "");
  if (current && !makers.find((m) => m.name === current)) current = "";
  view.innerHTML = header("Ishlab chiqaruvchi paneli", "Skanlar, Ishonch indeksi, farmakonazorat xabarlari va markirovka ogohlantirishlari.",
    `<label class="sr-only" for="maker">Ishlab chiqaruvchi</label><select id="maker" class="select" style="width:auto;min-width:260px">
      <option value="">Barcha ishlab chiqaruvchilar</option>${makers.map((m) => `<option ${m.name === current ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>
     <button class="btn btn-primary" id="upload">${icon("upload")}Hujjat yuklash</button>`) + `<div id="dash"><div class="grid grid-cols-2 lg:grid-cols-4 gap-3">${'<div class="skel" style="height:96px"></div>'.repeat(4)}</div></div>`;
  refreshIcons(view);
  $("#maker").addEventListener("change", (e) => { current = e.target.value; storageSet("mezon.maker", current); draw(); });
  $("#upload").addEventListener("click", () => openUpload(current));
  const onTheme = () => draw();
  window.addEventListener("themechange", onTheme);

  async function draw() {
    let d;
    try { d = await api(`/api/maker/stats${current ? "?manufacturer=" + encodeURIComponent(current) : ""}`); }
    catch (e) { $("#dash").innerHTML = errorCard(e.message); refreshIcons(view); $("#dash [data-retry]")?.addEventListener("click", draw); return; }
    if (!alive) return;
    const k = d.kpis;
    const kpi = (ic, label, v, sub, tone = "primary") => `<div class="card kpi"><div class="flex items-center gap-2 t-14 muted">${icon(ic, "w-4 h-4")}${label}</div><div class="v">${v}</div><div class="t-12 muted">${sub}</div></div>`;
    $("#dash").innerHTML = `
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        ${kpi("scan-line", "Skanlar", fmtNum(k.scans), "oxirgi 30 kun")}
        ${kpi("gauge", "O'rtacha indeks", `<span class="ct-${k.avg_index >= 80 ? "green" : k.avg_index >= 60 ? "amber" : "red"}">${k.avg_index}</span>`, `${k.products} ta mahsulot bo'yicha`)}
        ${kpi("message-square-warning", "Xabarlar", fmtNum(k.reports), "farmakonazorat")}
        ${kpi("shield-alert", "Ogohlantirishlar", `<span class="${k.alerts ? "ct-red" : ""}">${fmtNum(k.alerts)}</span>`, "klon kod, qaytarish, muddat")}
      </div>
      <div class="grid lg:grid-cols-2 gap-3 mt-3 items-start">
        <section class="card"><div class="card-title">${icon("trending-up")}Kunlik skanlar <span class="t-12 muted font-normal">· 30 kun</span></div><div style="height:240px"><canvas id="cScans" aria-label="Kunlik skanlar grafigi" role="img"></canvas></div></section>
        <section class="card"><div class="card-title">${icon("chart-bar")}Mahsulotlar bo'yicha Ishonch indeksi</div>
          <div style="height:${Math.max(220, d.index_per_product.length * 22 + 40)}px;max-height:520px;overflow:auto"><div style="height:${Math.max(200, d.index_per_product.length * 22 + 20)}px"><canvas id="cIndex" aria-label="Ishonch indeksi grafigi" role="img"></canvas></div></div>
          <div class="flex gap-3 t-12 muted mt-2 flex-wrap">${["green", "amber", "red", "gray"].map((c) => `<span class="flex items-center gap-1"><span style="width:10px;height:10px;border-radius:3px;display:inline-block" class="bg-${c}"></span>${{ green: "Yashil ≥80", amber: "Sariq 60–79", red: "Qizil <60", gray: "Kulrang: ma'lumot kam" }[c]}</span>`).join("")}</div>
          <details class="mt-2"><summary class="t-12 cursor-pointer">Jadval ko'rinishi</summary><table class="tbl mt-2"><tbody>${d.index_per_product.map((p) => `<tr><td class="t-14">${esc(p.name)}</td><td class="text-right">${trustPill({ score: p.score, color: p.color })}</td></tr>`).join("")}</tbody></table></details>
        </section>
      </div>
      <div class="grid lg:grid-cols-2 gap-3 mt-3">
        <section class="card"><div class="card-title">${icon("siren")}Markirovka ogohlantirishlari</div>
          ${d.alerts.length ? d.alerts.map((a) => `<div class="alert-row"><div class="alert-ico ${a.severity === "danger" ? "sev-danger" : "sev-warn"}">${icon(a.type === "clone" ? "copy" : a.type === "recall" ? "octagon-x" : "calendar-x")}</div>
            <div class="flex-1 min-w-0"><div class="t-14 font-semibold">${esc(a.title)}: ${esc(a.product)}</div><div class="t-12 muted">${esc(a.detail)}${a.serial ? " · seriya " + esc(a.serial) : ""}</div></div></div>`).join("")
            : `<div class="t-14 muted">Ogohlantirish yo'q.</div>`}
        </section>
        <section class="card"><div class="card-title">${icon("messages-square")}So'nggi xabarlar <span class="t-12 muted font-normal">· AI toifasi</span></div>
          ${d.reports_by_category.length ? `<div class="flex flex-wrap gap-2 mb-2">${d.reports_by_category.map((c) => `<span class="chip chip-static">${esc(cap(c.category))} <b class="num">${c.count}</b></span>`).join("")}</div>` : ""}
          ${d.recent_reports.length ? d.recent_reports.map((r) => `<div class="alert-row"><div class="alert-ico ${SEV[r.severity].cls}">${icon(SEV[r.severity].icon)}</div>
            <div class="flex-1 min-w-0"><div class="t-14">${esc(r.text)}</div><div class="t-12 muted">${esc(r.product)} · <b>${esc(r.category)}</b> · ${r.classified_by === "ai" ? "AI" : "qoida"} · ${esc(timeAgo(r.ts))}</div></div></div>`).join("")
            : `<div class="t-14 muted">Xabar yo'q.</div>`}
        </section>
      </div>
      <p class="t-12 muted mt-4">${demoBadge()} Skanlar anonim; indekslar demo ma'lumotlar asosida hisoblangan.</p>`;
    refreshIcons(view);
    charts.forEach((c) => c.destroy()); charts = [];
    if (!window.Chart) return;
    const t = tokens();
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.color = t.muted;
    const grid = { color: t.border, drawTicks: false };
    const tip = { backgroundColor: t.text, titleColor: t.surface, bodyColor: t.surface, padding: 10, cornerRadius: 8, displayColors: false };
    charts.push(new Chart($("#cScans"), {
      type: "line",
      data: { labels: d.scans_by_day.labels, datasets: [{ label: "Skanlar", data: d.scans_by_day.values, borderColor: t.primary, borderWidth: 2,
        backgroundColor: t.primary + "22", fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: t.surface }] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { ...tip, callbacks: { label: (c) => `${c.parsed.y} ta skan` } } },
        scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { beginAtZero: true, grid, border: { display: false }, ticks: { precision: 0, padding: 6 } } } },
    }));
    const col = { green: t.green, amber: t.amber, red: t.red, gray: t.gray };
    charts.push(new Chart($("#cIndex"), {
      type: "bar",
      data: { labels: d.index_per_product.map((p) => p.name.length > 30 ? p.name.slice(0, 29) + "…" : p.name),
        datasets: [{ label: "Ishonch indeksi", data: d.index_per_product.map((p) => p.score), backgroundColor: d.index_per_product.map((p) => col[p.color]),
          borderRadius: 4, borderSkipped: "start", barThickness: 12 }] },
      options: { indexAxis: "y", maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { ...tip, callbacks: {
          title: (c) => d.index_per_product[c[0].dataIndex].name,
          label: (c) => { const p = d.index_per_product[c.dataIndex]; return `Indeks ${p.score} · ${{ green: "Yashil", amber: "Sariq", red: "Qizil", gray: "Kulrang" }[p.color]}${p.is_local ? " · mahalliy" : ""}`; } } } },
        scales: { x: { min: 0, max: 100, grid, border: { display: false } }, y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } } } },
    }));
  }
  await draw();
  return () => { alive = false; window.removeEventListener("themechange", onTheme); charts.forEach((c) => c.destroy()); charts = []; };
}

async function openUpload(manufacturer) {
  const products = (await api("/api/products?limit=100").catch(() => [])).filter((p) => !manufacturer || p.manufacturer === manufacturer);
  const sh = openSheet({
    title: "Tahlil sertifikatini (CoA) yuklash", center: true,
    body: `<form id="upForm" class="grid gap-3">
      <div><label class="label" for="upProd">Mahsulot</label><select id="upProd" class="select" required>${products.map((p) => `<option value="${p.id}">${esc(p.trade_name)}</option>`).join("")}</select></div>
      <div><label class="label" for="upBatch">Partiya raqami</label><input id="upBatch" class="input" placeholder="Masalan: NV2507I" maxlength="30"></div>
      <div><label class="label" for="upFile">PDF fayl</label><input id="upFile" class="input" type="file" accept="application/pdf" required></div>
      <p class="t-12 muted m-0">AI hujjatdan qiymatlarni ajratadi, me'yorga solishtirish esa dasturda bajariladi. Hujjat farmatsevt tasdiqlaguncha indeksga ta'sir qilmaydi. Sinab ko'rish uchun <code>data/coa/</code> papkasidagi PDF'lardan foydalaning.</p>
      <button class="btn btn-primary" id="upGo" type="submit">${icon("upload")}Yuklash</button>
      <div id="upOut"></div></form>`,
  });
  sh.body.querySelector("#upForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = sh.body.querySelector("#upGo");
    const file = sh.body.querySelector("#upFile").files[0];
    if (!file) { toast("PDF faylni tanlang", "err"); return; }
    const fd = new FormData();
    fd.append("product_id", sh.body.querySelector("#upProd").value);
    fd.append("batch_no", sh.body.querySelector("#upBatch").value.trim());
    fd.append("file", file);
    btn.disabled = true; btn.innerHTML = `${icon("loader-circle", "spin")}Yuklanmoqda…`; refreshIcons(btn);
    try {
      const r = await api("/api/maker/documents", { method: "POST", form: fd });
      const rows = r.extracted.results || [];
      sh.body.querySelector("#upOut").innerHTML = `<div class="banner banner-green fade-in">${icon("circle-check")}<div><div class="font-semibold">${esc(r.message_uz)}</div>
        <div class="t-12 banner-sub mt-1 flex gap-2 items-center flex-wrap">${sourceTag(r.source === "none" ? "precomputed" : r.source, r.model)} partiya: ${esc(r.batch_no || "—")} · SHA-256 ${esc(r.sha256.slice(0, 12))}…</div></div></div>
        ${rows.length ? `<table class="tbl mt-3"><thead><tr><th>Ko'rsatkich</th><th class="text-right">Natija</th><th></th></tr></thead><tbody>${rows.map((x) => `<tr><td>${esc(x.parameter)}</td><td class="text-right num">${esc(x.value)} ${esc(x.unit)}</td>
          <td class="text-right">${x.status === "ok" ? `<span class="pill tone-green">Mos</span>` : `<span class="pill tone-red">Mos emas</span>`}</td></tr>`).join("")}</tbody></table>` : `<div class="t-14 muted mt-2">Hujjatdan jadval ajratib bo'lmadi — farmatsevt qo'lda tekshiradi.</div>`}`;
      refreshIcons(sh.body);
      btn.innerHTML = `${icon("check")}Yuborildi`; refreshIcons(btn);
    } catch (err) { btn.disabled = false; btn.innerHTML = `${icon("upload")}Yuklash`; refreshIcons(btn); toast(err.message, "err"); }
  });
}

// ------------------------------------------------------------------ routing
route("/approvals", approvalsPage);
route("/rules", rulesPage);
route("/maker", makerPage);
route("/", () => navigate(ROLE_HOME[getRole()], { replace: true }));
fallback(() => navigate(ROLE_HOME[getRole()], { replace: true }));
onAfterRender(({ path }) => {
  $$("[data-nav]").forEach((a) => (a.dataset.nav === path ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  refreshIcons();
});
// pending badge in sidebar
setInterval(() => { if (getRole() !== "maker") api("/api/approvals?status=pending").then((l) => updateCount(l.length)).catch(() => {}); }, 8000);
if (getRole() !== "maker") api("/api/approvals?status=pending").then((l) => updateCount(l.length)).catch(() => {});
start();
