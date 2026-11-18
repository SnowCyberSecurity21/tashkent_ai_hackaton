import { api } from "../api.js";
import { esc, icon, skeleton, errorCard, refreshIcons, toast, meter, sevGroupList, empty, openSheet, trustPill } from "../components.js";
import { openAddFlow } from "./addflow.js";

export default async function medsPage({ view }) {
  let alive = true;

  async function load() {
    try {
      const [reg, saf, pat] = await Promise.all([api("/api/regimen"), api("/api/safety"), api("/api/patient")]);
      return { reg, saf, pat };
    } catch (e) {
      view.innerHTML = errorCard(e.message);
      refreshIcons(view);
      view.querySelector("[data-retry]").addEventListener("click", draw);
      return null;
    }
  }

  async function draw(first = false) {
    if (first) view.innerHTML = skeleton(2);
    const d = await load();
    if (!d || !alive) return;
    const { reg, saf, pat } = d;
    const meters = saf.daily_totals.filter((t) => t.limit_mg);
    const c = saf.counts;
    view.innerHTML = `
      <div class="grid gap-3 fade-in">
        <div class="flex items-end justify-between gap-3 mt-2">
          <div><h1 class="t-22">Dorilarim</h1><div class="t-14 muted">${esc(pat.name)}${pat.conditions.length ? " · " + pat.conditions.length + " ta holat hisobga olinadi" : ""}</div></div>
          <button class="btn btn-primary btn-sm" id="addMed">${icon("plus")}Dori qo'shish</button>
        </div>

        ${reg.length ? `<section class="card" aria-label="Qabul qilinayotgan dorilar">
          ${reg.map((r) => `<div class="flex items-center gap-3 py-2 ${reg.indexOf(r) ? "border-t" : ""}" style="border-color:var(--border)">
            <a href="#/product/${r.product.id}" class="min-w-0 flex-1" style="color:inherit;text-decoration:none">
              <div class="font-semibold t-14">${esc(r.product.trade_name)}</div>
              <div class="t-12 muted">${esc(r.product.inns_display)}</div>
            </a>
            <div class="flex items-center gap-1" aria-label="Kuniga dona">
              <button class="icon-btn" data-dec="${r.id}" aria-label="Kamaytirish" ${r.units_per_day <= 1 ? "disabled" : ""}>${icon("minus")}</button>
              <div class="w-10 text-center"><div class="font-semibold num">${r.units_per_day}</div><div class="t-12 muted" style="line-height:1">/kun</div></div>
              <button class="icon-btn" data-inc="${r.id}" data-max="${r.product.max_units_per_day}" aria-label="Ko'paytirish">${icon("plus")}</button>
              <button class="icon-btn" data-del="${r.id}" aria-label="Olib tashlash" style="color:var(--danger-text)">${icon("trash-2")}</button>
            </div>
          </div>`).join("")}
        </section>` : empty("pill", "Hali dori qo'shilmagan", "Skanerlang yoki qidiruv orqali qo'shing.", `<a class="btn btn-primary" href="#/scan">${icon("scan-line")}Skanerlash</a>`)}

        <section class="card" aria-labelledby="h-dose">
          <div class="card-title" id="h-dose">${icon("gauge")}Kunlik doza</div>
          ${meters.length ? meters.map((m) => meter(m)).join("") : `<div class="t-14 muted">Kunlik chegarasi belgilangan modda hozircha yo'q.</div>`}
          ${pat.alcohol ? `<div class="t-12 mt-2 ct-amber">${icon("wine", "inline w-3 h-3")} Spirtli ichimlik belgilangan — paratsetamol chegarasi 2 000 mg.</div>` : ""}
        </section>

        <section class="card" aria-labelledby="h-warn">
          <div class="card-title" id="h-warn">${icon("shield-alert")}Ogohlantirishlar
            <span class="flex-1"></span>
            ${c.danger ? `<span class="pill tone-red">${c.danger} xavfli</span>` : ""}${c.warn ? `<span class="pill tone-amber">${c.warn} ehtiyot</span>` : ""}
          </div>
          ${saf.warnings.length ? sevGroupList(saf.warnings) : `<div class="banner banner-green">${icon("shield-check")}<div><div class="font-semibold">Mos kelmaslik topilmadi</div><div class="t-14 banner-sub">Tasdiqlangan qoidalar bo'yicha tekshirildi.</div></div></div>`}
          <p class="t-12 muted mt-3 mb-0">Ogohlantirishlar faqat farmatsevt tasdiqlagan qoidalardan chiqadi. Dozani o'zingiz o'zgartirmang — shifokor yoki farmatsevt bilan maslahatlashing.</p>
        </section>
      </div>`;
    refreshIcons(view);
    view.querySelector("#addMed").addEventListener("click", openSearch);
    view.querySelectorAll("[data-inc]").forEach((b) => b.addEventListener("click", async () => {
      const item = reg.find((r) => r.id === +b.dataset.inc);
      if (item.units_per_day >= +b.dataset.max) { toast(`Yo'riqnoma bo'yicha kuniga ${b.dataset.max} donadan ko'p emas`, "info"); return; }
      await update(item.id, item.units_per_day + 1);
    }));
    view.querySelectorAll("[data-dec]").forEach((b) => b.addEventListener("click", async () => {
      const item = reg.find((r) => r.id === +b.dataset.dec);
      if (item.units_per_day > 1) await update(item.id, item.units_per_day - 1);
    }));
    view.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
      const item = reg.find((r) => r.id === +b.dataset.del);
      try {
        await api(`/api/regimen/${item.id}`, { method: "DELETE" });
        toast(`${item.product.trade_name} olib tashlandi`);
        draw();
      } catch (e) { toast(e.message, "err"); }
    }));
  }

  async function update(id, units) {
    try { await api(`/api/regimen/${id}`, { method: "PATCH", body: { units_per_day: units } }); draw(); }
    catch (e) { toast(e.message, "err"); }
  }

  function openSearch() {
    const sh = openSheet({
      title: "Dori qo'shish",
      body: `<div class="flex gap-2">
          <input class="input" id="q" type="search" placeholder="Nomi yoki modda: paratsetamol, Tylol…" autocomplete="off" autofocus>
          <a class="icon-btn" href="#/scan" aria-label="Skanerlash">${icon("scan-line")}</a>
        </div>
        <div id="res" class="mt-3 grid gap-2"></div>`,
    });
    const res = sh.body.querySelector("#res");
    let timer, my = 0;
    const search = async (q) => {
      const id = ++my;
      res.innerHTML = `<div class="skel" style="height:56px"></div><div class="skel" style="height:56px"></div>`;
      try {
        const list = await api(`/api/products?limit=12&q=${encodeURIComponent(q)}`);
        if (id !== my) return;
        res.innerHTML = list.length ? list.map((p, i) => `<button class="btn btn-block" style="justify-content:space-between;text-align:left;min-height:56px" data-i="${i}">
            <span class="min-w-0"><span class="block t-14 font-semibold truncate">${esc(p.trade_name)}</span><span class="block t-12 muted truncate">${esc(p.inns_display)} · ${p.is_local ? "mahalliy" : "import"}</span></span>
            ${trustPill(p.trust, { showWord: false })}
          </button>`).join("") : `<div class="t-14 muted text-center py-4">Hech narsa topilmadi</div>`;
        refreshIcons(res);
        res.querySelectorAll("[data-i]").forEach((b) => b.addEventListener("click", () => {
          sh.close();
          openAddFlow(list[+b.dataset.i], { onDone: draw });
        }));
      } catch (e) { res.innerHTML = `<div class="t-14 ct-red">${esc(e.message)}</div>`; }
    };
    sh.body.querySelector("#q").addEventListener("input", (e) => { clearTimeout(timer); timer = setTimeout(() => search(e.target.value.trim()), 200); });
    search("");
  }

  await draw(true);
  return () => { alive = false; };
}
