import os
import re
import sys

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

def find_untranslated_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    untranslated = []

    # 1. JSX text nodes: > ... < across newlines
    # Find all > ... < that contain non-whitespace text and don't start with {
    jsx_text_pattern = re.compile(r'>([^<{}]+)<')
    for m in jsx_text_pattern.finditer(content):
        raw = m.group(1)
        # Normalize whitespace
        text = ' '.join(raw.split()).strip()
        # Clean html entities
        text_clean = text.replace('&amp;', '&').replace('&bull;', '•')
        if not text_clean:
            continue
        # Skip pure symbols, numbers, punctuation
        if re.match(r'^[•\s\-_/\\|:;,.\(\)\d%#~▲▼]+$', text_clean):
            continue
        # Check if line has t(
        start_idx = m.start()
        line_no = content[:start_idx].count('\n') + 1
        line = content.split('\n')[line_no - 1]
        if 't(' in line:
            # Check if this exact text is inside t()
            continue
        untranslated.append((line_no, 'JSX Text', text_clean))

    # 2. Attributes: title="...", placeholder="...", aria-label="..."
    attr_pattern = re.compile(r'\b(title|placeholder|aria-label)=[\'"]([^\'"]+)[\'"]')
    for m in attr_pattern.finditer(content):
        attr, val = m.group(1), m.group(2).strip()
        start_idx = m.start()
        line_no = content[:start_idx].count('\n') + 1
        if val and not val.startswith('e.g.'):
            untranslated.append((line_no, f'Attr {attr}', val))

    # 3. String literals in JS (e.g. ternary, toasts, tooltips)
    # Match showToast?.('...', ...) or showToast('...', ...) or `...`
    toast_pattern = re.compile(r'showToast\??\.\(\s*([`\'"])(.*?)\1')
    for m in toast_pattern.finditer(content):
        quote, val = m.group(1), m.group(2).strip()
        start_idx = m.start()
        line_no = content[:start_idx].count('\n') + 1
        untranslated.append((line_no, 'Toast Msg', val))

    # 4. Title attributes in JSX elements like title={isFieldOfficer ? '...' : ''}
    ternary_title_pattern = re.compile(r'title=\{[^\}]*?[\'"]([A-Z][^\'"]+[\'"])[^\}]*?\}')
    for m in ternary_title_pattern.finditer(content):
        val = m.group(1).strip()
        start_idx = m.start()
        line_no = content[:start_idx].count('\n') + 1
        untranslated.append((line_no, 'Conditional Title', val))

    return untranslated

files = [
    'frontend/src/App.jsx',
    'frontend/src/components/auth/AuthModal.jsx',
    'frontend/src/components/common/GovStrip.jsx',
    'frontend/src/components/common/Header.jsx',
    'frontend/src/components/common/Navigation.jsx',
    'frontend/src/components/common/Toast.jsx',
    'frontend/src/components/dashboard/Dashboard.jsx',
    'frontend/src/components/ingestion/Ingestion.jsx',
    'frontend/src/components/modals/AuditModal.jsx',
    'frontend/src/components/modals/DilrmpModal.jsx',
    'frontend/src/components/modals/DuplicateCompareModal.jsx',
    'frontend/src/components/modals/FieldModal.jsx',
    'frontend/src/components/registry/Registry.jsx',
    'frontend/src/components/workspace/CadastralMapPanel.jsx',
    'frontend/src/components/workspace/Workspace.jsx'
]

total_found = 0
for f in files:
    results = find_untranslated_in_file(f)
    if results:
        print(f"\n=== {f} ({len(results)} items) ===")
        for line_no, kind, text in results:
            # Skip language names in Header.jsx
            if 'Header.jsx' in f and kind == 'JSX Text' and ('Hindi' in text or 'English' in text or 'Bengali' in text):
                continue
            print(f"  L{line_no} [{kind}]: {text}")
            total_found += 1

print(f"\nTotal potential untranslated items found: {total_found}")
