import json
import sys
import re
from pathlib import Path
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LOCALES_DIR = Path(__file__).resolve().parent.parent / "public" / "locales"
EN_FILE = LOCALES_DIR / "en.json"

TARGET_LANGUAGES = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok",
    "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat",
    "sd", "ta", "te", "ur"
]

RISK_TERMS = ["stamp", "seal", "push", "pipeline", "flag", "stream", "ingest"]

INDIC_CONJUNCTIONS = {
    "and", "or", "&", "+", "-", "/",
    "और", "तथा", "एवं", "व", "या", "अथवा", "اور", "یا", "ਅਤੇ", "ਜਾਂ", "ਤੇ",
    "మరియు", "లేదా", "மற்றும்", "அல்லது", "ಮತ್ತು", "ಅಥವಾ", "കൂടാതെ", "അല്ലെങ്കിൽ",
    "এবং", "বা", "আৰু", "ବା", "ଏବଂ", "ଓ", "କିମ୍ବା", "અને", "અથવા", "आणि", "किंवा",
    "का", "की", "के", "में", "से", "पर", "को", "ਨੇ", "ਦਾ", "ਦੀ", "ਦੇ", "ਨੂੰ", "నుండి", "కు", "తో",
    "ਆ", "ਓ", "ਰ", "ਚ", "ਵਿੱਚ", "ਵਿਚ", "واري", "وارو", "وارا", "۾", "منٛز", "कें", "केँ", "लेल"
}

