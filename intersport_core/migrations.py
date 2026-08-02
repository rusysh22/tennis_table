"""Small versioned SQL migration runner for the normalized PostgreSQL schema."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    checksum: str
    sql: str


def discover_migrations(directory=MIGRATIONS_DIR):
    directory = Path(directory)
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=path.stem,
                path=path,
                checksum=sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    return migrations


def apply_migrations(database_url, directory=MIGRATIONS_DIR):
    if not database_url:
        raise ValueError("DATABASE_URL wajib diisi untuk menjalankan migrasi normalized.")

    import psycopg2

    applied_now = []
    connection = psycopg2.connect(database_url)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS intersport")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS intersport.schema_migrations (
                        version TEXT PRIMARY KEY,
                        checksum TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )

        for migration in discover_migrations(directory):
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT checksum FROM intersport.schema_migrations WHERE version = %s",
                        (migration.version,),
                    )
                    row = cursor.fetchone()
                    if row:
                        if row[0] != migration.checksum:
                            raise RuntimeError(
                                f"Checksum migrasi {migration.version} berubah setelah diterapkan."
                            )
                        continue
                    cursor.execute(migration.sql)
                    cursor.execute(
                        """
                        INSERT INTO intersport.schema_migrations (version, checksum)
                        VALUES (%s, %s)
                        """,
                        (migration.version, migration.checksum),
                    )
                    applied_now.append(migration.version)
    finally:
        connection.close()
    return applied_now
