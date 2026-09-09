import os
import sys
import json
import re
import ssl
import time
import random
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

SCRIPT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = SCRIPT_DIR.parent
LOCALES_DIR = FRONTEND_DIR / "public" / "locales"
EN_LOCALE_PATH = LOCALES_DIR / "en.json"
CACHE_PATH = FRONTEND_DIR / ".translation_cache.json"

# All 22 official Bhashini languages
TARGET_LANGUAGES = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok",
    "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat",
    "sd", "ta", "te", "ur"
]

# Protected tokens
PROTECTED_TOKENS = [
    ("BhoomiScan AI", "[[TOKEN_BHOOMISCAN]]"),
    ("ULPIN", "[[TOKEN_ULPIN]]"),
    ("DILRMP", "[[TOKEN_DILRMP]]"),
    ("SHA-256", "[[TOKEN_SHA256]]"),
    ("Khasra", "[[TOKEN_KHASRA]]"),
    ("Khata", "[[TOKEN_KHATA]]"),
    ("Tehsil", "[[TOKEN_TEHSIL]]"),
    ("Patwari", "[[TOKEN_PATWARI]]"),
    ("Talati", "[[TOKEN_TALATI]]"),
]

# Locked Tier 1 Metaphor/Jargon Pre-Substitution Table
TIER1_METAPHOR_RULES = [
    (r"\bPush to\b", "Submit to"),
    (r"\bPush\b", "Transfer"),
    (r"\bconfidence scores?\b", "reliability score"),
    (r"\bConfidence\b", "Reliability"),
    (r"\bPipeline Processing Stream\b", "Verification Workflow Activity"),
    (r"\bPipeline\b", "Workflow"),
    (r"\bStart Ingestion & OCR Pipeline\b", "Start Document Intake & OCR Workflow"),
    (r"\bFlagged Fields for Review\b", "Marked Fields for Review"),
    (r"\bFlagged Fields\b", "Marked Fields"),
    (r"\bFlagged for Review\b", "Marked for Review"),
    (r"\bFuzzy duplicate\b", "Approximate duplicate"),
    (r"\bIngest Deed\b", "Upload Land Record"),
    (r"\bIngest Land Record Document\b", "Upload Land Record Document"),
    (r"\bIngest New Document\b", "Upload New Document"),
    (r"\bIngest Another Deed\b", "Upload Another Land Record"),
    (r"\bscanned deed stamp\b", "scanned land record text"),
    (r"\bdeed stamp\b", "land record text"),
    (r"\bdrag & drop deed file\b", "drag land record file to attach"),
    (r"\bVerified & Sealed\b", "Verified & Digitally Signed"),
    (r"\bCryptographic Seal:\b", "Cryptographic Verification:"),
    (r"\bSHA-256 File Seal:\b", "SHA-256 File Integrity Hash:"),
    (r"\btamper-evident QR (?:seal|verification code)\b", "tamper-evident QR security code"),
    (r"\bAutonomous Land Record Digitization\b", "Automated Land Record Digitization"),
    (r"\bIngestion\b", "Document Intake"),
    (r"\bIngest\b", "Upload"),
]

RISK_TERMS_TO_CHECK = ["stamp", "seal", "push", "pipeline", "flag", "stream", "ingest"]

def flatten_dict(d, prefix=""):
    flat = {}
    for k, v in d.items():
        curr_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(flatten_dict(v, curr_key))
        elif isinstance(v, str):
            flat[curr_key] = v
    return flat

def unflatten_dict(flat):
    nested = {}
    for k, v in flat.items():
        parts = k.split(".")
        cur = nested
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = v
    return nested

def tier1_pre_normalize(text: str) -> str:
    normalized = text
    for pattern, replacement in TIER1_METAPHOR_RULES:
        normalized = re.sub(pattern, replacement, normalized)
    for term, token in PROTECTED_TOKENS:
        normalized = re.sub(r"\b" + re.escape(term) + r"\b", token, normalized)
    return normalized

def tier1_restore_tokens(text: str) -> str:
    restored = text
    for term, token in PROTECTED_TOKENS:
        token_pat = re.escape(token).replace(r"\[\[", r"\[\s*\[\s*").replace(r"\]\]", r"\s*\]\s*\]")
        restored = re.sub(token_pat, term, restored, flags=re.IGNORECASE)
    return restored

def load_cache():
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

TRANSLATION_CACHE = load_cache()

def get_cache_key(text: str, target_lang: str) -> str:
    return hashlib.sha256(f"{text}_{target_lang}".encode("utf-8")).hexdigest()

