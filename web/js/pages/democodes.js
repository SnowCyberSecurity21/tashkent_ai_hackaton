import { api } from "../api.js";
import { esc, icon, refreshIcons, errorCard, demoBadge } from "../components.js";
import { loadScript } from "../scanner.js";
import { submitCode } from "./scan.js";

export const BWIP_URL = "vendor/bwip-js-4.5.1.min.js";

export default async function demoCodesPage({ view }) {
  view.innerHTML = `<div class="grid gap-3 fade-in">
    <div class="flex items-center gap-2 mt-1">
      <a class="icon-btn" href="#/profile" aria-label="Orqaga">${icon("chevron-left")}</a>
      <div class="flex-1"><h1 class="t-18">Demo kodlar</h1><div class="t-12 muted">Ikkinchi ekranda oching va telefon bilan skanerlang</div></div>
      ${demoBadge()}
    </div>
    <div id="grid" class="grid grid-cols-2 gap-3">${Array.from({ length: 6 }, () => `<div class="skel" style="height:220px"></div>`).join("")}</div>
  </div>`;
  refreshIcons(view);
  let data;
  try {
    [data] = await Promise.all([api("/api/codes"), loadScript(BWIP_URL, "bwipjs")]);
  } catch (e) {
    view.querySelector("#grid").outerHTML = errorCard(e.message);
    refreshIcons(view);
    view.querySelector("[data-retry]")?.addEventListener("click", () => demoCodesPage({ view }));
    return;
  }
  const grid = view.querySelector("#grid");
  grid.innerHTML = data.featured.map((f, i) => `
    <figure class="card m-0 grid gap-2 justify-items-center text-center min-w-0" style="padding:12px">
      <div style="background:#fff;padding:10px;border-radius:12px;line-height:0"><canvas style="max-width:100%;height:auto" data-c="${i}" aria-label="${esc(f.label)} kodi"></canvas></div>
      <figcaption class="t-14 font-semibold">${esc(f.label)}</figcaption>
      <div class="t-12 muted" style="word-break:break-all;font-family:ui-monospace,Consolas,monospace">${esc(f.element_string)}</div>
      <button class="btn btn-sm btn-soft" data-go="${i}">${icon("play")}Shu yerda tekshirish</button>
    </figure>`).join("");
  refreshIcons(grid);
  data.featured.forEach((f, i) => {
    const canvas = grid.querySelector(`[data-c="${i}"]`);
    try {
      if (f.scenario === "ean13") window.bwipjs.toCanvas(canvas, { bcid: "ean13", text: f.element_string, scale: 2, height: 16, includetext: true });
      else window.bwipjs.toCanvas(canvas, { bcid: "gs1datamatrix", text: f.element_string, scale: 4, padding: 0 });
    } catch (e) {
      canvas.replaceWith(Object.assign(document.createElement("div"), { className: "t-12 ct-red", textContent: "Kodni chizib bo'lmadi" }));
    }
  });
  grid.addEventListener("click", (e) => {
    const b = e.target.closest("[data-go]");
    if (b) submitCode(data.featured[+b.dataset.go].element_string, { button: b });
  });
}
