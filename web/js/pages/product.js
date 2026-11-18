import { api } from "../api.js";
import {
  esc, icon, banner, gauge, animateGauges, compBar, skeleton, errorCard, refreshIcons, openSheet, toast, fmtMoney,
  fmtMg, cap, SEV, sourceTag, demoBadge, $, trustPill,
} from "../components.js";
import { openAddFlow } from "./addflow.js";

function alertRow(a) {
  const s = SEV[a.severity] || SEV.info;
  return `<div class="alert-row">
    <div class="alert-ico ${s.cls}">${icon(a.icon || s.icon)}</div>
    <div class="min-w-0 flex-1">
      <div class="t-14 font-semibold">${esc(a.title_uz)}</div>
      ${a.detail_uz ? `<div class="t-14 muted">${esc(a.detail_uz)}</div>` : ""}
    </div>
    <span class="pill tone-${s.tone} self-start">${esc(s.word)}</span>
  </div>`;
}

function coaTable(coa) {
  if (!coa) return `<div class="soft p-3 t-14 muted flex gap-2">${icon("file-question", "w-5 h-5 flex-none")}Bu partiya uchun laboratoriya sertifikati (CoA) hali yuklanmagan.</div>`;
  const spec = (r) => r.spec_min != null && r.spec_max != null ? `${fmtMg(r.spec_min)}–${fmtMg(r.spec_max)}`
    : r.spec_min != null ? `≥ ${fmtMg(r.spec_min)}` : r.spec_max != null ? `≤ ${fmtMg(r.spec_max)}` : "—";
  return `<div class="flex items-center justify-between gap-2 mb-2">
      <div class="t-14"><b>Tahlil sertifikati</b> · partiya ${esc(coa.batch_no)}${coa.other_batch ? ` <span class="pill tone-info">boshqa partiya</span>` : ""}</div>
      <a class="btn btn-ghost btn-sm" href="/api/documents/${coa.document_id}/file" target="_blank" rel="noopener">${icon("file-text")}PDF</a>
    </div>
    <div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>Ko'rsatkich</th><th class="text-right">Natija</th><th class="text-right">Me'yor</th><th></th></tr></thead>
      <tbody>${coa.results.map((r) => `<tr>
        <td>${esc(r.parameter)}</td>
        <td class="text-right num">${fmtMg(r.value)} ${esc(r.unit)}</td>
        <td class="text-right num muted">${spec(r)}</td>
        <td class="text-right">${r.status === "ok" ? `<span class="pill tone-green">${icon("check")}Mos</span>` : `<span class="pill tone-red">${icon("x")}Mos emas</span>`}</td>
      </tr>`).join("")}</tbody>
    </table></div>
    <div class="t-12 muted mt-2">Sana: ${esc(coa.date)} · SHA-256: ${esc(coa.sha256 || "—")}… · ${demoBadge("Demo hujjat")}</div>`;
}

async function openCompare(productId) {
  const sh = openSheet({ title: "Asl Belgisi bilan solishtirish", wide: true, center: true, body: skeleton(1) });
  try {
    const d = await api(`/api/products/${productId}/compare`);
    sh.setBody(`
      <p class="t-14 muted mt-0">Chapda — rasmiy ilovadagi xom maydonlar (qanday bo'lsa shunday). O'ngda — Mezon talqini. O'zgargan qatorlar belgilangan.</p>
      <div class="tbl-wrap"><table class="tbl" style="table-layout:fixed">
        <thead><tr><th style="width:50%">${icon("database", "inline w-3 h-3")} Asl Belgisi (xom) ${demoBadge("demo nusxa")}</th><th>${icon("sparkles", "inline w-3 h-3")} Mezon talqini</th></tr></thead>
        <tbody>${d.rows.map((r) => `<tr class="compare-row ${r.danger ? "danger" : r.changed ? "changed" : ""}">
          <td><div class="t-12 muted">${esc(r.label)}</div><div class="t-14" style="font-family:ui-monospace,Consolas,monospace;word-break:break-word">${esc(r.raw)}</div></td>
          <td><div class="t-12 muted">${r.changed ? `${icon("pencil", "inline w-3 h-3")} ${esc(r.note || "tozalandi")}` : "o'zgarishsiz"}</div><div class="t-14 ${r.danger ? "ct-red font-semibold" : ""}" style="word-break:break-word">${esc(r.clean)}</div></td>
        </tr>`).join("")}</tbody>
      </table></div>
      ${d.ai_notes.length ? `<div class="soft p-3 mt-3 t-14">
        <div class="font-semibold flex items-center gap-2">${icon("sparkles", "w-4 h-4")}INN nomlari normalizatsiyasi</div>
        ${d.ai_notes.map((n) => `<div class="mt-1"><span style="text-decoration:line-through;opacity:.7">${esc(n.raw)}</span> → <b>${esc(n.inn)}</b> <span class="t-12 muted">(${n.source === "live" || n.source === "cache" ? "AI" : "lug'at"})</span></div>`).join("")}
        <div class="t-12 muted mt-2">Normalizatsiya faqat nomni tozalaydi; ogohlantirishlar tasdiqlangan qoidalardan olinadi.</div>
      </div>` : ""}`);
  } catch (e) { sh.setBody(errorCard(e.message)); }
}

