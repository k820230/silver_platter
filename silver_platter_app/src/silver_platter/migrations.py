from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Sequence

from silver_platter.config import AppSettings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


@dataclass(frozen=True)
class MigrationPlanItem:
    name: str
    checksum: str
    statement_count: int


@dataclass(frozen=True)
class MigrationApplyResult:
    name: str
    checksum: str
    status: str
    statement_count: int


def list_migrations() -> List[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_migrations(paths: Iterable[Path]) -> str:
    chunks = []
    for path in paths:
        chunks.append("-- migration: %s\n%s\n" % (path.name, path.read_text()))
    return "\n".join(chunks)


def split_sql_statements(sql: str) -> List[str]:
    statements = []
    buffer = []
    index = 0
    in_single_quote = False
    in_line_comment = False
    in_block_comment = False

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if in_line_comment:
            buffer.append(char)
            if char == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            buffer.append(char)
            if char == "*" and next_char == "/":
                buffer.append(next_char)
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue

        if in_single_quote:
            buffer.append(char)
            if char == "'" and next_char == "'":
                buffer.append(next_char)
                index += 2
                continue
            if char == "'":
                in_single_quote = False
            index += 1
            continue

        if char == "-" and next_char == "-":
            buffer.extend([char, next_char])
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            buffer.extend([char, next_char])
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            buffer.append(char)
            in_single_quote = True
            index += 1
            continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)
    return statements


def build_migration_plan(paths: Sequence[Path]) -> List[MigrationPlanItem]:
    return [
        MigrationPlanItem(
            name=path.name,
            checksum=migration_checksum(path),
            statement_count=len(split_sql_statements(path.read_text())),
        )
        for path in paths
    ]


def format_migration_plan(plan: Sequence[MigrationPlanItem]) -> str:
    lines = ["migration apply plan", "count=%s" % len(plan)]
    lines.extend(
        "%s checksum=%s statements=%s"
        % (item.name, item.checksum, item.statement_count)
        for item in plan
    )
    return "\n".join(lines)


def status() -> str:
    migrations = list_migrations()
    lines = ["migrations_dir=%s" % MIGRATIONS_DIR, "count=%s" % len(migrations)]
    lines.extend(path.name for path in migrations)
    return "\n".join(lines)


def is_missing_migration_note_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "schema_migration_note" in message
        or "does not exist" in message
        or "not exist" in message
        or "not found" in message
        or "undefined table" in message
    )


def load_applied_migrations(connection: object) -> Dict[str, str]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT migration_name, checksum FROM SP.schema_migration_note"
        )
        return {str(row[0]): str(row[1]) for row in cursor.fetchall()}
    except Exception as exc:
        if not is_missing_migration_note_error(exc):
            raise
        return {}


def record_migration(connection: object, name: str, checksum: str) -> None:
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO SP.schema_migration_note (migration_name, checksum) VALUES (?, ?)",
        (name, checksum),
    )


def apply_migrations(
    connection: object,
    paths: Sequence[Path],
) -> List[MigrationApplyResult]:
    applied = load_applied_migrations(connection)
    results: List[MigrationApplyResult] = []

    for path in paths:
        checksum = migration_checksum(path)
        statements = split_sql_statements(path.read_text())
        existing_checksum = applied.get(path.name)
        if existing_checksum == checksum:
            results.append(
                MigrationApplyResult(path.name, checksum, "skipped", len(statements))
            )
            continue
        if existing_checksum is not None and existing_checksum != checksum:
            raise RuntimeError(
                "migration %s was already applied with checksum %s, current checksum %s"
                % (path.name, existing_checksum, checksum)
            )

        cursor = connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
            record_migration(connection, path.name, checksum)
            connection.commit()
            applied[path.name] = checksum
            results.append(
                MigrationApplyResult(path.name, checksum, "applied", len(statements))
            )
        except Exception:
            rollback = getattr(connection, "rollback", None)
            if rollback is not None:
                rollback()
            raise

    return results


def connect_goldilocks_from_env() -> object:
    settings = AppSettings.from_env().goldilocks
    connect_string = os.getenv("GOLDILOCKS_ODBC_CONNECT_STRING", "").strip()
    dsn = os.getenv("GOLDILOCKS_ODBC_DSN", "").strip()
    driver = os.getenv("GOLDILOCKS_ODBC_DRIVER", "").strip()

    if not connect_string and not dsn and not driver:
        raise RuntimeError(
            "set GOLDILOCKS_ODBC_CONNECT_STRING, GOLDILOCKS_ODBC_DSN, "
            "or GOLDILOCKS_ODBC_DRIVER before running migrations"
        )

    try:
        import pyodbc  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pyodbc is required for migrate apply; install the db optional "
            "dependency or configure the API image before applying migrations"
        ) from exc

    if not connect_string:
        if dsn:
            connect_string = "DSN=%s;UID=%s;PWD=%s;DATABASE=%s" % (
                dsn,
                settings.user,
                settings.password,
                settings.database,
            )
        else:
            connect_string = (
                "DRIVER={%s};SERVER=%s;PORT=%s;DATABASE=%s;UID=%s;PWD=%s"
                % (
                    driver,
                    settings.host,
                    settings.port,
                    settings.database,
                    settings.user,
                    settings.password,
                )
            )

    return pyodbc.connect(
        connect_string,
        timeout=max(1, int(settings.connect_timeout_seconds)),
        autocommit=False,
    )


def format_apply_results(results: Sequence[MigrationApplyResult]) -> str:
    lines = ["migration apply results", "count=%s" % len(results)]
    lines.extend(
        "%s status=%s checksum=%s statements=%s"
        % (item.name, item.status, item.checksum, item.statement_count)
        for item in results
    )
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    command = argv[1] if len(argv) > 1 else "status"
    if command == "status":
        print(status())
        return 0
    if command == "render":
        print(render_migrations(list_migrations()))
        return 0
    if command == "plan":
        print(format_migration_plan(build_migration_plan(list_migrations())))
        return 0
    if command == "apply":
        paths = list_migrations()
        if "--dry-run" in argv[2:]:
            print(format_migration_plan(build_migration_plan(paths)))
            return 0
        connection = connect_goldilocks_from_env()
        print(format_apply_results(apply_migrations(connection, paths)))
        return 0
    print("unsupported command: %s" % command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
