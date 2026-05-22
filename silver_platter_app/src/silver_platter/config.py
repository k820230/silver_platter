from dataclasses import dataclass
import os


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _float_from_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class GoldilocksSettings:
    host: str
    port: int
    database: str
    schema: str
    user: str
    password: str
    connect_timeout_seconds: float

    def redacted(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "schema": self.schema,
            "user": self.user,
            "password": "***" if self.password else "",
            "connect_timeout_seconds": self.connect_timeout_seconds,
        }


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    app_timezone: str
    goldilocks: GoldilocksSettings
    redis_url: str
    backup_base_dir: str
    parquet_export_dir: str
    raw_data_dir: str
    log_dir: str
    model_artifact_dir: str
    live_order_enabled: bool
    simulation_order_broker_send: bool

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_timezone=os.getenv("APP_TIMEZONE", "Asia/Seoul"),
            goldilocks=GoldilocksSettings(
                host=os.getenv("GOLDILOCKS_HOST", "host.docker.internal"),
                port=_int_from_env("GOLDILOCKS_PORT", 22581),
                database=os.getenv("GOLDILOCKS_DATABASE", "GOLDILOCKS"),
                schema=os.getenv("GOLDILOCKS_SCHEMA", "SP"),
                user=os.getenv("GOLDILOCKS_USER", "sp_app"),
                password=os.getenv("GOLDILOCKS_PASSWORD", ""),
                connect_timeout_seconds=_float_from_env(
                    "GOLDILOCKS_CONNECT_TIMEOUT_SECONDS", 1.0
                ),
            ),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            backup_base_dir=os.getenv("BACKUP_BASE_DIR", "/home/jhkim5/backup_sp"),
            parquet_export_dir=os.getenv(
                "PARQUET_EXPORT_DIR", "/home/jhkim5/silver_platter_data/parquet"
            ),
            raw_data_dir=os.getenv(
                "RAW_DATA_DIR", "/home/jhkim5/silver_platter_data/raw"
            ),
            log_dir=os.getenv("LOG_DIR", "/home/jhkim5/silver_platter_logs"),
            model_artifact_dir=os.getenv(
                "MODEL_ARTIFACT_DIR", "/home/jhkim5/silver_platter_models"
            ),
            live_order_enabled=_bool_from_env("LIVE_ORDER_ENABLED", False),
            simulation_order_broker_send=_bool_from_env(
                "SIMULATION_ORDER_BROKER_SEND", False
            ),
        )

    def redacted(self) -> dict:
        return {
            "app_env": self.app_env,
            "app_timezone": self.app_timezone,
            "goldilocks": self.goldilocks.redacted(),
            "redis_url": self.redis_url,
            "backup_base_dir": self.backup_base_dir,
            "parquet_export_dir": self.parquet_export_dir,
            "raw_data_dir": self.raw_data_dir,
            "log_dir": self.log_dir,
            "model_artifact_dir": self.model_artifact_dir,
            "live_order_enabled": self.live_order_enabled,
            "simulation_order_broker_send": self.simulation_order_broker_send,
        }
