from contextlib import closing
from datetime import datetime
from io import BytesIO
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.db import get_connection, init_db
from app.sqlite_backup import TAIPEI, backup_and_verify, checksum, latest_run


def test_backup_day_changes_at_three_am():
    assert latest_run(datetime(2026, 11, 24, 2, 59, tzinfo=TAIPEI)).day == 23
    assert latest_run(datetime(2026, 11, 24, 3, 0, tzinfo=TAIPEI)).day == 24


def test_daily_object_survives_restart_and_is_checked_on_download(tmp_path):
    database = tmp_path / "app.db"
    init_db(str(database))
    with closing(get_connection(str(database))) as db:
        db.execute("INSERT INTO users(username, display_name, role) VALUES ('u', 'U', 'Student')")
        db.commit()
    original = checksum(database)
    stored = {}
    s3 = Mock()
    s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadObject"
    )

    def put(*, Body, Metadata, IfNoneMatch, **kwargs):
        assert IfNoneMatch == "*"
        stored.update(data=Body.read(), metadata=Metadata)

    s3.put_object.side_effect = put
    s3.get_object.side_effect = lambda **kwargs: {
        "Body": BytesIO(stored["data"]), "Metadata": stored["metadata"]
    }
    backup_and_verify(s3, "bucket", "sqlite/day.db", database)
    s3.head_object.side_effect = None
    backup_and_verify(s3, "bucket", "sqlite/day.db", database)
    s3.put_object.assert_called_once()
    stored["data"] += b"damaged"
    with pytest.raises(ValueError, match="SHA-256"):
        backup_and_verify(s3, "bucket", "sqlite/day.db", database)
    assert checksum(database) == original
