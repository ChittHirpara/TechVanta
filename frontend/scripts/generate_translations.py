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

# ── Paths ──
SCRIPT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = SCRIPT_DIR.parent
LOCALES_DIR = FRONTEND_DIR / "public" / "locales"
EN_LOCALE_PATH = LOCALES_DIR / "en.json"
CACHE_PATH = FRONTEND_DIR / ".translation_cache.json"

# ── 22 Official 8th Schedule Bhashini Languages ──
TARGET_LANGUAGES = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok",
    "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat",
    "sd", "ta", "te", "ur"
]

# ── Tier 1: Acronym & Token Protection ──
PROTECTED_TOKENS = [
    ("ULPIN", "[[TOKEN_ULPIN]]"),
    ("DILRMP", "[[TOKEN_DILRMP]]"),
    ("SHA-256", "[[TOKEN_SHA256]]"),
    ("Khasra", "[[TOKEN_KHASRA]]"),
    ("Khata", "[[TOKEN_KHATA]]"),
    ("Tehsil", "[[TOKEN_TEHSIL]]"),
    ("Patwari", "[[TOKEN_PATWARI]]"),
    ("Talati", "[[TOKEN_TALATI]]"),
]

# ── Tier 1: Metaphor & Jargon Pre-Substitution ──
TIER1_METAPHOR_RULES = [
    # Compound & Specific Matches First
    (r"\bPush to\b", "Submit to"),
    (r"\bconfidence scores?\b", "reliability score"),
    (r"\bConfidence\b", "Reliability"),
    (r"\bPipeline Processing Stream\b", "Verification Workflow Activity"),
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
    (r"\btamper-evident QR seal\b", "tamper-evident QR verification code"),
    
    # Standalone Fallbacks
    (r"\bPush\b", "Transfer"),
    (r"\bPipeline\b", "Workflow"),
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
    # 1. Apply metaphor substitutions
    normalized = text
    for pattern, replacement in TIER1_METAPHOR_RULES:
        normalized = re.sub(pattern, replacement, normalized)
        
    # 2. Tokenize acronyms/cadastral terms
    for term, token in PROTECTED_TOKENS:
        normalized = re.sub(r"\b" + re.escape(term) + r"\b", token, normalized)
        
    return normalized

def tier1_restore_tokens(text: str) -> str:
    restored = text
    for term, token in PROTECTED_TOKENS:
        # Match token with optional spaces injected by translation engines
        token_pat = re.escape(token).replace(r"\[\[", r"\[\s*\[\s*").replace(r"\]\]", r"\s*\]\s*\]")
        restored = re.sub(token_pat, term, restored, flags=re.IGNORECASE)
    return restored

# ── Translation Cache ──
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

# ── Tier 2: Translation Engine with Exponential Backoff ──
def translate_via_bhashini_or_neural(text: str, target_lang: str) -> str:
    key = get_cache_key(text, target_lang)
    if key in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[key]
        
    # Check if Bhashini API credentials exist
    bhashini_key = os.environ.get("BHASHINI_API_KEY")
    bhashini_user = os.environ.get("BHASHINI_USER_ID")
    
    if bhashini_key and bhashini_user:
        # Bhashini ULCA API Call
        url = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
        headers = {
            "Content-Type": "application/json",
            "Authorization": bhashini_key,
            "userID": bhashini_user
        }
        payload = {
            "pipelineTasks": [{
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": "en",
                        "targetLanguage": target_lang
                    }
                }
            }],
            "inputData": {
                "input": [{"source": text}]
            }
        }
        backoff = [1.0, 3.0, 7.0]
        for attempt, delay in enumerate(backoff):
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    translated = data["pipelineResponse"][0]["output"][0]["target"]
                    TRANSLATION_CACHE[key] = translated
                    return translated
            except Exception as e:
                if attempt == len(backoff) - 1:
                    break
                jitter = random.uniform(0.1, 0.5)
                time.sleep(delay + jitter)

    # High-fidelity Fallback Translation Engine
    url = (
        "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl="
        + target_lang + "&dt=t&q=" + urllib.parse.quote(text)
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    backoff = [1.0, 3.0, 7.0]
    for attempt, delay in enumerate(backoff):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                translated = "".join([part[0] for part in res[0] if part[0]])
                TRANSLATION_CACHE[key] = translated
                return translated
        except Exception as e:
            if attempt == len(backoff) - 1:
                raise RuntimeError(f"Failed to translate '{text}' to {target_lang} after 3 retries: {e}")
            jitter = random.uniform(0.1, 0.5)
            time.sleep(delay + jitter)

def generate_locale_for_language(target_lang: str, flat_en: dict):
    print(f"[{target_lang}] Translating {len(flat_en)} strings in parallel...", flush=True)
    translated_flat = {}
    failed_keys = []
    
    def process_key(item):
        key, raw_val = item
        vars_found = re.findall(r"\{\{[^}]+\}\}", raw_val)
        normalized = tier1_pre_normalize(raw_val)
        
        try:
            translated = translate_via_bhashini_or_neural(normalized, target_lang)
            restored = tier1_restore_tokens(translated)
            
            for v in vars_found:
                if v not in restored:
                    clean_v_name = v[2:-2].strip()
                    restored = re.sub(r"\{\{\s*" + re.escape(clean_v_name) + r"\s*\}\}", v, restored)
                    
            return (key, restored, None)
        except Exception as err:
            return (key, raw_val, str(err))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(process_key, flat_en.items()))
        
    for key, val, err in results:
        if err:
            failed_keys.append((key, val, err))
        else:
            translated_flat[key] = val
            
    if failed_keys:
        print(f"\n[ERROR] Language '{target_lang}' failed on {len(failed_keys)} keys:", file=sys.stderr)
        for k, orig, err in failed_keys:
            print(f"  - Key: {k} | Error: {err}", file=sys.stderr)
        return False, None
        
    nested = unflatten_dict(translated_flat)
    return True, nested

