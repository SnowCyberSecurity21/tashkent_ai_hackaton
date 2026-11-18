import { api } from "../api.js";
import { esc, icon, gauge, animateGauges, skeleton, errorCard, refreshIcons, toast, fmtMoney, fmtNum, trustPill, empty, timeAgo } from "../components.js";
import { openAddFlow } from "./addflow.js";

function timeline(a) {
  const decided = a.status !== "pending";
  const ok = a.status === "approved";
  return `<div class="tl mt-3" aria-live="polite">
    <div class="tl-step done"><div class="tl-dot">${icon("send")}</div><div><div class="t-14 font-semibold">Yuborildi</div><div class="t-12 muted">${esc(timeAgo(a.ts))}</div></div></div>
    <div class="tl-step ${decided ? "done" : "active"}"><div class="tl-dot">${decided ? icon("check") : icon("loader-circle", "spin")}</div>
      <div><div class="t-14 font-semibold">Ko'rib chiqilmoqda</div><div class="t-12 muted">${decided ? "Farmatsevt ko'rib chiqdi" : "Farmatsevt javobi kutilmoqda…"}</div></div></div>
    <div class="tl-step ${decided ? (ok ? "done" : "bad") : ""}"><div class="tl-dot">${decided ? icon(ok ? "badge-check" : "x") : icon("circle")}</div>
      <div><div class="t-14 font-semibold ${decided ? (ok ? "ct-green" : "ct-red") : "muted"}">${decided ? (ok ? "Tasdiqlandi" : "Rad etildi") : "Tasdiqlandi / Rad etildi"}</div>
      ${a.note ? `<div class="t-12">Izoh: ${esc(a.note)}</div>` : ""}${a.decided_at ? `<div class="t-12 muted">${esc(timeAgo(a.decided_at))}</div>` : ""}</div></div>
  </div>`;
}

