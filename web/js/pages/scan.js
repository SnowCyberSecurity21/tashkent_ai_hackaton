import { api } from "../api.js";
import { esc, icon, openSheet, toast, vibrate, refreshIcons, $ } from "../components.js";
import { navigate } from "../router.js";
import { startCamera, decodeImageFile, cameraSupport, cameraErrorText, loadZXing } from "../scanner.js";
import { addRecent, getCity, setCity, CITIES } from "../store.js";

const SCEN_ICON = {
  conformity_expired: "file-warning", import_paracetamol: "globe", local_paracetamol: "badge-check", tylol_hot: "cup-soda",
  clone: "copy", recalled: "octagon-x", expired: "calendar-x", coa_out_of_spec: "flask-conical", near_expiry: "calendar-clock",
  unknown: "shield-x", ean13: "barcode",
};

export async function submitCode(raw, { button } = {}) {
  if (button) button.disabled = true;
  try {
    const res = await api("/api/scan", { method: "POST", body: { raw, city: getCity() } });
    vibrate(40);
    addRecent(res);
    navigate(`/product/${res.product.id}?scan=${res.scan_id}`);
    return true;
  } catch (e) {
    vibrate([40, 60, 40]);
    toast(e.message, "err", 4500);
    return false;
  } finally {
    if (button) button.disabled = false;
  }
}

