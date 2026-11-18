import { api } from "../api.js";
import { esc, icon, skeleton, errorCard, refreshIcons, toast } from "../components.js";
import { getTheme, setTheme } from "../theme.js";

export default async function profilePage({ view }) {
  view.innerHTML = skeleton(2);
  let pat, conds, health;
  try {
    [pat, conds, health] = await Promise.all([api("/api/patient"), api("/api/conditions"), api("/api/health").catch(() => null)]);
  } catch (e) {
    view.innerHTML = errorCard(e.message);
    refreshIcons(view);
    view.querySelector("[data-retry]").addEventListener("click", () => profilePage({ view }));
    return;
  }
  const llm = health?.llm;
  const theme = getTheme();
  view.innerHTML = `
    <div class="grid gap-3 fade-in">
      <h1 class="t-22 mt-2">Profil</h1>
      <section class="card">
        <label class="label" for="name">Ism</label>
        <div class="flex gap-2"><input id="name" class="input" value="${esc(pat.name)}" maxlength="60" autocomplete="given-name">
          <button class="btn btn-soft" id="saveName">${icon("check")}Saqlash</button></div>
        <p class="t-12 muted mt-2 mb-0">Ism faqat salomlashish uchun. AI'ga hech qachon yuborilmaydi.</p>
      </section>

      <section class="card" aria-labelledby="h-cond">
        <div class="card-title" id="h-cond">${icon("heart-pulse")}Surunkali holatlar</div>
        <p class="t-14 muted mt-0">Belgilangan holatlar dori xavfsizligi tekshiruvida hisobga olinadi.</p>
        <div class="flex flex-wrap gap-2" id="conds">${conds.map((c) => `<button class="chip" data-k="${esc(c.key)}" aria-pressed="${pat.conditions.includes(c.key)}">${pat.conditions.includes(c.key) ? icon("check") : icon("plus")}${esc(c.label_uz)}</button>`).join("")}</div>
        <div class="divider"></div>
        <div class="flex items-center justify-between gap-3">
          <label for="alc" class="t-16">Spirtli ichimlik iste'mol qilaman<div class="t-12 muted">Paratsetamol chegarasi 4 000 → 2 000 mg</div></label>
          <span class="switch"><input type="checkbox" id="alc" ${pat.alcohol ? "checked" : ""} role="switch" aria-checked="${pat.alcohol}"><span class="track"></span><span class="knob"></span></span>
        </div>
      </section>

      <section class="card" aria-labelledby="h-theme">
        <div class="card-title" id="h-theme">${icon("palette")}Ko'rinish</div>
        <div class="seg" role="group" aria-label="Mavzu">
          ${[["auto", "monitor", "Avto"], ["light", "sun", "Yorug'"], ["dark", "moon", "Qorong'i"]].map(([k, ic, l]) =>
            `<button data-theme-opt="${k}" aria-pressed="${theme === k}">${icon(ic)}${l}</button>`).join("")}
        </div>
      </section>

      <section class="card grid gap-2">
        <a class="btn" href="#/demo-codes" style="justify-content:space-between">${icon("qr-code")}<span class="flex-1 text-left">Demo kodlar (ikkinchi ekran uchun)</span>${icon("chevron-right")}</a>
        <a class="btn" href="#/connect" style="justify-content:space-between">${icon("smartphone")}<span class="flex-1 text-left">Telefonda ochish (QR havola)</span>${icon("chevron-right")}</a>
        <a class="btn" href="/staff.html" target="_blank" rel="noopener" style="justify-content:space-between">${icon("building-2")}<span class="flex-1 text-left">Xodimlar konsoli (farmatsevt, ishlab chiqaruvchi)</span>${icon("external-link")}</a>
      </section>

      <details class="card" id="about">
        <summary class="flex items-center gap-2 font-semibold cursor-pointer list-none" style="min-height:28px">${icon("info", "w-5 h-5")}Ilova haqida<span class="flex-1"></span>${icon("chevron-down", "w-4 h-4 muted")}</summary>
        <div class="t-14 mt-3 grid gap-3">
          <p class="m-0"><b>Mezon</b> — dorixonada turgan bemorga bitta savolga javob beradi: «Bu doriga ishonsam bo'ladimi va u men ichayotgan boshqa dorilar bilan xavfsizmi?»</p>
          <p class="m-0"><b>Muhim:</b> Mezon tashxis qo'ymaydi, dori tayinlamaydi va dozani belgilamaydi. Har bir ogohlantirish oxirida — shifokor yoki farmatsevt bilan maslahatlashing.</p>
          <p class="m-0"><b>Ma'lumot manbalari:</b> Asl Belgisi markirovka tizimi (bu demoda — nusxa/mock), ishlab chiqaruvchining tahlil sertifikatlari (CoA), dori yo'riqnomalari (masalan, Tylol Hot qisqa mahsulot ma'lumoti), farmakonazorat xabarlari, farmatsevt baholari.</p>
          <p class="m-0"><b>AI qanday ishlatiladi:</b> izoh yozish, nomlarni tozalash, hujjatdan qiymat ajratish va yo'riqnomadan qoida <i>taklif qilish</i>. Ogohlantirishni faqat farmatsevt tasdiqlagan qoidalar chiqaradi.${llm ? ` Hozir: ${esc(llm.provider)} · ${esc(llm.model)} · ${llm.configured ? "ulangan" : "oflayn (tayyor natijalar)"}.` : ""}</p>
          <p class="m-0"><span class="demo-badge">Demo ma'lumot</span> — rasmiy holatlar, partiyalar, narxlar, indekslar, mahalliy ishlab chiqaruvchilar nomlari va laboratoriya natijalari namoyish uchun yaratilgan. Haqiqiy kompaniyalar haqida baho emas.</p>
        </div>
      </details>
    </div>`;
  refreshIcons(view);

  const save = async (body, msg) => {
    try { pat = await api("/api/patient", { method: "PUT", body }); if (msg) toast(msg); return true; }
    catch (e) { toast(e.message, "err"); return false; }
  };
  view.querySelector("#saveName").addEventListener("click", () => save({ name: view.querySelector("#name").value }, "Ism saqlandi"));
  view.querySelector("#name").addEventListener("keydown", (e) => { if (e.key === "Enter") save({ name: e.target.value }, "Ism saqlandi"); });
  view.querySelector("#conds").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-k]"); if (!b) return;
    const k = b.dataset.k;
    const on = b.getAttribute("aria-pressed") !== "true";
    const next = on ? [...pat.conditions, k] : pat.conditions.filter((x) => x !== k);
    if (await save({ conditions: next })) {
      b.setAttribute("aria-pressed", String(on));
      b.innerHTML = `${icon(on ? "check" : "plus")}${esc(conds.find((c) => c.key === k).label_uz)}`;
      refreshIcons(b);
    }
  });
  view.querySelector("#alc").addEventListener("change", async (e) => {
    const el = e.target;
    if (await save({ alcohol: el.checked }, el.checked ? "Paratsetamol chegarasi 2 000 mg ga tushirildi" : "Saqlandi")) el.setAttribute("aria-checked", String(el.checked));
    else el.checked = !el.checked;
  });
  view.querySelectorAll("[data-theme-opt]").forEach((b) => b.addEventListener("click", () => {
    setTheme(b.dataset.themeOpt);
    view.querySelectorAll("[data-theme-opt]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  }));
}