export default async function analogsPage({ view }, { params }) {
  let alive = true;
  const timers = new Set();
  view.innerHTML = skeleton(2);
  let data, mine;
  try {
    [data, mine] = await Promise.all([api(`/api/products/${params.id}/analogs`), api("/api/approvals")]);
  } catch (e) {
    view.innerHTML = errorCard(e.message);
    refreshIcons(view);
    view.querySelector("[data-retry]").addEventListener("click", () => analogsPage({ view }, { params }));
    return;
  }
  if (!alive) return;
  const base = data.product;
  const locals = data.analogs.filter((a) => a.is_local);
  view.innerHTML = `
    <div class="grid gap-3 fade-in">
      <div class="flex items-center gap-2 -mt-1">
        <a class="icon-btn" href="#/product/${base.id}" aria-label="Orqaga">${icon("chevron-left")}</a>
        <div><h1 class="t-18">Mahalliy analoglar</h1><div class="t-12 muted">Tarkibi, miqdori, shakli va qabul usuli bir xil</div></div>
      </div>
      <div class="card">
        <div class="flex items-center gap-2 t-12 muted font-semibold uppercase tracking-wide">${icon("globe", "w-4 h-4")}Hozirgi dori · import</div>
        <div class="flex items-center justify-between gap-3 mt-2">
          <div class="min-w-0"><div class="font-semibold">${esc(base.trade_name)}</div><div class="t-12 muted">${esc(base.manufacturer)} · ${esc(base.country)}</div>
            <div class="mt-2">${trustPill(base.trust)}</div></div>
          <div class="text-right"><div class="t-12 muted">Narx</div><div class="t-18 num">${fmtMoney(base.price_uzs)}</div></div>
        </div>
      </div>
      ${locals.length ? locals.map((a) => `
        <article class="card" data-analog="${a.id}">
          <div class="flex items-center gap-2 t-12 font-semibold uppercase tracking-wide" style="color:var(--primary)">${icon("map-pin", "w-4 h-4")}Mahalliy analog</div>
          <div class="flex items-center gap-4 mt-2">
            ${gauge(a.trust.score, a.trust.color, { size: 104 })}
            <div class="min-w-0 flex-1">
              <div class="font-semibold">${esc(a.trade_name)}</div>
              <div class="t-12 muted">${esc(a.manufacturer)} ${a.is_mock ? "· demo" : ""}</div>
              <div class="t-18 num mt-1">${fmtMoney(a.price_uzs)}</div>
              ${a.savings_uzs > 0 ? `<span class="pill tone-green mt-1">${icon("badge-percent")}−${a.savings_pct}% · ${fmtNum(a.savings_uzs)} so'm tejaysiz</span>` : ""}
            </div>
          </div>
          <ul class="grid gap-1 mt-3 p-0 m-0" style="list-style:none">${a.checklist.map((c) => `<li class="flex items-center gap-2 t-14">
            <span class="${c.ok ? "ct-green" : "ct-red"}">${icon(c.ok ? "circle-check" : "circle-x", "w-4 h-4")}</span>${esc(c.label)}</li>`).join("")}</ul>
          <div class="divider"></div>
          <div data-approval></div>
        </article>`).join("") : empty("search-x", "Mahalliy analog topilmadi", "Bu tarkib, miqdor va shakldagi mahalliy dori bazada yo'q.")}
      <p class="t-12 muted">Narxlar taxminiy (demo). Almashtirish faqat farmatsevt yoki shifokor roziligi bilan.</p>
    </div>`;
  refreshIcons(view);
  animateGauges(view);

  for (const a of locals) {
    const slot = view.querySelector(`[data-analog="${a.id}"] [data-approval]`);
    const existing = mine.find((x) => x.from.id === base.id && x.to.id === a.id);
    const paint = (appr) => {
      if (!alive) return;
      if (!appr) {
        slot.innerHTML = `<button class="btn btn-primary btn-block" data-req>${icon("user-check")}Farmatsevtdan tasdiq so'rash</button>`;
        refreshIcons(slot);
        slot.querySelector("[data-req]").addEventListener("click", async (e) => {
          const btn = e.currentTarget;
          btn.disabled = true;
          try {
            const r = await api("/api/approvals", { method: "POST", body: { from_product_id: base.id, to_product_id: a.id } });
            toast("So'rov farmatsevtga yuborildi");
            paint(r); poll(r.id);
          } catch (err) { btn.disabled = false; toast(err.message, "err"); }
        });
        return;
      }
      slot.innerHTML = `<div class="font-semibold t-14 flex items-center gap-2">${icon("user-check", "w-4 h-4")}Farmatsevt tasdig'i</div>${timeline(appr)}
        ${appr.status === "approved" ? `<button class="btn btn-primary btn-block mt-3" data-add>${icon("plus")}Dorilarimga qo'shish</button>` : ""}
        ${appr.status === "rejected" ? `<button class="btn btn-block mt-3" data-again>${icon("rotate-cw")}Qayta so'rash</button>` : ""}`;
      refreshIcons(slot);
      slot.querySelector("[data-add]")?.addEventListener("click", () => openAddFlow(a));
      slot.querySelector("[data-again]")?.addEventListener("click", () => paint(null));
    };
    const poll = (id) => {
      const t = setInterval(async () => {
        if (!alive) return clearInterval(t);
        try {
          const r = await api(`/api/approvals/${id}`);
          if (r.status !== "pending") {
            clearInterval(t); timers.delete(t); paint(r);
            toast(r.status === "approved" ? "Farmatsevt almashtirishni tasdiqladi" : "Farmatsevt so'rovni rad etdi", r.status === "approved" ? "ok" : "err");
            try { navigator.vibrate && navigator.vibrate(60); } catch { /* ignore */ }
          }
        } catch { /* keep polling */ }
      }, 4000);
      timers.add(t);
    };
    paint(existing || null);
    if (existing && existing.status === "pending") poll(existing.id);
  }
  return () => { alive = false; timers.forEach(clearInterval); };
}