export default async function scanPage({ view }) {
  let stop = null;
  let alive = true;
  view.innerHTML = `
    <div class="fade-in">
      <h1 class="t-22 mt-2">Skaner</h1>
      <p class="t-14 muted mt-1 mb-3">Qadoqdagi kvadrat Data Matrix yoki shtrix-kodni (EAN-13) o'qing.</p>
      <div class="cam" id="cam">
        <video id="video" playsinline muted autoplay aria-label="Kamera ko'rinishi"></video>
        <div class="frame" hidden id="frame"></div>
        <div class="hint" hidden id="hint">Kodni 10–15 sm masofada tuting</div>
        <button class="cam-torch" id="torchBtn" hidden aria-pressed="false" type="button">${icon("flashlight")}Chiroq</button>
        <div class="cam-msg" id="camMsg">
          <div class="mx-auto w-14 h-14 rounded-2xl grid place-items-center" style="background:rgba(255,255,255,.08)">${icon("camera", "w-7 h-7")}</div>
          <div class="t-16 font-semibold">Kamera o'chiq</div>
          <div class="t-14" style="opacity:.8" id="camText">Kodni o'qish uchun kamerani yoqing.</div>
          <div><button class="btn btn-primary mt-2" id="camBtn">${icon("camera")}Kamerani yoqish</button></div>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 mt-3">
        <label class="btn" for="imgInput" tabindex="0" id="imgLabel">${icon("image")}Rasmdan o'qish</label>
        <input type="file" id="imgInput" accept="image/*" hidden>
        <button class="btn" id="manualBtn">${icon("keyboard")}Kodni qo'lda kiritish</button>
      </div>
      <div class="flex items-center justify-between gap-3 mt-3 soft px-3 py-2">
        <label for="city" class="t-14 flex items-center gap-2">${icon("map-pin", "w-4 h-4 muted")}Shahar</label>
        <select id="city" class="select" style="width:auto;min-height:40px">${CITIES.map((c) => `<option ${c === getCity() ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
      </div>
      <section class="mt-5" aria-labelledby="demoTitle">
        <div class="flex items-center justify-between gap-2">
          <h2 id="demoTitle" class="t-16 font-semibold">Demo kodlar</h2>
          <a href="#/demo-codes" class="t-14">Rasmlar ${icon("arrow-right", "inline w-4 h-4")}</a>
        </div>
        <p class="t-12 muted mt-1 mb-2">Taqdimot uchun: bosing — kod darhol tekshiriladi.</p>
        <div class="flex flex-wrap gap-2" id="chips">${Array.from({ length: 6 }, () => `<span class="skel" style="width:140px;height:36px;border-radius:999px"></span>`).join("")}</div>
      </section>
    </div>`;
  refreshIcons(view);

  view.querySelector("#city").addEventListener("change", (e) => { setCity(e.target.value); toast(`Shahar: ${e.target.value}`, "info", 1800); });

  // demo chips
  api("/api/codes").then((d) => {
    if (!alive) return;
    view.querySelector("#chips").innerHTML = d.featured.map((f, i) => `<button class="chip" data-i="${i}" title="${esc(f.element_string)}">${icon(SCEN_ICON[f.scenario] || "scan")}${esc(f.label)}</button>`).join("");
    refreshIcons(view.querySelector("#chips"));
    view.querySelector("#chips").addEventListener("click", (e) => {
      const b = e.target.closest("[data-i]");
      if (b) submitCode(d.featured[+b.dataset.i].element_string, { button: b });
    });
  }).catch((e) => { if (alive) view.querySelector("#chips").innerHTML = `<div class="t-14 muted">${esc(e.message)}</div>`; });

  // camera
  const camMsg = view.querySelector("#camMsg"), camText = view.querySelector("#camText"), camBtn = view.querySelector("#camBtn");
  const torchBtn = view.querySelector("#torchBtn");
  let torchOn = false, ctl = null;
  torchBtn.addEventListener("click", async () => {
    if (!ctl) return;
    if (await ctl.setTorch(!torchOn)) {
      torchOn = !torchOn;
      torchBtn.setAttribute("aria-pressed", String(torchOn));
      torchBtn.innerHTML = `${icon(torchOn ? "flashlight-off" : "flashlight")}Chiroq`;
      refreshIcons(torchBtn);
    } else toast("Chiroqni yoqib bo'lmadi", "err", 2000);
  });
  async function begin() {
    camBtn.disabled = true;
    camText.textContent = "Kamera ishga tushirilmoqda…";
    try {
      ctl = await startCamera(view.querySelector("#video"), async (text) => {
        view.querySelector("#frame").style.borderColor = "var(--primary)";
        torchBtn.hidden = true; torchOn = false;
        const ok = await submitCode(text);
        if (!ok && alive) { view.querySelector("#frame").style.borderColor = ""; begin(); }
      });
      stop = ctl.stop;
      if (!alive) { stop(); return; }
      camMsg.hidden = true; view.querySelector("#frame").hidden = false; view.querySelector("#hint").hidden = false;
      torchBtn.hidden = !ctl.torchSupported;
      torchBtn.setAttribute("aria-pressed", "false"); torchOn = false;
    } catch (err) {
      camText.textContent = cameraErrorText(err);
      camBtn.disabled = false;
      camBtn.innerHTML = `${icon("rotate-cw")}Qayta urinish`;
      refreshIcons(camBtn);
      if (err && (err.name === "insecure" || err.name === "unsupported")) camBtn.hidden = true;
    }
  }
  camBtn.addEventListener("click", begin);
  const sup = cameraSupport();
  if (!sup.ok) { camText.textContent = cameraErrorText({ name: sup.reason }); camBtn.hidden = true; }
  else {
    loadZXing().catch(() => {});
    try {
      const p = await navigator.permissions?.query({ name: "camera" });
      if (p && p.state === "granted" && alive) begin();
    } catch { /* permissions API unsupported */ }
  }

  // image
  view.querySelector("#imgLabel").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); view.querySelector("#imgInput").click(); } });
  view.querySelector("#imgInput").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    toast("Rasm tekshirilmoqda…", "info", 2500);
    try { await submitCode(await decodeImageFile(file)); }
    catch (err) { vibrate([40, 60, 40]); toast(err.message, "err", 4500); }
  });

  // manual entry
  view.querySelector("#manualBtn").addEventListener("click", () => {
    const sh = openSheet({
      title: "Kodni qo'lda kiritish",
      body: `<label class="label" for="rawCode">Data Matrix matni yoki EAN-13</label>
        <textarea id="rawCode" class="textarea" autofocus placeholder="(01)04007000011209(21)…(17)290430(10)EG2504P" spellcheck="false" autocapitalize="off"></textarea>
        <p class="t-12 muted mt-2">Qavsli ko'rinish, GS ajratgichli xom satr (<code>&lt;GS&gt;</code> deb yozish mumkin) yoki 13 xonali shtrix-kod qabul qilinadi.</p>
        <button class="btn btn-primary btn-block mt-3" id="rawGo">${icon("search")}Tekshirish</button>`,
    });
    const go = async () => {
      const v = sh.body.querySelector("#rawCode").value.trim();
      if (!v) { toast("Kodni kiriting", "err"); return; }
      if (await submitCode(v, { button: sh.body.querySelector("#rawGo") })) sh.close();
    };
    sh.body.querySelector("#rawGo").addEventListener("click", go);
    sh.body.querySelector("#rawCode").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } });
  });

  return () => { alive = false; if (stop) stop(); };
}
