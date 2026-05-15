"""
ETL configuration — connection settings from environment variables.

Reads from process env (set by docker-compose, .env loader, or shell).
Never hardcode credentials.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )


def _from_env(prefix: str, default_port: int, default_db: str, default_user: str) -> DbConfig:
    return DbConfig(
        host=os.getenv(f"{prefix}_HOST", "localhost"),
        port=int(os.getenv(f"{prefix}_PORT", str(default_port))),
        dbname=os.getenv(f"{prefix}_DB", default_db),
        user=os.getenv(f"{prefix}_USER", default_user),
        password=os.getenv(f"{prefix}_PASSWORD", default_user),
    )


@dataclass(frozen=True)
class Settings:
    syriatel: DbConfig
    mtn: DbConfig
    dw: DbConfig

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    batch_size: int = int(os.getenv("ETL_BATCH_SIZE", "1000"))


settings = Settings(
    syriatel=_from_env("SYRIATEL", 5433, "syriatel_oltp", "syriatel"),
    mtn=_from_env("MTN", 5434, "mtn_oltp", "mtn"),
    dw=_from_env("DW", 5435, "telecom_dw", "dw"),
)
