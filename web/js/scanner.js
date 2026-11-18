// Barcode reading for the Skaner page.
// Camera: native BarcodeDetector first (Android Chrome = Google ML Kit, same engine as the phone's own scanner),
// otherwise @zxing/library on a crop of the on-screen frame. Images: BarcodeDetector -> ZXing (downscaled, centre
// crop, rotations) -> server POST /api/decode-image (zxing-cpp). ZXing is loaded lazily from web/vendor (offline-safe).
import { api } from "./api.js";

const ZXING_URL = "vendor/zxing-library-0.21.3.min.js";
const NATIVE_FORMATS = ["data_matrix", "ean_13", "qr_code"];
const DETECT_EVERY_MS = 150; // native detector
const ZXING_EVERY_MS = 220;  // ZXing is heavier: a bit slower cadence
const FRAME_FRACTION = 0.64; // .cam .frame has inset 18% -> the centre 64% of the visible square
export const NOT_FOUND_UZ = "Kod topilmadi. Kodga yaqinroq va to'g'ri burchakda rasmga oling yoki kodni qo'lda kiriting.";

let loading = null;
let nativeDetector; // undefined = not checked yet, null = unavailable

export function loadScript(src, globalName) {
  if (globalName && window[globalName]) return Promise.resolve(window[globalName]);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src; s.async = true;
    s.onload = () => resolve(globalName ? window[globalName] : true);
    s.onerror = () => reject(new Error("Kutubxonani yuklab bo'lmadi (serverni tekshiring)"));
    document.head.appendChild(s);
  });
}

export function loadZXing() {
  if (!loading) loading = loadScript(ZXING_URL, "ZXing").catch((e) => { loading = null; throw e; });
  return loading;
}

/** BarcodeDetector that supports Data Matrix, or null. */
export async function getNativeDetector() {
  if (nativeDetector !== undefined) return nativeDetector;
  nativeDetector = null;
  try {
    if ("BarcodeDetector" in window) {
      const supported = await window.BarcodeDetector.getSupportedFormats();
      if (supported.includes("data_matrix")) {
        nativeDetector = new window.BarcodeDetector({ formats: NATIVE_FORMATS.filter((f) => supported.includes(f)) });
      }
    }
  } catch { nativeDetector = null; }
  return nativeDetector;
}

function zxingReader(Z) {
  const hints = new Map();
  hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [Z.BarcodeFormat.DATA_MATRIX, Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.QR_CODE]);
  hints.set(Z.DecodeHintType.TRY_HARDER, true);
  const reader = new Z.MultiFormatReader();
  reader.setHints(hints);
  return reader;
}

/** One ZXing attempt on a canvas; returns text or null. */
function zxingCanvas(Z, reader, canvas) {
  try {
    const bitmap = new Z.BinaryBitmap(new Z.HybridBinarizer(new Z.HTMLCanvasElementLuminanceSource(canvas)));
    return reader.decodeWithState(bitmap).getText();
  } catch { return null; } finally { try { reader.reset(); } catch { /* ignore */ } }
}

function drawTo(canvas, src, sx, sy, sw, sh, dw, dh, rotate = 0) {
  const swap = rotate % 180 !== 0;
  canvas.width = swap ? dh : dw; canvas.height = swap ? dw : dh;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.save();
  if (rotate) { ctx.translate(canvas.width / 2, canvas.height / 2); ctx.rotate((rotate * Math.PI) / 180); ctx.translate(-dw / 2, -dh / 2); }
  ctx.drawImage(src, sx, sy, sw, sh, 0, 0, dw, dh);
  ctx.restore();
  return canvas;
}

export function cameraSupport() {
  if (!window.isSecureContext) return { ok: false, reason: "insecure" };
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return { ok: false, reason: "unsupported" };
  return { ok: true };
}

export function cameraErrorText(err) {
  const name = err && (err.name || err.reason);
  if (name === "insecure") return "Kamera faqat xavfsiz (HTTPS) ulanishda ishlaydi. Telefon uchun tunnel havolasidan (https://…) foydalaning.";
  if (name === "unsupported") return "Bu brauzer kamerani qo'llab-quvvatlamaydi. Rasm yuklang yoki kodni qo'lda kiriting.";
  if (name === "NotAllowedError" || name === "SecurityError") return "Kameraga ruxsat berilmadi. Brauzer sozlamalaridan ruxsat bering yoki pastdagi usullardan foydalaning.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "Kamera topilmadi. Rasm yuklang yoki kodni qo'lda kiriting.";
  if (name === "NotReadableError") return "Kamera boshqa ilova tomonidan band. Uni yopib, qayta urinib ko'ring.";
  return (err && err.message) || "Kamerani ishga tushirib bo'lmadi.";
}

async function openStream() {
  const ideal = {
    audio: false,
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 }, advanced: [{ focusMode: "continuous" }] },
  };
  try { return await navigator.mediaDevices.getUserMedia(ideal); }
  catch (e) {
    if (e && (e.name === "OverconstrainedError" || e.name === "TypeError")) {
      return navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" } } });
    }
    throw e;
  }
}

/** Focus, zoom and torch from the track's capabilities. Returns {torch: bool, zoom: number|null}. */
async function tuneTrack(track) {
  const caps = (track.getCapabilities && track.getCapabilities()) || {};
  const adv = {};
  if (Array.isArray(caps.focusMode) && caps.focusMode.includes("continuous")) adv.focusMode = "continuous";
  let zoom = null;
  if (caps.zoom && typeof caps.zoom.max === "number" && caps.zoom.max > 1) {
    zoom = Math.max(caps.zoom.min || 1, Math.min(caps.zoom.max, 1.8)); // a small code fills more pixels
    adv.zoom = zoom;
  }
  if (Object.keys(adv).length) {
    try { await track.applyConstraints({ advanced: [adv] }); }
    catch {
      for (const [k, v] of Object.entries(adv)) { try { await track.applyConstraints({ advanced: [{ [k]: v }] }); } catch { /* unsupported */ } }
    }
  }
  return { torch: !!caps.torch, zoom };
}

