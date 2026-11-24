"""Daily SQLite online backups to a private S3-compatible bucket."""

import asyncio
import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.db import get_db_path

log = logging.getLogger("uvicorn.error")
TAIPEI = timezone(timedelta(hours=8))


def latest_run(now: datetime) -> datetime:
    now = now.astimezone(TAIPEI)
    scheduled = now.replace(hour=3, minute=0, second=0, microsecond=0)
    return scheduled if now >= scheduled else scheduled - timedelta(days=1)


def readonly_db(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup_and_verify(s3, bucket: str, key: str, database: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="cosmomate-backup-") as directory:
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                raise
            snapshot = Path(directory) / "snapshot.db"
            with closing(readonly_db(database)) as source, closing(sqlite3.connect(snapshot)) as copy:
                source.backup(copy, pages=256)
            with snapshot.open("rb") as stream:
                try:
                    s3.put_object(
                        Bucket=bucket, Key=key, Body=stream, IfNoneMatch="*",
                        Metadata={"sha256": checksum(snapshot)},
                    )
                except ClientError as conflict:
                    if conflict.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                        raise

        restored = Path(directory) / "restored.db"
        response = s3.get_object(Bucket=bucket, Key=key)
        with closing(response["Body"]) as body, restored.open("xb") as target:
            shutil.copyfileobj(body, target)
        digest = checksum(restored)
        if digest != response["Metadata"]["sha256"]:
            raise ValueError("Downloaded SQLite backup failed its SHA-256 check")
        with closing(readonly_db(restored)) as db:
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Restored SQLite database failed its integrity check")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Restored SQLite database contains broken foreign keys")
            counts = {
                table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("users", "cases", "tasks", "notifications", "mood_journals")
            }
        log.info("SQLite backup restored and verified: key=%s bytes=%s sha256=%s rows=%s",
                 key, restored.stat().st_size, digest, counts)


def run_daily_backup(scheduled: datetime) -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["SQLITE_BACKUP_ENDPOINT"],
        region_name=os.environ["SQLITE_BACKUP_REGION"],
        aws_access_key_id=os.environ["SQLITE_BACKUP_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["SQLITE_BACKUP_SECRET_ACCESS_KEY"],
        config=Config(s3={"addressing_style": "virtual"}, request_checksum_calculation="when_required"),
    )
    try:
        backup_and_verify(s3, os.environ["SQLITE_BACKUP_BUCKET"],
                          f"sqlite/{scheduled.date()}.db", Path(get_db_path()))
    finally:
        s3.close()


async def daily_backups() -> None:
    while True:
        scheduled = latest_run(datetime.now(TAIPEI))
        try:
            await asyncio.to_thread(run_daily_backup, scheduled)
        except Exception:
            log.exception("SQLite backup failed; retrying in five minutes")
            await asyncio.sleep(300)
            continue
        next_run = scheduled + timedelta(days=1)
        log.info("Next SQLite backup: %s", next_run.isoformat())
        await asyncio.sleep(max(0, (next_run - datetime.now(TAIPEI)).total_seconds()))
