# Migration to make admission_number null=True, unique=True
# Uses manual SQLite table rebuild approach to handle NOT NULL → NULL conversion
import sqlite3 as _sqlite3
from django.conf import settings
from django.db import migrations, models


def rebuild_admission_number(apps, schema_editor):
    """
    SQLite doesn't support ALTER COLUMN, and we can't UPDATE to NULL when
    the column is NOT NULL. So we rebuild the table:
    1. Disable foreign keys
    2. Create a new temp table with admission_number as NULL-able
    3. Copy data, converting '' to NULL
    4. Drop old table, rename new table
    5. Re-enable foreign keys
    """
    db_path = settings.DATABASES['default']['NAME']
    conn = _sqlite3.connect(str(db_path))
    conn.isolation_level = None  # autocommit mode
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # Get current table schema to preserve column definitions
        cols = conn.execute("PRAGMA table_info(accounts_userprofile)").fetchall()
        # cols: (cid, name, type, notnull, dflt_value, pk)
        col_defs = []
        for col in cols:
            cid, name, ctype, notnull, dflt, pk = col
            if name == 'admission_number':
                # Change to NULL-able, unique handled separately
                col_defs.append(f'"{name}" {ctype}')
            else:
                null_part = 'NOT NULL' if notnull else ''
                dflt_part = f'DEFAULT {dflt}' if dflt is not None else ''
                pk_part = 'PRIMARY KEY AUTOINCREMENT' if pk else ''
                parts = [f'"{name}"', ctype, pk_part, null_part, dflt_part]
                col_defs.append(' '.join(p for p in parts if p))

        col_defs_str = ',\n  '.join(col_defs)
        create_sql = f"""
CREATE TABLE "accounts_userprofile_new" (
  {col_defs_str},
  UNIQUE ("admission_number")
)"""
        conn.execute(create_sql)

        # Copy data, converting empty string to NULL
        col_names = [col[1] for col in cols]
        col_names_quoted = ', '.join(f'"{c}"' for c in col_names)
        select_parts = []
        for col in cols:
            name = col[1]
            if name == 'admission_number':
                select_parts.append(
                    f'CASE WHEN "{name}" = \'\' THEN NULL ELSE "{name}" END AS "{name}"'
                )
            else:
                select_parts.append(f'"{name}"')
        select_str = ', '.join(select_parts)

        conn.execute(f"""
INSERT INTO "accounts_userprofile_new" ({col_names_quoted})
SELECT {select_str}
FROM "accounts_userprofile"
""")

        conn.execute('DROP TABLE "accounts_userprofile"')
        conn.execute('ALTER TABLE "accounts_userprofile_new" RENAME TO "accounts_userprofile"')

        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        conn.execute("ROLLBACK")
        conn.execute("PRAGMA foreign_keys = ON")
        raise
    finally:
        conn.close()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('accounts', '0002_userprofile_must_change_password_and_more'),
    ]

    operations = [
        migrations.RunPython(rebuild_admission_number, reverse_code=migrations.RunPython.noop),
        # Tell Django the field is now null=True, unique=True (table already matches)
        migrations.AlterField(
            model_name='userprofile',
            name='admission_number',
            field=models.CharField(blank=True, null=True, max_length=50, unique=True),
        ),
    ]
