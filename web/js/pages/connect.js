// "/#/connect": the app's own URL as a big QR code, so a mentor can open Mezon on their phone from the laptop screen.
import { esc, icon, refreshIcons, toast, errorCard } from "../components.js";
import { loadScript } from "../scanner.js";
import { BWIP_URL } from "./democodes.js";

const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "::1", "0.0.0.0"];

export default async function connectPage({ view }) {
  const url = location.origin + location.pathname + "#/";
  const local = LOCAL_HOSTS.includes(location.hostname);
  const https = location.protocol === "https:";
  view.innerHTML = `<div class="grid gap-4 fade-in">
    <div class="flex items-center gap-2 mt-1">
      <a class="icon-btn" href="#/profile" aria-label="Orqaga">${icon("chevron-left")}</a>
      <div class="flex-1"><h1 class="t-18">Telefonda ochish</h1><div class="t-12 muted">Telefon kamerasi bilan QR kodni skanerlang</div></div>
    </div>
    ${local ? `<div class="banner banner-amber">${icon("triangle-alert")}<div><div class="font-semibold">Bu manzil faqat shu kompyuterda ishlaydi</div>
      <div class="t-14 banner-sub">Telefon «${esc(location.host)}» ni ocholmaydi. Kompyuterda <b>tunnel.bat</b> ni ishga tushiring va chiqqan
      <b>https://…trycloudflare.com/#/connect</b> havolasini shu brauzerda oching — QR kod o'sha manzilni ko'rsatadi.</div></div></div>`
      : !https ? `<div class="banner banner-amber">${icon("camera-off")}<div><div class="font-semibold">HTTPS emas — telefonda kamera ishlamaydi</div>
      <div class="t-14 banner-sub">Ilova ochiladi, lekin skaner uchun demo kodlar yoki qo'lda kiritishdan foydalaning. Kamera uchun tunnel.bat bilan HTTPS havola oling.</div></div></div>` : ""}
    <section class="card grid justify-items-center gap-3 text-center" style="padding:20px">
      <div id="qrBox" style="background:#fff;padding:16px;border-radius:16px;line-height:0;width:min(100%,340px)">
        <div class="skel" style="width:100%;aspect-ratio:1"></div>
      </div>
      <div class="t-18 font-semibold" style="word-break:break-all" id="qrUrl">${esc(url)}</div>
      <button class="btn btn-soft" id="copyUrl">${icon("copy")}Havolani nusxalash</button>
    </section>
    <p class="t-12 muted text-center">Demo ma'lumot. Havola faqat ushbu taqdimot serveriga olib boradi.</p>
  </div>`;
  refreshIcons(view);
  view.querySelector("#copyUrl").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(url); toast("Havola nusxalandi", "ok", 1800); }
    catch { toast("Nusxalab bo'lmadi — havolani qo'lda belgilang", "err"); }
  });
  try {
    await loadScript(BWIP_URL, "bwipjs");
  } catch (e) {
    view.querySelector("#qrBox").outerHTML = errorCard(e.message);
    refreshIcons(view);
    view.querySelector("[data-retry]")?.addEventListener("click", () => connectPage({ view }));
    return;
  }
  const box = view.querySelector("#qrBox");
  if (!box) return;
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-label", "Ilova havolasi QR kodi");
  canvas.style.cssText = "width:100%;height:auto;image-rendering:pixelated";
  try {
    window.bwipjs.toCanvas(canvas, { bcid: "qrcode", text: url, scale: 8, eclevel: "M", padding: 0 });
    box.replaceChildren(canvas);
  } catch {
    box.innerHTML = `<div class="t-14 ct-red" style="line-height:1.4">QR kodni chizib bo'lmadi — havolani qo'lda kiriting.</div>`;
  }
}
