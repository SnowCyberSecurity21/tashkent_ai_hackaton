import { api } from "../api.js";
import { esc, icon, refreshIcons, trustPill, timeAgo, empty } from "../components.js";
import { getRecent, syncDemoReset } from "../store.js";

export default async function homePage({ view }) {
  const recent = getRecent();
  view.innerHTML = `
    <div class="grid gap-4 fade-in">
      <div class="mt-2">
        <div class="t-14 muted">Assalomu alaykum,</div>
        <h1 class="t-28" id="hello"><span class="skel inline-block align-middle" style="width:160px;height:30px"></span></h1>
      </div>
      <a href="#/scan" class="card flex items-center gap-4" style="background:var(--primary);color:var(--primary-ink);border-color:transparent;text-decoration:none;padding:20px">
        <div class="w-14 h-14 rounded-2xl grid place-items-center flex-none" style="background:color-mix(in srgb, var(--primary-ink) 16%, transparent)">${icon("scan-line", "w-7 h-7")}</div>
        <div class="flex-1"><div class="t-22">Dorini skanerlang</div><div class="t-14" style="opacity:.9">Qadoqdagi kvadrat kod — rasmiy holat, Ishonch indeksi va xavfsizlik</div></div>
        ${icon("chevron-right", "w-6 h-6")}
      </a>
      <div class="grid grid-cols-2 gap-2" id="chips">
        <span class="skel" style="height:64px"></span><span class="skel" style="height:64px"></span>
      </div>
      <section aria-labelledby="h-recent">
        <h2 id="h-recent" class="t-16 font-semibold mb-2">So'nggi skanlar</h2>
        ${recent.length ? `<div class="card" style="padding:4px 16px">${recent.slice(0, 6).map((r, i) => `
          <a href="#/product/${r.product_id}?scan=${r.scan_id}" class="flex items-center gap-3 py-3 ${i ? "border-t" : ""}" style="border-color:var(--border);color:inherit;text-decoration:none;min-height:56px">
            <div class="alert-ico ${r.banner === "red" ? "sev-danger" : r.banner === "amber" ? "sev-warn" : r.banner === "green" ? "sev-ok" : "sev-info"}">${icon("pill")}</div>
            <div class="min-w-0 flex-1"><div class="t-14 font-semibold truncate">${esc(r.name)}</div><div class="t-12 muted">${esc(timeAgo(r.ts))}</div></div>
            ${trustPill({ score: r.score, color: r.color, color_word: r.color_word }, { showWord: false })}
          </a>`).join("")}</div>`
        : empty("scan-search", "Hali skan qilinmagan", "Skaner bo'limidagi demo kodlar bilan sinab ko'ring.", `<a class="btn btn-soft" href="#/scan">${icon("qr-code")}Demo kodlar</a>`)}
      </section>
      <p class="t-12 muted text-center mt-2">Mezon tashxis qo'ymaydi va dori tayinlamaydi. Rasmiy ma'lumotlar bu demoda namunaviy.<br>Shifokor yoki farmatsevt bilan maslahatlashing.</p>
    </div>`;
  refreshIcons(view);
  try {
    const [pat, reg, saf, health] = await Promise.all([api("/api/patient"), api("/api/regimen"), api("/api/safety"),
      api("/api/health").catch(() => ({}))]);
    if (syncDemoReset(health.demo_reset_at) && view.isConnected) return homePage({ view });
    const hello = view.querySelector("#hello");
    if (!hello) return;
    hello.textContent = pat.name.replace(/\s*\(demo\)\s*/i, "") || pat.name;
    const n = saf.warnings.length;
    const tone = saf.max_severity === "danger" ? "red" : saf.max_severity === "warn" ? "amber" : "green";
    view.querySelector("#chips").innerHTML = `
      <a href="#/meds" class="card flex items-center gap-3" style="padding:12px;text-decoration:none;color:inherit">
        <div class="alert-ico tone-primary">${icon("pill")}</div><div><div class="t-12 muted">Dorilarim</div><div class="t-18 num">${reg.length}</div></div></a>
      <a href="#/meds" class="card flex items-center gap-3 tone-${n ? tone : "green"}" style="padding:12px;text-decoration:none">
        <div class="alert-ico" style="background:transparent">${icon(n ? "shield-alert" : "shield-check")}</div><div><div class="t-12">Ogohlantirishlar</div><div class="t-18 num">${n}</div></div></a>`;
    refreshIcons(view.querySelector("#chips"));
  } catch (e) {
    const c = view.querySelector("#chips");
    if (c) c.innerHTML = `<div class="col-span-2 t-14 ct-red">${esc(e.message)}</div>`;
    const hello = view.querySelector("#hello");
    if (hello) hello.textContent = "mehmon";
  }
}