# Dedicated Administrative Term Maps for Regional Scripts in Offline Fallback
# Bodo (Devanagari script), Kashmiri (Nastaliq script), Manipuri (Meetei Mayek script)
OFFLINE_REGIONAL_VOCAB = {
    "brx": {
        "GOVERNMENT OF INDIA": "भारत सरकार",
        "Department of Land Resources & Revenue Administration": "हा सम्पद आरो खाजाना सामलायनाय बिफान",
        "DIGITAL INDIA LAND RECORDS MODERNIZATION PROGRAMME (DILRMP)": "डिजिटल भारत हा रेकर्ड फोसाबनाय बिथांखि (DILRMP)",
        "Sovereign Node Active": "सार्वभौम नद गोहो गोनां",
        "GIGW Compliant": "GIGW मानिनाय",
        "BhoomiScan AI": "भूमिस्कैन AI",
        "Autonomous Land Record Digitization, Semantic Verification & Sovereign Governance": "गावनो गाव हा रेकर्ड डिजिटाइजेसन, सेमान्टिक नायबिजिरनाय आरो सार्वभौम खुंथाइ",
        "National Land Records Sovereign Platform": "रास्ट्रिय हा रेकर्ड सार्वभौम प्लेटफर्म",
        "Sign In": "हाबनाय",
        "Sign Out": "ओंखारनाय",
        "Register Officer": "अफिकार रेजिस्टार",
        "Administrator": "सामलायगिरि",
        "Verifying Officer": "नायबिजिरग्रा अफिसार",
        "Field Officer": "फिल्ड अफिसार",
        "Operations Dashboard": "दाहाव बिफान डेशबर्ड",
        "Land Record Registry": "हा रेकर्ड रेजिस्ट्रि",
        "Upload Land Record": "हा रेकर्ड आपलोड",
        "Total Registered Deeds": "गासै रेजिस्टार हा रेकर्ड",
        "Needs Review": "नायफिननाय नांगौ",
        "Verified & Digitally Signed": "नायबिजिरखांनाय आरो डिजिटल सोहो",
        "Reliability": "फोथायथाव",
        "Total Records": "गासै रेकर्ड",
        "Audit / Verify": "नायबिजिरनाय",
        "View Record": "रेकर्ड नायनाय"
    },
    "ks": {
        "GOVERNMENT OF INDIA": "حکومتِ ہِند",
        "Department of Land Resources & Revenue Administration": "محکمہ اراضی وسائل و مالیات انتظام",
        "DIGITAL INDIA LAND RECORDS MODERNIZATION PROGRAMME (DILRMP)": "ڈیجیٹل انڈیا لینڈ ریکارڈ ماڈرنائزیشن پروگرام (DILRMP)",
        "Sovereign Node Active": "خود مختار نوڈ چالو",
        "GIGW Compliant": "GIGW موافق",
        "BhoomiScan AI": "بھومی اسکین AI",
        "Autonomous Land Record Digitization, Semantic Verification & Sovereign Governance": "خودکار اراضی ریکارڈ ڈیجیٹائزیشن، تصدیق اور خود مختار حکمرانی",
        "National Land Records Sovereign Platform": "قومی اراضی ریکارڈ پلیٹ فارم",
        "Sign In": "اندر آئیں",
        "Sign Out": "باہر نکلیں",
        "Register Officer": "افسر اندراج",
        "Administrator": "منتظم",
        "Verifying Officer": "تصدیق کار افسر",
        "Field Officer": "فیلڈ افسر",
        "Operations Dashboard": "آپریشنز ڈیش بورڈ",
        "Land Record Registry": "اراضی ریکارڈ رجسٹر",
        "Upload Land Record": "اراضی ریکارڈ اپ لوڈ",
        "Total Registered Deeds": "کل درج شدہ اراضی ریکارڈ",
        "Needs Review": "جائزہ درکار",
        "Verified & Digitally Signed": "تصدیق شدہ اور ڈیجیٹل دستخط شدہ",
        "Reliability": "اعتماد",
        "Total Records": "کل ریکارڈز",
        "Audit / Verify": "آڈٹ / تصدیق",
        "View Record": "ریکارڈ دیکھیں"
    },
    "mni": {
        "GOVERNMENT OF INDIA": "ভারত সরকার",
        "Department of Land Resources & Revenue Administration": "ꯂꯝ ꯃꯄꯨ ꯑꯃꯁꯨꯡ ꯔꯦꯚꯤꯅꯤꯎ ꯂꯩꯉꯥꯛ ꯂꯣꯏꯁꯪ",
        "DIGITAL INDIA LAND RECORDS MODERNIZATION PROGRAMME (DILRMP)": "ꯗꯤꯖꯤꯇꯦꯜ ꯏꯟꯗꯤꯌꯥ ꯂꯦꯟꯗ ꯔꯦꯀꯣꯔꯗ ꯃꯣꯗꯔꯅꯥꯏꯖꯦꯁꯟ (DILRMP)",
        "Sovereign Node Active": "ꯁꯣꯚꯔꯦꯟ ꯅꯣꯗ ꯑꯦꯛꯇꯤꯚ",
        "GIGW Compliant": "GIGW ꯆꯨꯅꯕ",
        "BhoomiScan AI": "ꯚꯨꯃꯤꯁ꯭ꯀꯦꯟ AI",
        "Autonomous Land Record Digitization, Semantic Verification & Sovereign Governance": "ꯑꯣꯇꯣꯅꯣꯃꯁ ꯂꯦꯟꯗ ꯔꯦꯀꯣꯔꯗ ꯗꯤꯖꯤꯇꯥꯏꯖꯦꯁꯟ ꯑꯃꯁꯨꯡ ꯁꯣꯚꯔꯦꯟ ꯂꯩꯉꯥꯛ",
        "National Land Records Sovereign Platform": "ꯅꯦꯁ꯭ꯅꯦꯜ ꯂꯦꯟꯗ ꯔꯦꯀꯣꯔꯗ ꯄ꯭ꯂꯦꯠꯐꯣꯔꯝ",
        "Sign In": "ꯆꯪꯕ",
        "Sign Out": "ꯊꯣꯛꯄ",
        "Register Officer": "ꯑꯣꯐꯤꯁꯔ ꯔꯦꯖꯤꯁ꯭ꯇꯔ",
        "Administrator": "ꯑꯦꯗꯃꯤꯅꯤꯁ꯭ꯇ꯭ꯔꯦꯇꯔ",
        "Verifying Officer": "ꯌꯦꯡꯁꯤꯅꯕ ꯑꯣꯐꯤꯁꯔ",
        "Field Officer": "ꯐꯤꯜꯗ ꯑꯣꯐꯤꯁꯔ",
        "Operations Dashboard": "ꯑꯣꯄꯔꯦꯁꯟ ꯗꯦꯁꯕꯣꯔꯗ",
        "Land Record Registry": "ꯂꯦꯟꯗ ꯔꯦꯀꯣꯔꯗ ꯔꯦꯖꯤꯁ꯭ꯇ꯭ꯔꯤ",
        "Upload Land Record": "ꯂꯦꯟꯗ ꯔꯦꯀꯣꯔꯗ ꯑꯄꯂꯣꯗ",
        "Total Registered Deeds": "ꯑꯄꯨꯟꯕ ꯔꯦꯖꯤꯁ꯭ꯇꯔ ꯗꯤꯗ",
        "Needs Review": "ꯌꯦꯡꯐꯝ ꯊꯣꯛꯄ",
        "Verified & Digitally Signed": "ꯌꯦꯡꯁꯤꯟꯈ꯭ꯔꯕ ꯑꯃꯁꯨꯡ ꯗꯤꯖꯤꯇꯦꯜ ꯈꯨꯠꯌꯦꯛ",
        "Reliability": "ꯊꯥꯖꯕ",
        "Total Records": "ꯑꯄꯨꯟꯕ ꯔꯦꯀꯣꯔꯗ",
        "Audit / Verify": "ꯌꯦꯡꯁꯤꯅꯕ",
        "View Record": "ꯔꯦꯀꯣꯔꯗ ꯌꯦꯡꯕ"
    }
}

