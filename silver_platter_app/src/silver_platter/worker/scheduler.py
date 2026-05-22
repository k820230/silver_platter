from datetime import datetime

from silver_platter.config import AppSettings


def main() -> None:
    settings = AppSettings.from_env()
    print(
        "silver_platter scheduler ready timezone=%s backup_base_dir=%s now=%s"
        % (settings.app_timezone, settings.backup_base_dir, datetime.utcnow().isoformat())
    )


if __name__ == "__main__":
    main()
