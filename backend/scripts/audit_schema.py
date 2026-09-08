import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db.session import Base
import app.models
from sqlalchemy import create_engine, inspect

db_path = Path(__file__).resolve().parent.parent / 'land_records.db'
engine = create_engine(f'sqlite:///{db_path}')
insp = inspect(engine)
migrated_tables = set(insp.get_table_names())
declared_tables = set(Base.metadata.tables.keys())

print('======================================================================')
print('PHASE 1.5: DATABASE SCHEMA DRIFT AUDIT')
print('======================================================================\n')
print('Migrated Tables in land_records.db :', sorted(migrated_tables))
print('Declared Tables in Base.metadata    :', sorted(declared_tables))

migrated_app_tables = migrated_tables - {'alembic_version'}
diff = declared_tables.symmetric_difference(migrated_app_tables)
print('Schema Table Differences           :', diff if diff else 'None (0 table drift)')
print()

for t in sorted(declared_tables):
    cols_meta = {c.name for c in Base.metadata.tables[t].columns}
    cols_db = {c['name'] for c in insp.get_columns(t)}
    col_diff = cols_meta.symmetric_difference(cols_db)
    status = f'DRIFT DETECTED: {col_diff}' if col_diff else 'None (100% in sync)'
    print(f'Table {t:<20} -> Column Drift: {status}')
