"""
ETL listener — waits for pg_cron NOTIFY then runs `python -m etl`.

On startup, if the last successful batch is older than 8 days (or has never
run), a catch-up run is triggered immediately before entering the listen loop.
A missed NOTIFY (listener was down at 02:00) is recovered this way.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone

import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)

_CHANNEL = "telecom_etl"
_CATCHUP_THRESHOLD_DAYS = 8
_HEARTBEAT_SECS = 60.0
_RECONNECT_DELAY_SECS = 10


def _seconds_since_last_success(conn: psycopg.Connection) -> float | None:
    row = conn.execute(
        "SELECT MAX(started_at) FROM etl_runs WHERE status = 'succeeded'"
    ).fetchone()
    if not row or row[0] is None:
        return None
    last: datetime = row[0]
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds()


def _run_etl() -> None:
    logger.info("Running ETL batch")
    result = subprocess.run([sys.executable, "-m", "etl"], check=False)
    if result.returncode != 0:
        logger.error("ETL subprocess exited with code %d", result.returncode)
    else:
        logger.info("ETL batch completed successfully")


def _listen_loop() -> None:
    dsn = settings.dw.conninfo()
    with psycopg.connect(dsn, autocommit=True) as conn:
        age = _seconds_since_last_success(conn)
        if age is None or age > _CATCHUP_THRESHOLD_DAYS * 86_400:
            logger.info(
                "Catch-up triggered — last success was %s",
                f"{age / 86_400:.1f} days ago" if age is not None else "never",
            )
            _run_etl()

        conn.execute(f"LISTEN {_CHANNEL}")
        logger.info("Listening on channel '%s' (heartbeat every %ds)", _CHANNEL, int(_HEARTBEAT_SECS))

        while True:
            for notify in conn.notifies(timeout=_HEARTBEAT_SECS):
                logger.info(
                    "NOTIFY received on '%s' (pid=%s, payload=%r) — triggering ETL",
                    notify.channel, notify.pid, notify.payload,
                )
                _run_etl()
            logger.debug("Heartbeat — still listening")


def main() -> None:
    logger.info("ETL listener process starting")
    while True:
        try:
            _listen_loop()
        except Exception:
            logger.exception("Listener error — reconnecting in %ds", _RECONNECT_DELAY_SECS)
            time.sleep(_RECONNECT_DELAY_SECS)


if __name__ == "__main__":
    main()
