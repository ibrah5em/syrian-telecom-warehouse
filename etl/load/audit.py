"""ETL run audit — open/close run records and write quarantine rows."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import psycopg

from etl.config import settings
from etl.utils.logging import get_logger

logger = get_logger(__name__)


def open_run(batch_id: uuid.UUID, started_at: datetime) -> None:
    with psycopg.connect(settings.dw.conninfo()) as conn:
        conn.execute(
            """
            INSERT INTO dw.etl_runs
                (batch_id, started_at, rows_extracted, rows_loaded, rows_quarantined, status)
            VALUES (%s, %s, 0, 0, 0, 'running')
            """,
            (str(batch_id), started_at),
        )


def close_run(
    batch_id: uuid.UUID,
    finished_at: datetime,
    rows_extracted: int,
    rows_loaded: int,
    rows_quarantined: int,
    status: str,
    notes: str | None = None,
) -> None:
    with psycopg.connect(settings.dw.conninfo()) as conn:
        conn.execute(
            """
            UPDATE dw.etl_runs SET
                finished_at      = %s,
                rows_extracted   = %s,
                rows_loaded      = %s,
                rows_quarantined = %s,
                status           = %s,
                notes            = %s
            WHERE batch_id = %s
            """,
            (finished_at, rows_extracted, rows_loaded, rows_quarantined, status, notes, str(batch_id)),
        )


def write_quarantine(batch_id: uuid.UUID, errors: list[dict]) -> None:
    if not errors:
        return
    rows = [
        (
            str(batch_id),
            e["source_system"],
            e["source_table"],
            json.dumps(e["source_row"], default=str),
            e["reason"],
        )
        for e in errors
    ]
    with psycopg.connect(settings.dw.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO dw.etl_errors
                    (batch_id, source_system, source_table, source_row, reason)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                """,
                rows,
            )
    logger.info("audit: wrote %d quarantine rows for batch %s", len(rows), batch_id)
