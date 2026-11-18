"""Builds data/precomputed_llm.json — the offline fallback for every LLM task.

The demo never depends on the network: when there is no API key, on timeout, 429 or any error,
llm.py returns these results. Run:  python scripts/build_precomputed.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

EXPLAIN = {
    "dentashan": "Bu dori rasmiy bazada ro'yxatdan o'tgan, lekin uning muvofiqlik hujjati muddati tugagan deb belgilangan. "
                 "Bu dori albatta sifatsiz degani emas, ammo hozir sifatni tasdiqlovchi hujjat amal qilmayapti. "
                 "Sotib olishdan oldin farmatsevtdan hujjat holatini so'rang yoki muvofiqlik hujjati amal qilayotgan muqobilni ko'rib chiqing.",
    "para_imp": "Bu paratsetamol rasmiy bazada ro'yxatdan o'tgan, kodi haqiqiy va partiyaning laboratoriya natijalari me'yorda. "
                "Ishonch indeksi yuqori. Xuddi shu tarkibli mahalliy analog arzonroq bo'lishi mumkin — almashtirishdan oldin farmatsevt bilan maslahatlashing.",
    "para_loc": "Bu mahalliy paratsetamol rasmiy bazada ro'yxatdan o'tgan, laboratoriya natijalari me'yorda va bioekvivalentligi tasdiqlangan. "
                "Tarkibi, miqdori va shakli import paratsetamol bilan bir xil. Qabul qilish tartibi bo'yicha yo'riqnoma va farmatsevt tavsiyasiga amal qiling.",
    "tylol": "Tylol Hot uchta moddani saqlaydi: paratsetamol, psevdoefedrin va xlorfeniramin. "
             "Rasmiy holati va laboratoriya natijalari joyida, lekin psevdoefedrin ba'zi kasalliklar va dorilar bilan mos kelmasligi mumkin. "
             "\"Dorilarimga qo'shish\" orqali o'z dorilaringiz bilan moslikni tekshirib ko'ring.",
    "ibu_imp:coa_out": "Bu ibuprofen rasmiy bazada ro'yxatdan o'tgan va kodi haqiqiy. "
               "Biroq ushbu partiyaning laboratoriya sertifikatida bitta ko'rsatkich (erish tezligi) me'yordan past chiqqan. "
               "Boshqa partiya yoki mos mahalliy analog haqida farmatsevt bilan maslahatlashing.",
    "aml_loc:near_expiry": "Bu amlodipin rasmiy bazada ro'yxatdan o'tgan va kodi haqiqiy. "
               "Ushbu qadoqning yaroqlilik muddati tugashiga oz qoldi. Qadoqdagi muddatni tekshiring, savollar bo'lsa farmatsevtdan so'rang.",
    "ome_imp:clone": "Bu kodning seriya raqami boshqa shaharda ham skanerlangan — bu nusxalangan (klon) kod belgisi bo'lishi mumkin. "
                     "Dori qalbaki ekani aniq emas, ammo ehtiyot bo'lish kerak. Qadoqni farmatsevtga ko'rsating va iloji bo'lsa boshqa dorixonadan oling.",
    "dic_imp:recalled": "Rasmiy ma'lumotga ko'ra, bu partiya muomaladan qaytarib olingan. "
                        "Bu partiyadagi dorini ishlatmaslik va dorixonaga qaytarish tavsiya etiladi. "
                        "Xuddi shu dorining boshqa partiyasi yoki mos analogi haqida farmatsevtdan so'rang.",
    "set_imp:expired": "Bu qadoqning yaroqlilik muddati o'tgan. Muddati o'tgan dori kutilgan ta'sirni bermasligi mumkin, shuning uchun uni ishlatmang. "
                       "Yangi qadoq yoki mos analog haqida farmatsevtdan so'rang.",
    "para_loc:unknown": "Bu seriya raqami rasmiy markirovka bazasida topilmadi. "
                        "Kod noto'g'ri o'qilgan yoki qadoq haqiqiy bo'lmasligi mumkin. Kodni qayta skanerlang, natija o'zgarmasa farmatsevtga murojaat qiling.",
}

NORMALIZE_INN = {
    "Metrodonidazol": "metronidazol",
    "metrodonidazol": "metronidazol",
    "hlorgeksedin": "xlorgeksidin",
    "Hlorgeksedin": "xlorgeksidin",
    "Paracetamol": "paratsetamol",
    "Parasetamol": "paratsetamol",
    "Psödoefedrin HCl": "psevdoefedrin",
    "Pseudoephedrine": "psevdoefedrin",
    "Klorfeniramin maleat": "xlorfeniramin",
    "Chlorphenamine": "xlorfeniramin",
}

LEAFLET_RULES = [
    {"kind": "drug_condition", "a": "psevdoefedrin", "b": "buyrak_kasalligi", "threshold_mg": None, "severity": "danger",
     "message_uz": "Og'ir buyrak kasalligi yoki buyrak yetishmovchiligida Tylol Hot qarshi ko'rsatilgan.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.3"},
    {"kind": "drug_condition", "a": "paratsetamol", "b": "jigar_kasalligi", "threshold_mg": None, "severity": "danger",
     "message_uz": "Og'ir jigar yetishmovchiligida (Child-Pugh > 9) paratsetamol saqlovchi Tylol Hot qarshi ko'rsatilgan.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.3"},
    {"kind": "drug_drug", "a": "psevdoefedrin", "b": "class:tricyclic_antidepressant", "threshold_mg": None, "severity": "danger",
     "message_uz": "Psevdoefedrin trisiklik antidepressantlar bilan birga qabul qilinsa, qon bosimi ko'tarilishi mumkin.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.3 va 4.5"},
    {"kind": "drug_drug", "a": "psevdoefedrin", "b": "class:MAOI", "threshold_mg": None, "severity": "danger",
     "message_uz": "MAO ingibitorlarini oxirgi 14 kun ichida qabul qilganlarda psevdoefedrin qarshi ko'rsatilgan.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.3"},
    {"kind": "drug_condition", "a": "psevdoefedrin", "b": "diabet", "threshold_mg": None, "severity": "warn",
     "message_uz": "Diabetda psevdoefedrin saqlovchi dorilar ehtiyotkorlik bilan, shifokor nazoratida qo'llanadi.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.4"},
    {"kind": "drug_condition", "a": "psevdoefedrin", "b": "homiladorlik", "threshold_mg": None, "severity": "warn",
     "message_uz": "Homiladorlikda Tylol Hot faqat shifokor tavsiyasi bilan, foyda va xavf baholangandan keyin qo'llanadi.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.6"},
    {"kind": "drug_drug", "a": "paratsetamol", "b": "varfarin", "threshold_mg": None, "severity": "warn",
     "message_uz": "Varfarin qabul qiladiganlar shifokor nazoratisiz uzoq muddat paratsetamol ichmasligi kerak: INR va qon ketish xavfi oshadi.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.5"},
    {"kind": "max_daily", "a": "paratsetamol", "b": "alcohol", "threshold_mg": 2000, "severity": "danger",
     "message_uz": "Spirtli ichimlik iste'mol qiladiganlarda paratsetamolning kunlik miqdori 2000 mg dan oshmasligi kerak.",
     "source": "Tylol Hot qisqa mahsulot ma'lumoti, 4.2"},
]

REPORT_EXAMPLES = {
    "Ichgandan keyin terimda toshma va qichish paydo bo'ldi": {"category": "allergik reaksiya", "severity": "warn"},
    "Qadoq rangi boshqacha, tabletka hidi g'alati": {"category": "sifat shikoyati", "severity": "warn"},
}


def main():
    coa = json.loads((DATA / "coa_results.json").read_text(encoding="utf-8"))
    extract = {c["batch_no"]: {"batch_no": c["batch_no"], "results": c["results"]} for c in coa["certificates"]}
    out = {
        "_note": "MOCK: precomputed LLM results used when the live model is unavailable (no key, timeout, 429, error).",
        "explain_uz": EXPLAIN,
        "normalize_inn": NORMALIZE_INN,
        "extract_coa": extract,
        "leaflet_to_rules": {"tylol-hot": LEAFLET_RULES},
        "classify_report": REPORT_EXAMPLES,
    }
    (DATA / "precomputed_llm.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("precomputed_llm.json written")


if __name__ == "__main__":
    main()
