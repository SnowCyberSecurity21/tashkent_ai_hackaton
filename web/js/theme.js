// Theme: "auto" follows prefers-color-scheme; "light" (sut) / "dark" are manual. Persisted best-effort.
const KEY = "mezon.theme";

export function storageGet(key, fallback = null) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
}
export function storageSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode etc. */ }
}

export function getTheme() { return storageGet(KEY, "auto"); }

export function isDark() {
  const t = document.documentElement.dataset.theme;
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(theme = getTheme()) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", isDark() ? "#0E1315" : "#FAF7F0");
  window.dispatchEvent(new CustomEvent("themechange"));
}

export function setTheme(theme) { storageSet(KEY, theme); applyTheme(theme); }

if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => applyTheme());
}
