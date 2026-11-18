# Mezon — demo ssenariysi

Quyidagi ssenariy ilovani bosqichma-bosqich ko'rib chiqish uchun. Uni ochiq demo serverda yoki lokal nusxada
bajarish mumkin:

| | Ochiq demo | Lokal ([README](README.md#ishga-tushirish)) |
|---|---|---|
| Bemor ilovasi | <https://mezon.zehnprotect.uz> | <http://localhost:8000> |
| Xodimlar konsoli | <https://mezon.zehnprotect.uz/staff.html> | <http://localhost:8000/staff.html> |
| Holat | <https://mezon.zehnprotect.uz/api/health> | <http://localhost:8000/api/health> |
| API hujjatlari | <https://mezon.zehnprotect.uz/docs> | <http://localhost:8000/docs> |

Oqim internetsiz ham ishlaydi: barcha kutubxonalar `web/vendor/` da, AI natijalari keshda va
`data/precomputed_llm.json` da.

> Har ekranda **«Demo ma'lumot»** belgisi bor: Asl Belgisi javoblari, partiyalar, narxlar va mahalliy ishlab
> chiqaruvchilar namunaviy (mock).

---

## 0. Boshlang'ich holat (1 daqiqa)

1. `/api/health` → `"ok": true`. Yangi bazada `counts.scans: 426`, `rules_approved: 19`.
   `llm.primary` / `llm.fallback` modellarni, `llm.last_status` oxirgi AI chaqiruvi qanday tugaganini
   (`live | fallback | precomputed`) ko'rsatadi.
2. Xodimlar konsoli → yuqori o'ngda **«Demoni qayta boshlash»** → **«Ha, qayta boshlash»**.
   Natija: demo bemor Aziza — gipertoniya, faqat bisoprolol; navbatda bitta (Bobur) so'rovi; AI takliflari tozalangan.
3. Ikki oyna yonma-yon:
   - **Bemor** — bosh sahifa, telefonda yoki brauzer DevTools'ning telefon rejimida (390 px).
     Bosh sahifani bir marta yangilang (oldingi «So'nggi skanlar» ro'yxati o'chadi).
   - **Xodimlar konsoli** — `staff.html`, rol: **Farmatsevt**.
4. Telefonda ochish: Profil → **«Telefonda ochish (QR havola)»** ekrandagi QR kodni ko'rsatadi.
   Kamera faqat **https://** manzilda ishlaydi; havolani Chrome yoki Safari'ning o'zida oching
   (Telegram ichidagi brauzerda emas).
5. **Haqiqiy Dentashan qutisi** (GTIN 08906045340359, partiya EU601) bazada bor: qadoqdagi Data Matrix telefon
   kamerasi bilan skanerlansa — qizil banner va *Muvofiqlik hujjati muddati tugagan*.

---

## 1. Texnik qism (10 daqiqa)

| Daq. | Nima bosiladi | Nimani ko'rsatadi |
|---|---|---|
| 0–1 | Bemor: **Skaner** → «Dentashan gel» chip | Data Matrix GS1 satri `app/gs1.py` da parse qilinadi: GTIN, seriya, partiya, muddat (DD=00 → oy oxiri). Asl Belgisi — real API mijozi shaklidagi mock. |
| 1–2 | **«Asl Belgisi bilan solishtirish»** | Chapda xom maydonlar: *Metrodonidazol -16 mg, hlorgeksedin-2.5 mg*, `36`. O'ngda tozalangan: INN lug'ati + AI normalizatsiyasi, birliklar. |
| 2–4 | Konsol: **AI qoidalari** → **«Tylol Hot yo'riqnomasidan qoida chiqarish»** (keshdan, ~0,1 s) → **«Qayta tahlil qilish»** (jonli, odatda 4–8 s) | Yagona jonli AI chaqiruvi. Zanjir: kesh → asosiy model (20 s timeout) → zaxira model bir marta → tayyor natija. Belgi: *AI · jonli · model nomi*. |
| 4–5 | Jadvaldagi **«Manba bo'limi»** ustuni, bitta qoidani **«Tasdiqlash»** | Guardrail: qoida faqat shu dorining o'z moddasiga (paratsetamol/psevdoefedrin/xlorfeniramin) tegishli va bo'lim raqami bo'lsa qabul qilinadi. Hammasi `approved=false` — farmatsevt tasdiqlamaguncha ishlamaydi. AI ogohlantirish yaratmaydi va o'chirmaydi. |
| 5–6 | Bemor: Dentashan sahifasida **«AI izohi»** | Izoh guardrail'i: javobda dozalash ko'rsatmasi bo'lsa yoki muhim ogohlantirish (masalan, *muvofiqlik hujjati*) tilga olinmasa — javob rad etiladi va zaxira/tayyor matnga o'tiladi. |
| 6–7 | Bemor: Tylol Hot → **«Dorilarimga qo'shish»** | Xavfsizlik dvigateli (`app/safety.py`) — LLM'siz, deterministik: takroriy modda → kunlik jami doza → dori+dori → dori+kasallik. Faqat tasdiqlangan qoidalar ishlaydi. |
| 7–8 | Terminal (lokal): `python -m pytest -q` va `python scripts/smoke_test.py` | Unit testlar (GS1, Ishonch indeksi, xavfsizlik, LLM fallback zanjiri, PII, skaner, demo reset) va 34 qadamli smoke test. |
| 8–10 | Lokal nusxada internetni o'chirib → Konsolda **«Qayta tahlil qilish»** | Model chaqiruvi xato beradi → *tayyor natija* va sababi ko'rsatiladi; UI to'liq ishlaydi, CDN'ga bitta ham so'rov ketmaydi. |

Qo'shimcha: `scripts/check_models.py` — modellar tezligi va mavjudligi; `scripts/warm_cache.py` — demo ekranlari
uchun AI keshini oldindan to'ldirish.

---

## 2. Biznes qism (10 daqiqa)

| Daq. | Nima bosiladi | Nimani ko'rsatadi |
|---|---|---|
| 0–2 | Bemor: Skaner → «Dentashan gel» | Bemor dorixonada bir soniyada ko'radi: qizil banner — *Muvofiqlik hujjati muddati tugagan*. Bu ma'lumot rasmiy tizimda bor, lekin oddiy odamga tushunarsiz. |
| 2–4 | «Paratsetamol (import)» → Ishonch kartasi → pastdagi **«Mahalliy analog bor»** kartasi | Import 32 000 so'm, mahalliy analog 14 000 so'm: **−56 %, 18 000 so'm tejash**, Ishonch indeksi 99 — yashil. Tarkib, miqdor, shakl, qabul usuli bir xil. |
| 4–6 | **«Farmatsevtdan tasdiq so'rash»** → Konsol: **So'rovlar** → Aziza qatorida **«Tasdiqlash»** → izoh → **«Tasdiqlash»** | Almashtirishni dastur emas, farmatsevt tasdiqlaydi. Bemor ekranida ~4 s ichida *Tasdiqlandi* chiqadi. |
| 6–9 | Konsol: chapda **Rol → Ishlab chiqaruvchi** → panel | Mahalliy ishlab chiqaruvchi ko'radi: skanlar dinamikasi, mahsulotlar bo'yicha indeks, farmakonazorat xabarlari (AI toifalagan), klon/qaytarib olish/muddat ogohlantirishlari. **«Hujjat yuklash»** — CoA yuklab indeksni oshirish. |
| 9–10 | — | **Kim to'laydi:** mahalliy ishlab chiqaruvchilar (panel, CoA tekshiruvi, ishonch belgisi — obuna); dorixona tarmoqlari (farmatsevt konsoli, almashtirish tavsiyasi); keyinchalik regulyator/sug'urta uchun anonim farmakonazorat ma'lumoti. Bemor uchun — bepul. |

Keyingi bo'lim uchun konsolda rol: **Farmatsevt**.

---

## 3. Soha (farmatsevtika) qismi (10 daqiqa)

| Daq. | Nima bosiladi | Nimani ko'rsatadi |
|---|---|---|
| 0–1 | Bemor: **Profil** | Demo bemor Aziza: gipertoniya, bisoprolol ichadi (beta-bloker), spirtli ichimlik yo'q. |
| 1–3 | Skaner → «Paratsetamol (import)» → **«Dorilarimga qo'shish»** → **+** ikki marta (kuniga 3) → **«Qo'shish»** | Kunlik paratsetamol 1 500 mg. |
| 3–6 | Skaner → «Tylol Hot» → **«Dorilarimga qo'shish»** (qo'shishdan OLDIN tekshiruv) → **«Tushundim, baribir qo'shish»** → **Dorilarim** | Takroriy modda: ikkala dorida paratsetamol. Hisoblagich **1 500 → 2 000 / 4 000 mg**. Qizil: *psevdoefedrin + gipertoniya* va *psevdoefedrin + beta-bloker (bisoprolol)*. |
| 6–7 | Dorilarim: har ogohlantirishdagi **«Manba: Tylol Hot qisqa mahsulot ma'lumoti, 4.3 va 4.5»** | Har ogohlantirishda manba bo'limi va *Shifokor yoki farmatsevt bilan maslahatlashing*. Mezon **tashxis qo'ymaydi, dori tayinlamaydi, dozani belgilamaydi** — faqat tasdiqlangan qoidalarni ko'rsatadi. |
| 7–8 | Ishonch kartasida komponent ustiga bosish (R, L, M, F, U) | Har ball sababi, manbasi va sanasi bilan. CoA'da ko'rsatkich me'yordan chiqsa (Ibuprofen import, *Erish tezligi*) — L tushadi. |
| 8–9 | Terminal (lokal): `python -c "from app import pii; print(pii.mask('Bemor Karimova Aziza, tel +998 90 123-45-67, JShShIR 31203987654321, Tylol Hot ichdim'))"` | AI'ga yuborishdan oldin FISh, telefon, JShShIR maskalanadi: `[FISh]`, `[TELEFON]`, `[JShShIR]`. |
| 9–10 | Skaner → **«Omeprazol — klon kod»** (shahar: Toshkent) | *Klon kod: bu seriya boshqa shaharda ham skanerlangan* — avval Samarqandda. Markirovka komponenti M 100 → 40. |

---

## Agar nimadir ishlamasa

| Muammo | Yechim |
|---|---|
| Kamera kodni o'qimayapti | Kodni 10–15 sm da, ramka ichida ushlang; qorong'i bo'lsa **«Chiroq»**. Bo'lmasa — qutini suratga olib **«Rasmdan o'qish»** (server zxing-cpp bilan o'qiydi). |
| Kamera ishlamaydi / ruxsat yo'q / HTTPS emas | Skaner sahifasidagi **demo kod chiplari**, «Kodni qo'lda kiritish» yoki «Rasmdan o'qish». Demo kodlarni ikkinchi ekranda ko'rsatish: Profil → «Demo kodlar». |
| AI sekin yoki xato (503/429/timeout) | 20 s dan keyin zaxira model, so'ng **tayyor natija** avtomatik chiqadi (sababi bilan). Oddiy tugma keshdan darhol javob beradi. |
| Internet yo'q (lokal) | Ilova to'liq ishlaydi: vendored kutubxonalar + kesh + tayyor natijalar. |
| Holat aralashib ketdi | Konsol → **«Demoni qayta boshlash»**; bemor oynasida bosh sahifani yangilang. |
| Lokal server javob bermaydi | `run.bat` / `run.sh` ni qayta ishga tushiring. Bazani qaytadan yaratish: `python scripts/seed.py`, so'ng `python scripts/warm_cache.py`. |

Ekran rasmlari (yorug' va qorong'i mavzu): [`screenshots/`](screenshots/).