def main():
    print("=" * 80)
    print("BHASHINI 22-LANGUAGE TRANSLATION GENERATION (TIER 1 -> TIER 2)")
    print("=" * 80)
    
    if not EN_LOCALE_PATH.exists():
        print(f"Error: English source {EN_LOCALE_PATH} does not exist!", file=sys.stderr)
        sys.exit(1)
        
    with open(EN_LOCALE_PATH, "r", encoding="utf-8") as f:
        en_data = json.load(f)
        
    flat_en = flatten_dict(en_data)
    print(f"Total keys in canonical en.json: {len(flat_en)}")
    
    # Pre-validation scan on normalized English
    leaked_risks = {}
    for key, text in flat_en.items():
        norm = tier1_pre_normalize(text)
        lower_norm = norm.lower()
        for rk in RISK_TERMS_TO_CHECK:
            if re.search(r"\b" + re.escape(rk) + r"\b", lower_norm):
                leaked_risks.setdefault(rk, []).append((key, text, norm))
                
    if leaked_risks:
        print("\n[CRITICAL FAILURE] Tier 1 pre-normalization left literal risk terms surviving:", file=sys.stderr)
        for rk, occurrences in leaked_risks.items():
            print(f"  Risk term: '{rk}' ({len(occurrences)} leaks):", file=sys.stderr)
            for k, orig, norm in occurrences:
                print(f"    Key '{k}': \"{orig}\" -> \"{norm}\"", file=sys.stderr)
        sys.exit(1)
    else:
        print("✓ Tier 1 pre-normalization check clean: 0 risk terms remain in normalized English.")
        
    # Generate all 22 languages
    success_count = 0
    failed_languages = []
    
    for lang in TARGET_LANGUAGES:
        ok, nested_data = generate_locale_for_language(lang, flat_en)
        if not ok:
            failed_languages.append(lang)
            continue
            
        # Atomic write (.tmp -> .json)
        tmp_path = LOCALES_DIR / f"{lang}.json.tmp"
        final_path = LOCALES_DIR / f"{lang}.json"
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(nested_data, f, ensure_ascii=False, indent=2)
            
        # Atomic rename
        if final_path.exists():
            final_path.unlink()
        tmp_path.rename(final_path)
        print(f"✓ [{lang}] Successfully generated {final_path.name}")
        success_count += 1
        save_cache(TRANSLATION_CACHE)
        
    save_cache(TRANSLATION_CACHE)
    print("\n" + "=" * 80)
    print(f"GENERATION COMPLETE: {success_count}/{len(TARGET_LANGUAGES)} languages generated successfully.")
    print("=" * 80)
    
    if failed_languages:
        print(f"FAILED LANGUAGES: {failed_languages}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