/**
 * Starts the camera and continuous decoding. onResult(text, engine) is called once.
 * Returns a controller: { stop(), torchSupported, setTorch(on), engine }.
 */
export async function startCamera(video, onResult) {
  const sup = cameraSupport();
  if (!sup.ok) throw { name: sup.reason };
  const detector = await getNativeDetector();
  const Z = detector ? null : await loadZXing();
  const reader = Z ? zxingReader(Z) : null;
  const stream = await openStream();
  const track = stream.getVideoTracks()[0];
  video.setAttribute("playsinline", ""); video.muted = true;
  video.srcObject = stream;
  try { await video.play(); } catch { /* autoplay policies: the stream still renders */ }
  const tuned = await tuneTrack(track).catch(() => ({ torch: false, zoom: null }));

  let stopped = false, raf = 0, last = 0, busy = false, tick = 0;
  const canvas = document.createElement("canvas");
  const stop = () => {
    stopped = true;
    cancelAnimationFrame(raf);
    stream.getTracks().forEach((t) => { try { t.stop(); } catch { /* ignore */ } });
    video.srcObject = null;
  };
  const found = (text, engine) => {
    if (stopped || !text) return;
    try { if (!navigator.userActivation || navigator.userActivation.hasBeenActive) navigator.vibrate && navigator.vibrate(60); } catch { /* ignore */ }
    stop();
    onResult(text, engine);
  };

  async function attempt() {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return;
    if (detector) {
      const codes = await detector.detect(video);
      const best = codes.find((c) => c.format === "data_matrix") || codes[0];
      if (best && best.rawValue) found(best.rawValue, "native");
      return;
    }
    // ZXing: decode the area inside the on-screen frame; every 3rd try a tighter, upscaled crop for tiny codes
    const tight = tick++ % 3 === 2;
    const side = Math.round(Math.min(vw, vh) * (tight ? FRAME_FRACTION * 0.6 : FRAME_FRACTION));
    const out = Math.min(tight ? 900 : 1000, Math.max(side, 600));
    drawTo(canvas, video, (vw - side) / 2, (vh - side) / 2, side, side, out, out);
    const text = zxingCanvas(Z, reader, canvas);
    if (text) found(text, "zxing");
  }

  const loop = (t) => {
    if (stopped) return;
    raf = requestAnimationFrame(loop);
    if (busy || t - last < (detector ? DETECT_EVERY_MS : ZXING_EVERY_MS)) return;
    last = t; busy = true;
    attempt().catch(() => {}).finally(() => { busy = false; });
  };
  raf = requestAnimationFrame(loop);

  return {
    stop,
    engine: detector ? "native" : "zxing",
    torchSupported: tuned.torch,
    zoom: tuned.zoom,
    async setTorch(on) {
      try { await track.applyConstraints({ advanced: [{ torch: !!on }] }); return true; } catch { return false; }
    },
  };
}

async function loadImage(file) {
  if (window.createImageBitmap) {
    try { return await createImageBitmap(file, { imageOrientation: "from-image" }); } catch { /* fall through */ }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return img;
  } finally { setTimeout(() => URL.revokeObjectURL(url), 0); }
}

/** Decodes a photo: native detector -> ZXing (several tries) -> server (zxing-cpp). Throws with NOT_FOUND_UZ. */
export async function decodeImageFile(file) {
  let img = null;
  try { img = await loadImage(file); } catch { img = null; }
  if (img) {
    const detector = await getNativeDetector();
    if (detector) {
      try {
        const codes = await detector.detect(img);
        const best = codes.find((c) => c.format === "data_matrix") || codes[0];
        if (best && best.rawValue) return best.rawValue;
      } catch { /* fall through */ }
    }
    try {
      const Z = await loadZXing();
      const reader = zxingReader(Z);
      const w = img.width, h = img.height, canvas = document.createElement("canvas");
      const k = Math.min(1, 1600 / Math.max(w, h));
      const side = Math.min(w, h) * 0.5, cs = Math.min(1200, Math.max(side, 800));
      const tries = [
        () => drawTo(canvas, img, 0, 0, w, h, Math.round(w * k), Math.round(h * k)),                // full, max 1600 px
        () => drawTo(canvas, img, (w - side) / 2, (h - side) / 2, side, side, cs, cs),              // centre crop
        () => drawTo(canvas, img, 0, 0, w, h, Math.round(w * k), Math.round(h * k), 90),            // rotations
        () => drawTo(canvas, img, (w - side) / 2, (h - side) / 2, side, side, cs, cs, 90),
      ];
      for (const draw of tries) {
        const text = zxingCanvas(Z, reader, draw());
        if (text) return text;
        await new Promise((r) => setTimeout(r, 0)); // keep the UI responsive between tries
      }
    } catch { /* ZXing unavailable: the server still tries */ }
  }
  // server fallback: zxing-cpp handles small codes in large photos
  const form = new FormData();
  form.append("file", file, file.name || "photo.jpg");
  try {
    const res = await api("/api/decode-image", { method: "POST", form });
    if (res && res.text) return res.text;
  } catch (e) {
    if (e && e.status && e.status !== 404) throw e;
  }
  throw new Error(NOT_FOUND_UZ);
}
