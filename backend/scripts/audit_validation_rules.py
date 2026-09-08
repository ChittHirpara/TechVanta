import sys
import json
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.validation import validate_fields

valid_baseline = {
    'owner_name': 'Ram Kumar Singh',
    'survey_number': '78-B',
    'khasra_number': '451/2',
    'khata_number': '112',
    'plot_area': '2 Bigha 14 Biswa',
    'district': 'Jaipur',
    'tehsil': 'Sanganer',
    'village': 'Rampur Kalan',
    'land_classification': 'Agricultural-Irrigated',
}

rules_tests = [
    {
        'rule_id': '1. required_field',
        'desc': 'Fails when required field (owner_name, survey_number, district, tehsil, village) is missing',
        'pass_input': {**valid_baseline, 'owner_name': 'Ram Kumar Singh'},
        'fail_input': {**valid_baseline, 'owner_name': None},
    },
    {
        'rule_id': '2. recommended_field',
        'desc': 'Warns when recommended field (khasra_number, khata_number, plot_area, land_classification) is missing',
        'pass_input': {**valid_baseline, 'khata_number': '112'},
        'fail_input': {**valid_baseline, 'khata_number': None},
    },
    {
        'rule_id': '3. format_survey_number',
        'desc': 'Validates survey_number format against regex pattern',
        'pass_input': {**valid_baseline, 'survey_number': '78-B'},
        'fail_input': {**valid_baseline, 'survey_number': 'INVALID$$--SURVEY##'},
    },
    {
        'rule_id': '4. format_khasra_number',
        'desc': 'Validates khasra_number format against regex pattern',
        'pass_input': {**valid_baseline, 'khasra_number': '451/2'},
        'fail_input': {**valid_baseline, 'khasra_number': 'KHASRA_INVALID_CHARS@@'},
    },
    {
        'rule_id': '5. numeric_plot_area',
        'desc': 'Ensures plot_area starts with a numeric value',
        'pass_input': {**valid_baseline, 'plot_area': '2.5 acres'},
        'fail_input': {**valid_baseline, 'plot_area': 'approx large plot'},
    },
    {
        'rule_id': '6. min_length_owner_name',
        'desc': 'Warns if owner_name is suspiciously short (< 3 chars)',
        'pass_input': {**valid_baseline, 'owner_name': 'Ram Singh'},
        'fail_input': {**valid_baseline, 'owner_name': 'Om'},
    },
    {
        'rule_id': '7. max_length_geo_field',
        'desc': 'Warns if district, tehsil, or village exceeds 150 chars',
        'pass_input': {**valid_baseline, 'village': 'Rampur Kalan'},
        'fail_input': {**valid_baseline, 'village': 'A' * 160},
    },
]

print('======================================================================')
print('PHASE 1.2: VALIDATION RULE ENGINE - TESTING ALL 7 RULES')
print('======================================================================\n')

for t in rules_tests:
    v_pass = validate_fields(t['pass_input'])
    v_fail = validate_fields(t['fail_input'])
    
    rule_name = t['rule_id']
    rule_desc = t['desc']
    print(f'RULE: {rule_name} ({rule_desc})')
    print(f'  ✔ Pass Case Output : {len(v_pass)} violations')
    print(f'  ✘ Fail Case Output : {len(v_fail)} violation(s)')
    for v in v_fail:
        print(f'      • [{v.severity.upper()}] {v.field} -> rule={v.rule}: {v.message}')
    print('-'*70)