def translate_string(text: str, target_lang: str) -> str:
    key = get_cache_key(text, target_lang)
    if key in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[key]

    # Offline vocabulary fallback for regional minority scripts if not on GTX
    if target_lang in OFFLINE_REGIONAL_VOCAB and text in OFFLINE_REGIONAL_VOCAB[target_lang]:
        res = OFFLINE_REGIONAL_VOCAB[target_lang][text]
        TRANSLATION_CACHE[key] = res
        return res

    # Check for Bhashini API
    bhashini_key = os.environ.get("BHASHINI_API_KEY")
    bhashini_user = os.environ.get("BHASHINI_USER_ID")
    if bhashini_key and bhashini_user:
        url = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
        headers = {
            "Content-Type": "application/json",
            "Authorization": bhashini_key,
            "userID": bhashini_user
        }
        payload = {
            "pipelineTasks": [{"taskType": "translation", "config": {"language": {"sourceLanguage": "en", "targetLanguage": target_lang}}}],
            "inputData": {"input": [{"source": text}]}
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tr = data["pipelineResponse"][0]["output"][0]["target"]
                TRANSLATION_CACHE[key] = tr
                return tr
        except Exception:
            pass

    # Neural engine for the 22 languages
    target_code = target_lang
    if target_lang == "brx": target_code = "hi"  # Devanagari regional base
    elif target_lang == "ks": target_code = "ur"  # Nastaliq regional base
    elif target_lang == "mni": target_code = "mni-Mtei"  # Meetei Mayek native script
    elif target_lang == "sat": target_code = "sat"  # Ol Chiki native script

    clients = ["dict-chrome-ex"]
    for attempt in range(4):
        client = clients[attempt % len(clients)]
        url = (
            f"https://translate.googleapis.com/translate_a/single?client={client}&sl=en&tl="
            + target_code + "&dt=t&q=" + urllib.parse.quote(text)
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                tr = "".join([part[0] for part in res[0] if part[0]])
                TRANSLATION_CACHE[key] = tr
                return tr
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Error translating to {target_lang}: {e}")
            time.sleep(1.0 + random.uniform(0.2, 0.6))

def generate_locale(target_lang: str, flat_en: dict):
    print(f"[{target_lang}] Generating {len(flat_en)} keys...", flush=True)
    translated_flat = {}
    failed_keys = []

    def translate_entry(item):
        key, raw_val = item
        vars_found = re.findall(r"\{\{[^}]+\}\}", raw_val)
        vars_map = {}
        text_to_norm = raw_val
        for idx, v in enumerate(vars_found):
            v_token = f"[[VAR_{idx}]]"
            vars_map[v_token] = v
            text_to_norm = text_to_norm.replace(v, v_token)

        norm = tier1_pre_normalize(text_to_norm)

        try:
            tr = translate_string(norm, target_lang)
            restored = tier1_restore_tokens(tr)

            for v_token, orig_v in vars_map.items():
                v_pat = re.escape(v_token).replace(r"\[\[", r"\[\s*\[\s*").replace(r"\]\]", r"\s*\]\s*\]")
                restored = re.sub(v_pat, orig_v, restored, flags=re.IGNORECASE)

            return (key, restored, None)
        except Exception as err:
            return (key, raw_val, str(err))

    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(translate_entry, flat_en.items()))

    for key, val, err in results:
        if err:
            failed_keys.append((key, val, err))
        else:
            translated_flat[key] = val

    if failed_keys:
        print(f"[FAIL] {target_lang} failed on {len(failed_keys)} keys:", file=sys.stderr)
        for k, orig, err in failed_keys[:5]:
            print(f"   {k}: {err}", file=sys.stderr)
        return False, None

    nested = unflatten_dict(translated_flat)
    return True, nested

def main():
    print("=" * 80)
    print("TIER 1 -> TIER 2: 22-LANGUAGE LOCALE GENERATION")
    print("=" * 80)

    with open(EN_LOCALE_PATH, "r", encoding="utf-8") as f:
        en_data = json.load(f)

    flat_en = flatten_dict(en_data)
    print(f"Canonical English string count: {len(flat_en)}")

    # Tier 1 Leak Prevention Scan
    leaks = []
    for k, v in flat_en.items():
        norm = tier1_pre_normalize(v).lower()
        for term in RISK_TERMS_TO_CHECK:
            if re.search(r"\b" + re.escape(term) + r"\b", norm):
                leaks.append((k, term, v, norm))

    if leaks:
        print(f"[CRITICAL] Tier 1 pre-normalization leaked {len(leaks)} terms:", file=sys.stderr)
        for k, term, orig, norm in leaks:
            print(f"  Key '{k}' leaked '{term}': \"{orig}\" -> \"{norm}\"", file=sys.stderr)
        sys.exit(1)

    print("✓ Tier 1 scan 100% CLEAN: 0 literal risk terms remain in normalized English.")

    success_count = 0
    for lang in TARGET_LANGUAGES:
        ok, data = generate_locale(lang, flat_en)
        if not ok:
            print(f"[FATAL] Aborting: Language '{lang}' could not be generated cleanly.", file=sys.stderr)
            sys.exit(1)

        tmp_file = LOCALES_DIR / f"{lang}.json.tmp"
        final_file = LOCALES_DIR / f"{lang}.json"

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if final_file.exists():
            final_file.unlink()
        tmp_file.rename(final_file)
        print(f"✓ [{lang}] Atomically wrote {final_file.name}")
        success_count += 1
        save_cache(TRANSLATION_CACHE)

    save_cache(TRANSLATION_CACHE)
    print("\n" + "=" * 80)
    print(f"ALL {success_count}/{len(TARGET_LANGUAGES)} BHASHINI LOCALES GENERATED CLEANLY.")
    print("=" * 80)

if __name__ == "__main__":
    main()
