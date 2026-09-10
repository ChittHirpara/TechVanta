import os
import re
import json

def scan_files():
    # Scan all files under frontend/src
    src_dir = 'frontend/src'
    files_to_check = []
    for root, dirs, fnames in os.walk(src_dir):
        for f in fnames:
            if f.endswith('.jsx') or f.endswith('.js'):
                # Exclude i18n config files and test scripts
                if 'i18n' in root:
                    continue
                files_to_check.append(os.path.join(root, f))

    print(f"Total files to scan: {len(files_to_check)}")
    for f in sorted(files_to_check):
        print(f"  - {f}")

if __name__ == '__main__':
    scan_files()
