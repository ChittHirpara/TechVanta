import json
import sys
import os
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LOCALES_DIR = Path(__file__).resolve().parent.parent / "public" / "locales"
EN_FILE = LOCALES_DIR / "en.json"

TARGET_LANGUAGES = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok",
    "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat",
    "sd", "ta", "te", "ur"
]

LANGUAGE_NAMES = {
    "as": "Assamese (অসমীয়া)",
    "bn": "Bengali (বাংলা)",
    "brx": "Bodo (बड़ो)",
    "doi": "Dogri (डोगरी)",
    "gu": "Gujarati (ગુજરાતી)",
    "hi": "Hindi (हिन्दी)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ks": "Kashmiri (کٲشُر)",
    "kok": "Konkani (कोंकणी)",
    "mai": "Maithili (मैथिली)",
    "ml": "Malayalam (മലയാളം)",
    "mni": "Manipuri (মৈতৈলোন্ / Meetei)",
    "mr": "Marathi (मराठी)",
    "ne": "Nepali (नेपाली)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "sa": "Sanskrit (संस्कृतम्)",
    "sat": "Santali (ᱥᱟᱱᱛᱟᱲᱤ)",
    "sd": "Sindhi (سنڌي)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "ur": "Urdu (اردو)"
}

def flatten_dict(d, prefix=""):
    flat = {}
    for k, v in d.items():
        curr_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(flatten_dict(v, curr_key))
        elif isinstance(v, str):
            flat[curr_key] = v
    return flat

def is_legitimately_identical(key, en_text):
    clean = en_text.strip()
    # Brand name, status flags, and protected tokens / version strings
    if clean in ["BhoomiScan AI", "भूमिस्कैन एआई", "SECURED_VERIFIED", "v1.0.0", "DILRMP 2.0:"]:
        return True
    # Pure numbers or codes
    if re.match(r'^[vV]?[0-9\s:•\-_#%\\/\(\)\.]+$', clean):
        return True
    return False

def audit_completeness():
    with open(EN_FILE, "r", encoding="utf-8") as f:
        en_data = json.load(f)
    flat_en = flatten_dict(en_data)
    total_en_keys = len(flat_en)

    print("=" * 100)
    print("PER-LANGUAGE COMPLETENESS & IDENTICAL-MATCH AUDIT (SCHEDULE VIII LANGUAGES)")
    print("=" * 100)
    print(f"Total Canonical English Keys: {total_en_keys}\n")

    summary_rows = []
    suspicious_details = {}

    for lang in TARGET_LANGUAGES:
        l_file = LOCALES_DIR / f"{lang}.json"
        if not l_file.exists():
            summary_rows.append((lang, LANGUAGE_NAMES.get(lang, lang), 0, 0, 0, 0, "MISSING FILE"))
            continue

        with open(l_file, "r", encoding="utf-8") as f:
            l_data = json.load(f)
        flat_lang = flatten_dict(l_data)

        missing_keys = [k for k in flat_en if k not in flat_lang or not flat_lang[k].strip()]
        
        identical_keys = []
        legit_identical = []
        suspicious_identical = []

        for k, en_val in flat_en.items():
            if k in flat_lang:
                tr_val = flat_lang[k].strip()
                if tr_val == en_val.strip():
                    identical_keys.append(k)
                    if is_legitimately_identical(k, en_val):
                        legit_identical.append(k)
                    else:
                        suspicious_identical.append((k, en_val))

        summary_rows.append((
            lang,
            LANGUAGE_NAMES.get(lang, lang),
            len(flat_lang),
            len(flat_lang) - len(missing_keys),
            len(identical_keys),
            len(legit_identical),
            len(suspicious_identical)
        ))

        if suspicious_identical:
            suspicious_details[lang] = suspicious_identical

    # Print Table
    print(f"{'Code':<6} | {'Language':<30} | {'Total Keys':<10} | {'Translated':<10} | {'Total Identical':<15} | {'Legit Identical':<15} | {'Suspicious':<10}")
    print("-" * 110)
    for code, name, tot, tr, ident, legit, susp in summary_rows:
        print(f"{code:<6} | {name:<30} | {tot:<10} | {tr:<10} | {ident:<15} | {legit:<15} | {susp:<10}")

    print("\n" + "=" * 100)
    print("INVESTIGATION OF TOP LANGUAGES WITH HIGHEST IDENTICAL COUNTS:")
    print("=" * 100)
    
    sorted_susp = sorted(suspicious_details.items(), key=lambda x: len(x[1]), reverse=True)
    top_3 = sorted_susp[:3] if sorted_susp else []

    if not top_3:
        print("✓ Zero suspicious identical matches across all 22 languages!")
    else:
        for lang, items in top_3:
            print(f"\nLanguage: {LANGUAGE_NAMES.get(lang, lang)} ({lang}) - {len(items)} suspicious identical items:")
            for k, en_val in items[:5]:
                print(f"   Key: {k}")
                print(f"      Source English: \"{en_val}\"")

if __name__ == "__main__":
    audit_completeness()
