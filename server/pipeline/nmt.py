import os
import time
import logging
from typing import Tuple, Optional
from dotenv import load_dotenv

logger = logging.getLogger("NMTEngine")
logger.setLevel(logging.INFO)

load_dotenv()

# Custom Glossary: force preferred translations for domain/business/technical terms.
# Applied to the LLM prompt so strategic/technical terms stay consistent.
# Extend these dictionaries to add more terms (English <-> Indonesian).
GLOSSARY = {
    "en->id": {
        # Business & Meetings
        "agenda": "agenda",
        "meeting": "rapat",
        "roadmap": "peta jalan",
        "launching": "meluncurkan",
        "launch": "meluncurkan",
        "production": "produksi",
        "quarterly": "kuartalan",
        "annual": "tahunan",
        "monthly": "bulanan",
        "weekly": "mingguan",
        "internal": "internal",
        "boundaries": "batas",
        "restart": "restart",
        "deadline": "tenggat waktu",
        "timeline": "jadwal waktu",
        "milestone": "tonggak pencapaian",
        "stakeholder": "pemangku kepentingan",
        "objective": "tujuan",
        "goal": "sasaran",
        "target": "target",
        "budget": "anggaran",
        "revenue": "pendapatan",
        "profit": "keuntungan",
        "loss": "kerugian",
        "cost": "biaya",
        "expense": "pengeluaran",
        "investment": "investasi",
        "growth": "pertumbuhan",
        "market": "pasar",
        "customer": "pelanggan",
        "client": "klien",
        "vendor": "pemasok",
        "partner": "mitra",
        "team": "tim",
        "manager": "manajer",
        "department": "departemen",
        "division": "divisi",
        "project": "proyek",
        "schedule": "jadwal",
        "report": "laporan",
        "presentation": "presentasi",
        "strategy": "strategi",
        "plan": "rencana",
        "process": "proses",
        "procedure": "prosedur",
        "policy": "kebijakan",
        "decision": "keputusan",
        "feedback": "masukan",
        "approval": "persetujuan",
        "proposal": "usulan",
        "survey": "survei",
        "analysis": "analisis",
        "forecast": "perkiraan",
        "performance": "kinerja",
        "productivity": "produktivitas",
        "efficiency": "efisiensi",
        "effective": "efektif",
        "progress": "kemajuan",
        "update": "pembaruan",
        "summary": "ringkasan",
        "summary": "rangkuman",
        "deliverable": "luaran",
        "issue": "masalah",
        "concern": "kekhawatiran",
        "risk": "risiko",
        "opportunity": "peluang",
        "competitor": "pesaing",
        "sales": "penjualan",
        "marketing": "pemasaran",
        "brand": "merek",
        "resource": "sumber daya",
        "workforce": "tenaga kerja",
        "headcount": "jumlah karyawan",
        "turnover": "pergantian",
        "hiring": "perekrutan",
        "salary": "gaji",
        "benefit": "tunjangan",
        "contract": "kontrak",
        "agreement": "perjanjian",
        "legal": "hukum",
        "compliance": "kepatuhan",
        "regulation": "peraturan",
        "license": "lisensi",
        "merger": "penggabungan",
        "acquisition": "akuisisi",
        "rollout": "peluncuran",
        "onboarding": "pengenalan",
        "training": "pelatihan",
        "workshop": "lokakarya",
        "conference": "konferensi",
        "subsidiary": "anak perusahaan",
        "headquarters": "kantor pusat",
        "expansion": "ekspansi",
        "retirement": "pensiun",
        "promotion": "promosi",
        "career": "karier",
        # Product & Technology
        "feature": "fitur",
        "functionality": "fungsionalitas",
        "requirement": "kebutuhan",
        "specification": "spesifikasi",
        "implementation": "implementasi",
        "integration": "integrasi",
        "development": "pengembangan",
        "deployment": "penyebaran",
        "release": "rilis",
        "version": "versi",
        "upgrade": "peningkatan",
        "migration": "migrasi",
        "database": "basis data",
        "server": "server",
        "network": "jaringan",
        "software": "perangkat lunak",
        "hardware": "perangkat keras",
        "application": "aplikasi",
        "platform": "platform",
        "interface": "antarmuka",
        "user interface": "antarmuka pengguna",
        "backend": "backend",
        "frontend": "frontend",
        "cloud": "awan",
        "security": "keamanan",
        "encryption": "enkripsi",
        "authentication": "otentikasi",
        "authorization": "otorisasi",
        "password": "kata sandi",
        "account": "akun",
        "data": "data",
        "information": "informasi",
        "system": "sistem",
        "module": "modul",
        "component": "komponen",
        "code": "kode",
        "testing": "pengujian",
        "debugging": "penelusuran kesalahan",
        "error": "kesalahan",
        "bug": "kerusakan",
        "configuration": "konfigurasi",
        "setup": "pengaturan",
        "installation": "pemasangan",
        "performance": "kinerja",
        "optimization": "optimasi",
        "scalability": "skalabilitas",
        "availability": "ketersediaan",
        "reliability": "keandalan",
        "backup": "cadangan",
        "restore": "pemulihan",
        "archive": "arsip",
        "upload": "unggah",
        "download": "unduh",
        "notification": "notifikasi",
        "automation": "otomatisasi",
        "artificial intelligence": "kecerdasan buatan",
        "machine learning": "pembelajaran mesin",
        "deep learning": "pembelajaran mendalam",
        "model": "model",
        "algorithm": "algoritma",
        "training data": "data pelatihan",
        "inference": "inferensi",
        "transcription": "transkripsi",
        "translation": "terjemahan",
        "speech": "ucapan",
        "voice": "suara",
        "audio": "audio",
        "real-time": "waktu nyata",
        "streaming": "streaming",
        "latency": "latensi",
        "bandwidth": "lebar pita",
        "browser": "peramban",
        "extension": "ekstensi",
        "plugin": "plugin",
        "token": "token",
        "key": "kunci",
        "subscription": "langganan",
        "license": "lisensi",
        "trial": "uji coba",
        "premium": "premium",
        "free": "gratis",
        # Office & Admin
        "email": "surel",
        "attachment": "lampiran",
        "folder": "folder",
        "file": "berkas",
        "document": "dokumen",
        "spreadsheet": "lembar kerja",
        "slide": "slaid",
        "printer": "pencetak",
        "invoice": "faktur",
        "receipt": "tanda terima",
        "purchase": "pembelian",
        "order": "pesanan",
        "inventory": "persediaan",
        "shipping": "pengiriman",
        "delivery": "pengiriman",
        "payment": "pembayaran",
        "refund": "pengembalian dana",
        "discount": "diskon",
        "price": "harga",
        "currency": "mata uang",
        "quantity": "jumlah",
        "quality": "kualitas",
        "quantity control": "pengendalian mutu",
        "complaint": "keluhan",
        "warranty": "garansi",
        "support": "dukungan",
        "maintenance": "perawatan",
        "repair": "perbaikan",
        "insurance": "asuransi",
        "tax": "pajak",
        "audit": "audit",
        "asset": "aset",
        "liability": "kewajiban",
        "capital": "modal",
        "dividend": "dividen",
        "shareholder": "pemegang saham",
        "interest": "bunga",
        "loan": "pinjaman",
        "debt": "utang",
        "credit": "kredit",
    },
    "id->en": {
        "peta jalan": "roadmap",
        "meluncurkan": "launch",
        "peluncuran": "launch",
        "kuartalan": "quarterly",
        "tahunan": "annual",
        "bulanan": "monthly",
        "mingguan": "weekly",
        "rapat": "meeting",
        "tenggat waktu": "deadline",
        "pemangku kepentingan": "stakeholder",
        "tujuan": "objective",
        "sasaran": "goal",
        "pendapatan": "revenue",
        "keuntungan": "profit",
        "kerugian": "loss",
        "biaya": "cost",
        "pengeluaran": "expense",
        "investasi": "investment",
        "pertumbuhan": "growth",
        "pasar": "market",
        "pelanggan": "customer",
        "klien": "client",
        "mitra": "partner",
        "manajer": "manager",
        "departemen": "department",
        "divisi": "division",
        "proyek": "project",
        "jadwal": "schedule",
        "laporan": "report",
        "presentasi": "presentation",
        "strategi": "strategy",
        "rencana": "plan",
        "proses": "process",
        "prosedur": "procedure",
        "kebijakan": "policy",
        "keputusan": "decision",
        "masukan": "feedback",
        "persetujuan": "approval",
        "usulan": "proposal",
        "analisis": "analysis",
        "perkiraan": "forecast",
        "kinerja": "performance",
        "produktivitas": "productivity",
        "efisiensi": "efficiency",
        "efektif": "effective",
        "kemajuan": "progress",
        "pembaruan": "update",
        "ringkasan": "summary",
        "masalah": "issue",
        "risiko": "risk",
        "peluang": "opportunity",
        "pesaing": "competitor",
        "penjualan": "sales",
        "pemasaran": "marketing",
        "merek": "brand",
        "sumber daya": "resource",
        "perekrutan": "hiring",
        "gaji": "salary",
        "tunjangan": "benefit",
        "kontrak": "contract",
        "perjanjian": "agreement",
        "kepatuhan": "compliance",
        "peraturan": "regulation",
        "lisensi": "license",
        "penggabungan": "merger",
        "akuisisi": "acquisition",
        "pengenalan": "onboarding",
        "pelatihan": "training",
        "lokakarya": "workshop",
        "konferensi": "conference",
        "anak perusahaan": "subsidiary",
        "kantor pusat": "headquarters",
        "ekspansi": "expansion",
        "promosi": "promotion",
        "karier": "career",
        "fitur": "feature",
        "kebutuhan": "requirement",
        "spesifikasi": "specification",
        "implementasi": "implementation",
        "integrasi": "integration",
        "pengembangan": "development",
        "penyebaran": "deployment",
        "versi": "version",
        "peningkatan": "upgrade",
        "migrasi": "migration",
        "basis data": "database",
        "jaringan": "network",
        "perangkat lunak": "software",
        "perangkat keras": "hardware",
        "aplikasi": "application",
        "antarmuka": "interface",
        "awan": "cloud",
        "keamanan": "security",
        "enkripsi": "encryption",
        "otentikasi": "authentication",
        "kata sandi": "password",
        "akun": "account",
        "sistem": "system",
        "komponen": "component",
        "pengujian": "testing",
        "kesalahan": "error",
        "konfigurasi": "configuration",
        "pengaturan": "setup",
        "pemasangan": "installation",
        "optimasi": "optimization",
        "skalabilitas": "scalability",
        "ketersediaan": "availability",
        "keandalan": "reliability",
        "cadangan": "backup",
        "pemulihan": "restore",
        "unggah": "upload",
        "unduh": "download",
        "notifikasi": "notification",
        "otomatisasi": "automation",
        "kecerdasan buatan": "artificial intelligence",
        "pembelajaran mesin": "machine learning",
        "transkripsi": "transcription",
        "terjemahan": "translation",
        "ucapan": "speech",
        "suara": "voice",
        "waktu nyata": "real-time",
        "latensi": "latency",
        "lebar pita": "bandwidth",
        "peramban": "browser",
        "ekstensi": "extension",
        "langganan": "subscription",
        "uji coba": "trial",
        "surel": "email",
        "lampiran": "attachment",
        "berkas": "file",
        "dokumen": "document",
        "faktur": "invoice",
        "pembelian": "purchase",
        "pesanan": "order",
        "pengiriman": "shipping",
        "pembayaran": "payment",
        "pengembalian dana": "refund",
        "diskon": "discount",
        "harga": "price",
        "kualitas": "quality",
        "keluhan": "complaint",
        "garansi": "warranty",
        "dukungan": "support",
        "perawatan": "maintenance",
        "perbaikan": "repair",
        "asuransi": "insurance",
        "pajak": "tax",
        "audit": "audit",
        "aset": "asset",
        "kewajiban": "liability",
        "modal": "capital",
        "pemegang saham": "shareholder",
        "pinjaman": "loan",
        "utang": "debt",
        "kredit": "credit",
        "restart": "restart",
    }
}