# Standard grammatical participial suffixes / agreement verbs across languages
GRAMMATICAL_SUFFIXES = {
    "करें", "करो", "करना", "कर", "ਕਰੋ", "ਕੀਤਾ", "करा", "करावे", "గారు", "చేయండి", "செய்யவும்", "করুন", "गर्नुहोस्",
    "شدہ", "ٿيل", "ᱟᱠᱟᱱᱟ", "ᱟᱠᱟᱱ", "হৈছে", "কৰা", "গেआ", "गेया", "गया", "गए", "केला", "हୋଇଛି", "ହୋଇଛି", "হয়েছে"
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

def main():
    print("=" * 80)
    print("TIER 3 AUTOMATED QUALITY ASSURANCE GATE AUDIT")
    print("=" * 80)

    with open(EN_FILE, "r", encoding="utf-8") as f:
        en_data = json.load(f)
    flat_en = flatten_dict(en_data)

    conj_keys = {}
    for k, text in flat_en.items():
        match = re.search(r"(\b[A-Za-z0-9_-]+\b)\s*(?:&|&amp;|\band\b)\s*(\b[A-Za-z0-9_-]+\b)", text, re.IGNORECASE)
        if match and match.group(1).lower() != match.group(2).lower():
            conj_keys[k] = (text, match.group(1), match.group(2))

    print(f"Total canonical English keys: {len(flat_en)}")
    print(f"Keys with conjunctions (& / and): {len(conj_keys)}")

    total_checks = 0
    token_leaks = []
    conjunction_collisions = []
    length_anomalies = []
    raw_metaphor_leaks = []

    for lang in TARGET_LANGUAGES:
        l_file = LOCALES_DIR / f"{lang}.json"
        if not l_file.exists():
            print(f"[FAIL] Missing locale file for {lang}!", file=sys.stderr)
            sys.exit(1)

        with open(l_file, "r", encoding="utf-8") as f:
            l_data = json.load(f)
        flat_lang = flatten_dict(l_data)

        # 1. Key count check
        if len(flat_lang) != len(flat_en):
            print(f"[FAIL] Key count mismatch for {lang}: expected {len(flat_en)}, got {len(flat_lang)}", file=sys.stderr)
            sys.exit(1)

        for key, text in flat_lang.items():
            total_checks += 1
            en_orig = flat_en[key]

            # 1. Token restoration check (Zero un-restored token placeholders or brackets)
            if "[[" in text or "]]" in text:
                token_leaks.append((lang, key, text))

            # 2. Conjunction collision check
            if key in conj_keys:
                cleaned = re.sub(r"[^\w\s\u0900-\u0DFF\u0600-\u06FF]", " ", text)
                words = [w.strip() for w in cleaned.split() if w.strip()]
                content_words = [w for w in words if len(w) > 2 and w.lower() not in INDIC_CONJUNCTIONS and w not in GRAMMATICAL_SUFFIXES]
                counts = Counter(content_words)
                # Ignore duplicate brand or acronym words like AI in "BhoomiScan AI ... AI Engine"
                dups = [w for w, count in counts.items() if count > 1 and w.upper() not in ["AI", "এআই", "एआई", "ਏਆਈ", "ఏఐ", "ஏஐ", "QR"]]
                if dups:
                    conjunction_collisions.append((lang, key, en_orig, text, dups))

            # 3. Length anomaly detector (> 3.5x English length)
            if len(text) > 3.5 * len(en_orig) and len(en_orig) > 6:
                length_anomalies.append((lang, key, len(en_orig), len(text), en_orig, text))

            # 4. Untranslated raw risk term leak detector
            for rk in RISK_TERMS:
                # Whole word match in English Latin characters
                if re.search(r"\b" + re.escape(rk) + r"\b", text, re.IGNORECASE):
                    raw_metaphor_leaks.append((lang, key, rk, text))

    print("-" * 80)
    print("GATE 1: Token Restoration Check (Protected Acronyms & Tokens):")
    if token_leaks:
        print(f"  FAILED: {len(token_leaks)} tokens leaked in output!", file=sys.stderr)
        for lang, k, t in token_leaks:
            print(f"    [{lang}] {k}: {t}", file=sys.stderr)
    else:
        print(f"  PASS: 0 token placeholders leaked across all {len(TARGET_LANGUAGES)} languages.")

    print("\nGATE 2: Conjunction Collision Check (Tautology Elimination):")
    if conjunction_collisions:
        print(f"  FAILED: {len(conjunction_collisions)} collisions detected!", file=sys.stderr)
        for lang, k, en, t, dups in conjunction_collisions:
            print(f"    [{lang}] {k}: '{en}' -> '{t}' | Collided stems: {dups}", file=sys.stderr)
    else:
        print(f"  PASS: 0 semantic collisions across all {len(conj_keys) * len(TARGET_LANGUAGES)} conjunction pairs.")

    print("\nGATE 3: Length Anomaly Detector (Max 3.5x ratio):")
    if length_anomalies:
        print(f"  FAILED: {len(length_anomalies)} length anomalies detected!", file=sys.stderr)
        for lang, k, len_en, len_t, en, t in length_anomalies:
            print(f"    [{lang}] {k} (en:{len_en} -> target:{len_t}): '{en}' -> '{t}'", file=sys.stderr)
    else:
        print(f"  PASS: 0 length anomalies across all {total_checks} strings.")

    print("\nGATE 4: Untranslated Raw Risk Metaphor Leak Detector:")
    if raw_metaphor_leaks:
        print(f"  FAILED: {len(raw_metaphor_leaks)} raw metaphor leaks detected!", file=sys.stderr)
        for lang, k, rk, t in raw_metaphor_leaks:
            print(f"    [{lang}] {k}: leaked '{rk}' in '{t}'", file=sys.stderr)
    else:
        print(f"  PASS: 0 unnormalized English metaphors leaked verbatim across all {len(TARGET_LANGUAGES)} languages.")

    print("\n" + "=" * 80)
    if token_leaks or conjunction_collisions or length_anomalies or raw_metaphor_leaks:
        print("RESULT: TIER 3 QA GATE FAILED. Fix highlighted defects before deployment.", file=sys.stderr)
        sys.exit(1)
    else:
        print("RESULT: TIER 3 QA GATE PASSED WITH ZERO FLAGGED DEFECTS (100% CLEAN).")
        print("=" * 80)

if __name__ == "__main__":
    main()
