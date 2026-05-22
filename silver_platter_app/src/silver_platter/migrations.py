from pathlib import Path
import sys
from typing import Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def list_migrations() -> List[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def render_migrations(paths: Iterable[Path]) -> str:
    chunks = []
    for path in paths:
        chunks.append("-- migration: %s\n%s\n" % (path.name, path.read_text()))
    return "\n".join(chunks)


def status() -> str:
    migrations = list_migrations()
    lines = ["migrations_dir=%s" % MIGRATIONS_DIR, "count=%s" % len(migrations)]
    lines.extend(path.name for path in migrations)
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    command = argv[1] if len(argv) > 1 else "status"
    if command == "status":
        print(status())
        return 0
    if command == "render":
        print(render_migrations(list_migrations()))
        return 0
    print("unsupported command: %s" % command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