def _glossary_hint(src: str, tgt: str, text: str = "") -> str:
    """Build a glossary instruction string for the LLM prompt.

    Only terms actually present in the source text (case-insensitive) are
    included, keeping the prompt short so the LLM reliably follows it.
    """
    def _code(name: str) -> str:
        return "en" if name.lower().startswith("en") else "id"
    key = f"{_code(src)}->{_code(tgt)}"
    terms = GLOSSARY.get(key)
    if not terms:
        return ""
    lowered = text.lower()
    matched = {s: t for s, t in terms.items() if s.lower() in lowered}
    if not matched:
        return ""
    hints = "; ".join(f'"{s}" -> "{t}"' for s, t in matched.items())
    return (f"Use these exact preferred translations when the terms appear "
            f"(do not rephrase them): {hints}.\n")


def _apply_glossary(text: str, tgt: str) -> str:
    """Deterministic post-processing: replace glossary terms in the output.

    Works on the TARGET-language side of the dictionary. E.g. for en->id output
    (Indonesian), replace any English source terms with their Indonesian form so
    the LLM's preferred wording is guaranteed.
    """
    if not text:
        return text
    import re as _re
    # For Indonesian output, apply the en->id mappings; for English, id->en.
    # NOTE: match on the leading "en" (English) — "Indonesian" does NOT start
    # with "id", so startswith("id") would wrongly pick the id->en direction.
    if tgt.lower().startswith("en"):
        key = "id->en"
    else:
        key = "en->id"
    terms = GLOSSARY.get(key, {})
    result = text
    for src_term, dst_term in terms.items():
        result = _re.sub(_re.escape(src_term), dst_term, result, flags=_re.IGNORECASE)
    return result

