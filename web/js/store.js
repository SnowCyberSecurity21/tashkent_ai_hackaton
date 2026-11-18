// Per-viewer conveniences only (recent scans list, chosen city). Safe if storage is unavailable.
import { storageGet, storageSet } from "./theme.js";

const RECENT = "mezon.recent";
let memRecent = null;

export function getRecent() {
  return memRecent || storageGet(RECENT, []) || [];
}
export function addRecent(scan) {
  const item = {
    scan_id: scan.scan_id, product_id: scan.product.id, name: scan.product.trade_name,
    score: scan.trust.score, color: scan.trust.color, color_word: scan.trust.color_word,
    banner: scan.banner.color, ts: scan.ts || new Date().toISOString(),
  };
  const list = [item, ...getRecent().filter((r) => r.scan_id !== item.scan_id)].slice(0, 12);
  memRecent = list;
  storageSet(RECENT, list);
}
// After "Demoni qayta boshlash" in the staff console the server forgets post-seed scans: drop the local list too.
export function syncDemoReset(resetAt) {
  if (!resetAt || storageGet("mezon.resetAt", null) === resetAt) return false;
  storageSet("mezon.resetAt", resetAt);
  const had = getRecent().length > 0;
  memRecent = [];
  storageSet(RECENT, []);
  return had;
}
export function getCity() { return storageGet("mezon.city", "Toshkent"); }
export function setCity(c) { storageSet("mezon.city", c); }
export const CITIES = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Namangan", "Farg'ona", "Nukus", "Qarshi", "Xiva", "Termiz"];