function openReport(product, batchNo) {
  let stars = 0;
  const sh = openSheet({
    title: "Xabar qoldirish",
    body: `<p class="t-14 muted mt-0">Nojo'ya ta'sir, sifat yoki qadoq bo'yicha shikoyatingizni yozing. Ism va telefon raqamini yozmang — ular avtomatik yashiriladi.</p>
      <label class="label" for="repText">Nima bo'ldi?</label>
      <textarea id="repText" class="textarea" style="font-family:inherit;font-size:16px" maxlength="2000" placeholder="Masalan: ichgandan keyin terimda toshma paydo bo'ldi"></textarea>
      <div class="mt-3"><div class="label">Dorini baholang (ixtiyoriy)</div>
        <div class="flex gap-1" id="stars" role="radiogroup" aria-label="Baho">${[1, 2, 3, 4, 5].map((i) => `<button class="icon-btn" data-s="${i}" role="radio" aria-checked="false" aria-label="${i} yulduz">${icon("star")}</button>`).join("")}</div>
      </div>
      <button class="btn btn-primary btn-block mt-4" id="repGo">${icon("send")}Yuborish</button>
      <div id="repOut" class="mt-3"></div>`,
  });
  const b = sh.body;
  b.querySelector("#stars").addEventListener("click", (e) => {
    const t = e.target.closest("[data-s]"); if (!t) return;
    stars = +t.dataset.s;
    b.querySelectorAll("[data-s]").forEach((el) => {
      const on = +el.dataset.s <= stars;
      el.setAttribute("aria-checked", String(+el.dataset.s === stars));
      el.style.color = on ? "var(--accent)" : "";
      el.querySelector("svg")?.setAttribute("fill", on ? "currentColor" : "none");
    });
  });
  b.querySelector("#repGo").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const text = b.querySelector("#repText").value.trim();
    if (text.length < 3 && !stars) { toast("Xabar matnini yozing yoki baho bering", "err"); return; }
    btn.disabled = true;
    try {
      let out = "";
      if (stars) await api("/api/ratings", { method: "POST", body: { product_id: product.id, stars } });
      if (text.length >= 3) {
        const r = await api("/api/reports", { method: "POST", body: { product_id: product.id, batch_no: batchNo, text } });
        out = `<div class="banner banner-green fade-in">${icon("circle-check")}<div><div class="font-semibold">${esc(r.message_uz)}</div>
          <div class="t-14 banner-sub">Toifa: <b>${esc(r.category)}</b> · darajasi: <b>${esc(r.severity_uz)}</b> · ${r.classified_by === "ai" ? "AI tasnifladi" : "kalit so'zlar bo'yicha tasniflandi"}</div></div></div>`;
      } else out = `<div class="banner banner-green fade-in">${icon("circle-check")}<div class="font-semibold">Bahoyingiz uchun rahmat!</div></div>`;
      b.querySelector("#repOut").innerHTML = out;
      refreshIcons(b);
      btn.textContent = "Yuborildi";
      setTimeout(sh.close, 2600);
    } catch (err) { btn.disabled = false; toast(err.message, "err"); }
  });
}

