import os
import re
import json

# Read existing en.json
def get_flat_keys(d, prefix=''):
    res = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            res.update(get_flat_keys(v, full_key))
        else:
            res[full_key] = v
    return res

with open('frontend/public/locales/en.json', 'r', encoding='utf-8') as f:
    existing_en = json.load(f)
existing_flat = get_flat_keys(existing_en)

print(f"Existing flat keys count: {len(existing_flat)}")

# Scan each JSX file for raw text nodes outside of {t(...)}
jsx_files = [
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
    'frontend/src/components/workspace/Workspace.jsx',
    'frontend/index.html'
]

for fpath in jsx_files:
    if not os.path.exists(fpath):
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count t() calls
    t_calls = len(re.findall(r'\bt\([\'"]([^\'"]+)[\'"]', content))
    print(f"\n--- {fpath} (t() calls: {t_calls}) ---")
    
    # Check for placeholder="..."
    placeholders = re.findall(r'placeholder=([\'"][^\'"]+[\'"]|\{[^\}]+\})', content)
    if placeholders:
        print(f"  Placeholders: {placeholders}")
        
    # Check for title="..."
    titles = re.findall(r'\btitle=([\'"][^\'"]+[\'"]|\{[^\}]+\})', content)
    if titles:
        print(f"  Titles: {titles}")

    # Check for aria-label="..."
    aria_labels = re.findall(r'aria-label=([\'"][^\'"]+[\'"]|\{[^\}]+\})', content)
    if aria_labels:
        print(f"  Aria labels: {aria_labels}")
