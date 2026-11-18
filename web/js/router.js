// Minimal hash router: "#/product/12?scan=5" -> route "/product/:id", params {id: "12"}, query {scan: "5"}.
const routes = [];
let cleanup = null;
let notFound = null;
let afterRender = () => {};

export function route(pattern, handler) {
  const keys = [];
  const rx = new RegExp("^" + pattern.replace(/:([a-zA-Z]+)/g, (_, k) => { keys.push(k); return "([^/]+)"; }) + "/?$");
  routes.push({ pattern, rx, keys, handler });
}
export function fallback(handler) { notFound = handler; }
export function onAfterRender(fn) { afterRender = fn; }

export function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs = ""] = raw.split("?");
  const query = Object.fromEntries(new URLSearchParams(qs));
  return { path: path || "/", query };
}

export function navigate(to, { replace = false } = {}) {
  const target = to.startsWith("#") ? to : "#" + to;
  if (replace) history.replaceState(null, "", target);
  else if (location.hash !== target) { location.hash = target; return; }
  render();
}

export async function render() {
  const { path, query } = parseHash();
  if (typeof cleanup === "function") { try { cleanup(); } catch { /* ignore */ } }
  cleanup = null;
  for (const r of routes) {
    const m = path.match(r.rx);
    if (m) {
      const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
      const ret = await r.handler({ params, query, path, pattern: r.pattern });
      cleanup = typeof ret === "function" ? ret : null;
      afterRender({ path, pattern: r.pattern });
      return;
    }
  }
  if (notFound) { await notFound({ path, query }); afterRender({ path, pattern: null }); }
}

export function start() {
  window.addEventListener("hashchange", render);
  render();
}
