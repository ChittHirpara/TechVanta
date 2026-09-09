import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

LOCALES_DIR = Path(__file__).resolve().parent.parent / "public" / "locales"
EN_FILE = LOCALES_DIR / "en.json"

with open(EN_FILE, "r", encoding="utf-8") as f:
    en_data = json.load(f)

def flatten_dict(d, prefix=""):
    flat = {}
    for k, v in d.items():
        curr_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(flatten_dict(v, curr_key))
        elif isinstance(v, str):
            flat[curr_key] = v
    return flat

flat_en = flatten_dict(en_data)

TOKEN_KEYWORDS = [
    ("BhoomiScan AI", re.compile(r"\[\[[^\]]*(?:bhoomi|भूमिस्क|ᱵᱷᱩᱢᱤ|स्कन्)[^\]]*\]\]", re.IGNORECASE)),
    ("DILRMP", re.compile(r"\[\[[^\]]*(?:dilrmp|ᱰᱤᱞᱟᱨ|डीएलआर|ꯗꯤ)[^\]]*\]\]", re.IGNORECASE)),
    ("ULPIN", re.compile(r"\[\[[^\]]*(?:ulpin|ᱩᱞᱯᱤᱱ)[^\]]*\]\]", re.IGNORECASE)),
    ("SHA-256", re.compile(r"\[\[[^\]]*(?:sha|ᱥᱮᱪ|ᱥᱟ|ᱮᱥᱮᱪ)[^\]]*\]\]", re.IGNORECASE)),
    ("Tehsil", re.compile(r"\[\[[^\]]*(?:tehsil|ᱛᱮᱦᱥᱤᱞ)[^\]]*\]\]", re.IGNORECASE)),
    ("Patwari", re.compile(r"\[\[[^\]]*(?:patwari|ᱯᱟᱴᱣᱟᱨᱤ)[^\]]*\]\]", re.IGNORECASE)),
    ("Talati", re.compile(r"\[\[[^\]]*(?:talati|ᱛᱟᱞᱟᱴᱤ)[^\]]*\]\]", re.IGNORECASE)),
    ("Khasra", re.compile(r"\[\[[^\]]*(?:khasra|ᱠᱷᱟᱥᱨᱟ)[^\]]*\]\]", re.IGNORECASE)),
]

def clean_dict(d, prefix=""):
    for k, v in list(d.items()):
        curr_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            clean_dict(v, curr_key)
        elif isinstance(v, str) and ("[[" in v or "]]" in v):
            en_val = flat_en.get(curr_key, "")
            fixed_val = v

            # 1. Replace known named tokens
            for term, pat in TOKEN_KEYWORDS:
                if term in en_val:
                    fixed_val = pat.sub(term, fixed_val)

            # 2. Extract remaining {{var}} from en_val in sequential order
            en_vars = re.findall(r"\{\{[^}]+\}\}", en_val)
            # Find any remaining bracket patterns [[...]]
            rem_brackets = re.findall(r"\[\[[^\]]+\]\]", fixed_val)
            if len(en_vars) == len(rem_brackets):
                for en_var, br in zip(en_vars, rem_brackets):
                    fixed_val = fixed_val.replace(br, en_var, 1)

            # Catch any stray double bracket artifacts
            fixed_val = re.sub(r"\[\[\s*", "", fixed_val)
            fixed_val = re.sub(r"\s*\]\]", "", fixed_val)

            d[k] = fixed_val

def main():
    total_fixed = 0
    for locale_file in LOCALES_DIR.glob("*.json"):
        if locale_file.name == "en.json":
            continue
        with open(locale_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        clean_dict(data)
        with open(locale_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Cleaned {locale_file.name}")

if __name__ == "__main__":
    main()