export default async function productPage({ view, root }, { params, query }) {
  let alive = true;
  root.classList.add("has-actions");
  const load = async () => {
    view.innerHTML = skeleton(4);
    try {
      return query.scan ? await api(`/api/scans/${query.scan}`) : await api(`/api/products/${params.id}`);
    } catch (e) {
      view.innerHTML = errorCard(e.message);
      refreshIcons(view);
      view.querySelector("[data-retry]").addEventListener("click", () => render());
      return null;
    }
  };

  async function render() {
    const d = await load();
    if (!d || !alive) return;
    const p = d.product, t = d.trust, b = d.batch;
    const scanned = !!query.scan;
    view.innerHTML = `
      <div class="grid gap-3 fade-in">
        <div class="flex items-center gap-2 -mt-1">
          <a class="icon-btn" href="${scanned ? "#/scan" : "javascript:history.back()"}" aria-label="Orqaga">${icon("chevron-left")}</a>
          <div class="min-w-0 flex-1">
            <h1 class="t-18 truncate" title="${esc(p.trade_name)}">${esc(p.trade_name)}</h1>
            <div class="t-12 muted truncate">${esc(p.manufacturer)} · ${esc(p.country)} · ${p.is_local ? "mahalliy" : "import"}</div>
          </div>
        </div>
        ${banner(d.banner)}

        <section class="card" aria-labelledby="h-off">
          <div class="card-title" id="h-off">${icon("landmark")}Rasmiy holat <span class="flex-1"></span>${demoBadge()}</div>
          ${d.alerts.map(alertRow).join("") || `<div class="t-14 muted">Ogohlantirish yo'q.</div>`}
          ${scanned ? `<div class="t-12 muted mt-2">Skan: ${esc(d.city)} · seriya ${esc(d.parsed?.serial || "—")} · ${d.parsed?.kind === "ean13" ? "EAN-13" : "GS1 Data Matrix"}</div>` : ""}
          <button class="btn btn-soft btn-block mt-3" id="cmpBtn">${icon("columns-2")}Asl Belgisi bilan solishtirish</button>
        </section>

        <section class="card" aria-labelledby="h-trust">
          <div class="card-title" id="h-trust">${icon("gauge")}Ishonch indeksi</div>
          <div class="flex items-center gap-4">
            ${gauge(t.score, t.color)}
            <div class="min-w-0">
              <div class="t-18 ct-${t.color}">${esc(t.label)}</div>
              <div class="t-14 muted mt-1">${t.color === "gray" ? "Laboratoriya hujjati yo'q va skanlar kam — indeks ishonchli emas." : "5 ta mustaqil manba asosida 0–100 ball."}</div>
              <div class="t-12 muted mt-2 num">${esc(t.formula)}</div>
            </div>
          </div>
          <div class="mt-3">${t.components.map(compBar).join("")}</div>
          <div class="t-12 muted">Komponent ustiga bosing — sabab va manba ko'rinadi.</div>
        </section>

        <section class="card" aria-labelledby="h-ai">
          <div class="card-title" id="h-ai">${icon("sparkles")}AI izohi <span class="t-12 muted font-normal">· tashxis emas</span></div>
          <p class="m-0 t-16" id="aiText">${esc(d.explanation_uz)}</p>
          <div class="flex items-center gap-2 mt-3 flex-wrap" id="aiMeta">${sourceTag(d.explanation_source, d.explanation_model)}</div>
          <p class="t-12 muted mt-2 mb-0">AI faqat tushuntiradi: ogohlantirishlarni tasdiqlangan qoidalar chiqaradi. Shifokor yoki farmatsevt bilan maslahatlashing.</p>
        </section>

        <section class="card" aria-labelledby="h-comp">
          <div class="card-title" id="h-comp">${icon("flask-round")}Tarkib</div>
          <div class="flex flex-wrap gap-2">${p.inn_list.map((c) => `<span class="chip chip-static">${icon("atom")}${esc(cap(c.inn))} <b class="num">${fmtMg(c.amount_mg)} mg</b></span>`).join("")}</div>
          <dl class="grid grid-cols-2 gap-x-3 gap-y-2 mt-3 t-14" style="margin-bottom:0">
            <div><dt class="t-12 muted">Shakli</dt><dd class="m-0">${esc(cap(p.dose_form))}</dd></div>
            <div><dt class="t-12 muted">Qabul usuli</dt><dd class="m-0">${esc(p.route_label)}</dd></div>
            <div><dt class="t-12 muted">Yaroqlilik muddati</dt><dd class="m-0">${esc(p.shelf_life)}</dd></div>
            <div><dt class="t-12 muted">Berilishi</dt><dd class="m-0">${p.rx_only ? "Retsept bilan" : "Retseptsiz"}</dd></div>
            <div><dt class="t-12 muted">Taxminiy narx</dt><dd class="m-0 num">${fmtMoney(p.price_uzs)}</dd></div>
            <div><dt class="t-12 muted">GTIN</dt><dd class="m-0 num t-12" style="word-break:break-all">${esc(p.gtin)}</dd></div>
          </dl>
        </section>

        <section class="card" aria-labelledby="h-batch">
          <div class="card-title" id="h-batch">${icon("package")}Partiya</div>
          ${b ? `<div class="flex items-center justify-between gap-3 mb-3">
              <div><div class="t-12 muted">Partiya raqami</div><div class="font-semibold num">${esc(b.batch_no || "—")}</div></div>
              <div class="text-right"><div class="t-12 muted">Yaroqlilik muddati</div><div class="font-semibold">${esc(b.exp_label || "—")}</div>
                ${b.days_left != null ? `<span class="pill ${b.days_left < 0 ? "tone-red" : b.days_left <= 90 ? "tone-amber" : "tone-green"}">${icon("clock")}${b.days_left < 0 ? `${-b.days_left} kun o'tgan` : `${b.days_left} kun qoldi`}</span>` : ""}
              </div>
            </div>` : `<div class="t-14 muted mb-3">Partiya ma'lumoti uchun Data Matrix kodini skanerlang.</div>`}
          ${coaTable(d.coa)}
        </section>

        ${!p.is_local && d.analogs_count ? `<a class="card flex items-center gap-3" href="#/analogs/${p.id}" style="text-decoration:none;color:inherit">
            <div class="alert-ico tone-green">${icon("badge-percent")}</div>
            <div class="flex-1 min-w-0"><div class="font-semibold">Mahalliy analog bor</div>
              <div class="t-14 muted">${esc(d.analogs[0].trade_name)} · ${trustPill(d.analogs[0].trust)} · −${d.analogs[0].savings_pct}%</div></div>
            ${icon("chevron-right", "w-5 h-5 muted")}
          </a>` : ""}
        <p class="t-12 muted text-center">Mezon tashxis qo'ymaydi va dori tayinlamaydi.</p>
      </div>
      <div class="actionbar">
        <div class="grid ${!p.is_local && d.analogs_count ? "grid-cols-[1fr_auto_auto]" : "grid-cols-[1fr_auto]"} gap-2">
          <button class="btn btn-primary" id="addBtn" style="white-space:nowrap">${icon("plus")}Dorilarimga qo'shish</button>
          ${!p.is_local && d.analogs_count ? `<a class="btn" href="#/analogs/${p.id}" aria-label="Mahalliy analoglar">${icon("arrow-left-right")}<span class="hidden min-[400px]:inline">Analoglar</span></a>` : ""}
          <button class="btn" id="repBtn" aria-label="Xabar qoldirish">${icon("message-square-warning")}</button>
        </div>
      </div>`;
    refreshIcons(view);
    animateGauges(view);
    view.querySelector("#cmpBtn").addEventListener("click", () => openCompare(p.id));
    view.querySelector("#addBtn").addEventListener("click", () => openAddFlow(p));
    view.querySelector("#repBtn").addEventListener("click", () => openReport(p, b?.batch_no));

    // upgrade the instant explanation with a live AI answer when available
    if (d.explanation_source === "precomputed") {
      const meta = view.querySelector("#aiMeta");
      meta.insertAdjacentHTML("beforeend", `<span class="pill tone-info" id="aiLive">${icon("loader-circle", "spin")}Jonli AI so'ralmoqda…</span>`);
      refreshIcons(meta);
      api("/api/explain", { method: "POST", body: query.scan ? { scan_id: +query.scan } : { product_id: p.id } })
        .then((r) => {
          if (!alive) return;
          if (r.source === "live" || r.source === "cache") {
            const el = view.querySelector("#aiText");
            el.classList.remove("fade-in"); void el.offsetWidth;
            el.textContent = r.text; el.classList.add("fade-in");
            meta.innerHTML = sourceTag(r.source, r.model);
          } else {
            view.querySelector("#aiLive")?.remove();
          }
          refreshIcons(meta);
        })
        .catch(() => { view.querySelector("#aiLive")?.remove(); });
    }
  }
  await render();
  return () => { alive = false; };
}
