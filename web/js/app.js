import { route, fallback, onAfterRender, start } from "./router.js";
import { applyTheme } from "./theme.js";
import { $, $$, refreshIcons, empty, icon } from "./components.js";
import home from "./pages/home.js";
import scan from "./pages/scan.js";
import product from "./pages/product.js";
import analogs from "./pages/analogs.js";
import meds from "./pages/meds.js";
import profile from "./pages/profile.js";
import demoCodes from "./pages/democodes.js";
import connect from "./pages/connect.js";

applyTheme();

const root = $("#view");
// every render gets a fresh container: a slow, stale page render writes into a detached node
function fresh() {
  const view = document.createElement("div");
  root.classList.remove("has-actions");
  root.replaceChildren(view);
  return { view, root };
}

route("/", () => home(fresh()));
route("/scan", (r) => scan(fresh(), r));
route("/product/:id", (r) => product(fresh(), r));
route("/analogs/:id", (r) => analogs(fresh(), r));
route("/meds", (r) => meds(fresh(), r));
route("/profile", () => profile(fresh()));
route("/demo-codes", () => demoCodes(fresh()));
route("/connect", () => connect(fresh()));
fallback(() => {
  const { view } = fresh();
  view.innerHTML = empty("map-pin-off", "Sahifa topilmadi", "Bunday bo'lim yo'q.", `<a class="btn btn-primary" href="#/">${icon("house")}Bosh sahifa</a>`);
});

const TAB_OF = { "/": "/", "/scan": "/scan", "/product/:id": "/scan", "/analogs/:id": "/scan", "/meds": "/meds", "/profile": "/profile", "/demo-codes": "/profile" };
onAfterRender(({ pattern }) => {
  const tab = TAB_OF[pattern] || null;
  $$(".tab").forEach((a) => { if (a.dataset.tab === tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  refreshIcons();
  window.scrollTo({ top: 0 });
});

window.addEventListener("scroll", () => $("#topbar").classList.toggle("scrolled", window.scrollY > 4), { passive: true });
start();
refreshIcons();
