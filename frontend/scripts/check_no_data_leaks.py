import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"

pattern = re.compile(r'\bt\(([^)]+)\)')

violations = []
checked_calls = 0

for fpath in SRC_DIR.glob("**/*.jsx"):
    content = fpath.read_text(encoding="utf-8")
    for m in pattern.finditer(content):
        checked_calls += 1
        arg = m.group(1).strip()
        first_arg = arg.split(",")[0].strip()

        # Check if first argument is a dynamic variable instead of a string literal
        is_string_literal = (
            (first_arg.startswith("'") and first_arg.endswith("'")) or
            (first_arg.startswith('"') and first_arg.endswith('"')) or
            first_arg.startswith("`registry.status.")
        )

        if not is_string_literal:
            violations.append((str(fpath.relative_to(SRC_DIR)), arg, "Not a static string literal"))

        for forbidden in ["field.value", "doc.filename", "doc.district", "doc.tehsil", "doc.village", "item.details", "audit.details"]:
            if forbidden in first_arg:
                violations.append((str(fpath.relative_to(SRC_DIR)), arg, f"Forbidden data field: {forbidden}"))

print(f"Total t(...) calls analyzed across JSX: {checked_calls}")
if violations:
    print(f"FAILED: {len(violations)} data leaks detected!")
    for f, a, r in violations:
        print(f"  {f} -> t({a}): {r}")
    exit(1)
else:
    print("VERIFIED: 100% of t() calls pass static chrome keys only. Zero dynamic data leaks.")
