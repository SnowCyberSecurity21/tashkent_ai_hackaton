// "Dorilarimga qo'shish": what-if safety preview before the medicine is actually added.
import { api } from "../api.js";
import { esc, icon, openSheet, meter, sevGroupList, toast, refreshIcons, fmtMg, cap } from "../components.js";
import { navigate } from "../router.js";

export function openAddFlow(product, { units = 1, onDone } = {}) {
  let n = Math.min(units, product.max_units_per_day || 12);
  const max = Math.max(1, product.max_units_per_day || 12);
  const sheet = openSheet({
    title: "Dorilarimga qo'shish",
    body: `<div class="soft p-3 flex items-center gap-3">
        <div class="alert-ico tone-primary">${icon("pill")}</div>
        <div class="min-w-0 flex-1"><div class="font-semibold t-14">${esc(product.trade_name)}</div><div class="t-12 muted">${esc(product.inns_display)}</div></div>
      </div>
      <div class="flex items-center justify-between mt-4">
        <div><div class="font-semibold">Kuniga necha dona?</div><div class="t-12 muted">Yo'riqnomadagi eng ko'p miqdor: ${max} dona/kun</div></div>
        <div class="flex items-center gap-2">
          <button class="icon-btn" data-dec aria-label="Kamaytirish">${icon("minus")}</button>
          <output class="t-22 num w-8 text-center" data-n aria-live="polite">${n}</output>
          <button class="icon-btn" data-inc aria-label="Ko'paytirish">${icon("plus")}</button>
        </div>
      </div>
      <p class="t-12 muted mt-2 mb-0">Miqdorni shifokor yoki yo'riqnoma belgilaydi. Mezon faqat xavfsizlik tekshiruvini ko'rsatadi.</p>
      <div data-preview class="mt-4"></div>
      <div class="grid gap-2 mt-4" data-actions></div>`,
  });
  const body = sheet.body;
  const preview = body.querySelector("[data-preview]");
  const actions = body.querySelector("[data-actions]");
  let reqId = 0;

  async function check() {
    const my = ++reqId;
    preview.innerHTML = `<div class="skel" style="height:120px"></div>`;
    actions.innerHTML = "";
    try {
      const res = await api("/api/safety/check", { method: "POST", body: { product_id: product.id, units_per_day: n } });
      if (my !== reqId) return;
      const meters = res.meters.filter((m) => m.limit_mg && m.contributors.some((c) => c.is_candidate));
      const newW = res.new_warnings;
      const hasDanger = newW.some((w) => w.severity === "danger");
      preview.innerHTML = `
        <div class="card" style="box-shadow:none">
          <div class="card-title">${icon("gauge")}Kunlik doza (qo'shilgandan keyin)</div>
          ${meters.length ? meters.map((m) => meter(m, { showBefore: true })).join("") : `<div class="t-14 muted">Bu dori uchun kunlik chegara qoidasi yo'q.</div>`}
        </div>
        <div class="mt-3">
          ${newW.length ? `<div class="flex items-center gap-2 font-semibold mb-1">${icon("shield-alert", "w-5 h-5")} Yangi ogohlantirishlar: ${newW.length}</div>${sevGroupList(newW)}`
            : `<div class="banner banner-green">${icon("shield-check")}<div><div class="t-16 font-semibold">Yangi ogohlantirish yo'q</div><div class="t-14 banner-sub">Tasdiqlangan qoidalar bo'yicha mos kelmaslik topilmadi.</div></div></div>`}
        </div>`;
      actions.innerHTML = hasDanger
        ? `<button class="btn btn-primary btn-block" data-cancel>${icon("x")}Qo'shmaslik</button>
           <button class="btn btn-block" data-add style="color:var(--danger-text)">${icon("triangle-alert")}Tushundim, baribir qo'shish</button>`
        : `<button class="btn btn-primary btn-block" data-add>${icon("plus")}Qo'shish</button>`;
      refreshIcons(sheet.el);
      actions.querySelector("[data-cancel]")?.addEventListener("click", sheet.close);
      actions.querySelector("[data-add]").addEventListener("click", add);
    } catch (e) {
      if (my !== reqId) return;
      preview.innerHTML = `<div class="banner banner-red">${icon("circle-x")}<div><div class="font-semibold">Tekshiruv bajarilmadi</div><div class="t-14 banner-sub">${esc(e.message)}</div></div></div>`;
      actions.innerHTML = `<button class="btn btn-soft btn-block" data-retry>${icon("rotate-cw")}Qayta urinish</button>`;
      refreshIcons(sheet.el);
      actions.querySelector("[data-retry]").addEventListener("click", check);
    }
  }

  async function add(ev) {
    const btn = ev.currentTarget;
    btn.disabled = true;
    try {
      await api("/api/regimen", { method: "POST", body: { product_id: product.id, units_per_day: n } });
      sheet.close();
      toast(`${product.trade_name} dorilaringizga qo'shildi`);
      if (onDone) onDone(); else navigate("/meds");
    } catch (e) {
      btn.disabled = false;
      toast(e.message, "err");
    }
  }

  const out = body.querySelector("[data-n]");
  body.querySelector("[data-dec]").addEventListener("click", () => { if (n > 1) { n--; out.textContent = n; check(); } });
  body.querySelector("[data-inc]").addEventListener("click", () => { if (n < max) { n++; out.textContent = n; check(); } else toast(`Yo'riqnoma bo'yicha kuniga ${max} donadan ko'p emas`, "info"); });
  check();
  return sheet;
}

export function totalsLine(t) {
  return `${cap(t.inn)} ${fmtMg(t.total_mg)} / ${fmtMg(t.limit_mg)} mg`;
}
