from silver_platter.config import AppSettings


def main() -> None:
    settings = AppSettings.from_env()
    print(
        "silver_platter worker heartbeat env=%s redis=%s"
        % (settings.app_env, settings.redis_url)
    )


if __name__ == "__main__":
    main()