class GeminiTranslator:
    """
    Hybrid Neural Machine Translation Engine:
    - Primary: Groq LLM (llama-3.3-70b-versatile) for ultra-fast (~100ms) & natural meeting translation.
    - Secondary: Gemini AI API (gemini-2.0-flash).
    - Fallback: Google Translate Web API.
    """
    def __init__(self):
        self.api_key = None
        self.client = None
        self.is_loaded = False
        self._init_client()

    def _init_client(self):
        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key and self.api_key != "your_api_key_here":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                self.is_loaded = True
                logger.info("GeminiTranslator initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None
                self.is_loaded = False
        else:
            logger.info("GEMINI_API_KEY not set. Will use Groq LLM or Web Fallback.")
            self.client = None
            self.is_loaded = False

    def _translate_groq(self, text: str, src_full: str, tgt_full: str, custom_groq_key: Optional[str] = None) -> Optional[str]:
        api_key = custom_groq_key or os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            return None
        try:
            from groq import Groq
            groq_client = Groq(api_key=api_key)
            hint = _glossary_hint(src_full, tgt_full, text)
            prompt = f'{hint}Translate the following spoken text (which may contain code-switched or mixed languages, e.g. Indonesian mixed with English slang) into precise, natural, and fluent {tgt_full}. Output ONLY the translated text, nothing else.\n\nText: "{text.strip()}"'
            
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"You are a world-class professional interpreter. The input text may be code-switched (mixed languages). Translate the core meaning accurately and fluently into {tgt_full}. Output ONLY the translated text."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                max_tokens=256
            )

            translated = response.choices[0].message.content.strip()
            if translated.startswith('"') and translated.endswith('"'):
                translated = translated[1:-1]
            return translated
        except Exception as e:
            logger.warning(f"Groq LLM NMT error: {e}")
            return None

    def _fallback_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        try:
            import urllib.parse
            import urllib.request
            import json
            
            sl = "en" if source_lang.lower().startswith("en") else "id"
            tl = "id" if target_lang.lower().startswith("id") else "en"
            
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={urllib.parse.quote(text)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                translated = "".join([part[0] for part in data[0] if part[0]])
                return translated.strip()
        except Exception as e:
            logger.error(f"Fallback translation error: {e}")
            return text

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "id", custom_groq_key: Optional[str] = None, custom_gemini_key: Optional[str] = None) -> Tuple[str, float]:
        """
        Translates text from source_lang to target_lang using Groq LLM, Gemini AI, or Web Fallback.
        """
        start_time = time.time()
        if not text or not text.strip():
            return text, 0.0

        src_full = "English" if source_lang.lower().startswith("en") else "Indonesian"
        tgt_full = "Indonesian" if target_lang.lower().startswith("id") else "English"

        # 1. Try Groq LLM NMT first (~100ms ultra-fast translation)
        groq_translated = self._translate_groq(text, src_full, tgt_full, custom_groq_key=custom_groq_key)
        if groq_translated:
            groq_translated = _apply_glossary(groq_translated, tgt_full)
            latency = time.time() - start_time
            logger.info(f"Groq LLM NMT Completed in {latency*1000:.1f}ms")
            return groq_translated, latency

        # 2. Try Gemini AI if available
        gemini_key = custom_gemini_key or os.getenv("GEMINI_API_KEY")
        if gemini_key and gemini_key != "your_api_key_here":
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=gemini_key)
                hint = _glossary_hint(src_full, tgt_full, text)
                prompt = f'{hint}Translate the following spoken {src_full} text into natural, conversational {tgt_full}. Only output the translated text, nothing else. Text: "{text.strip()}"'
                for model_name in ['gemini-2.0-flash', 'gemini-1.5-flash-latest']:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(temperature=0.3)
                        )
                        translated_text = response.text.strip()
                        if translated_text.startswith('"') and translated_text.endswith('"'):
                            translated_text = translated_text[1:-1]
                        translated_text = _apply_glossary(translated_text, tgt_full)
                        latency = time.time() - start_time
                        return translated_text, latency
                    except Exception as e:
                        logger.warning(f"Gemini model {model_name} error: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Gemini translation init error: {e}")

        # 3. Fallback to Web Translate
        logger.info("Using fast fallback translation engine...")
        fallback_res = self._fallback_translate(text, source_lang, target_lang)
        return fallback_res, time.time() - start_time


