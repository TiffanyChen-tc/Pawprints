from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.models import EventMedia
from conftest import EVENT_A, bearer, image_bytes, upload_images


def test_metadata_failure_deletes_previously_written_files(client, token_a, monkeypatch, storage_root):
    import app.routes

    original_add = app.routes.Session.add

    def fail_on_add(self, instance, _warn=True):
        if isinstance(instance, EventMedia):
            raise RuntimeError("db failed")
        return original_add(self, instance, _warn=_warn)

    monkeypatch.setattr(app.routes.Session, "add", fail_on_add)
    with pytest.raises(RuntimeError):
        upload_images(client, token_a, EVENT_A, [image_bytes()])

    assert list(storage_root.rglob("*.*")) == []


def test_storage_failure_leaves_no_committed_metadata(client, token_a, monkeypatch, media_db_session):
    import app.routes

    def failing_write(self, key, content):
        raise OSError("disk full")

    monkeypatch.setattr(app.routes.LocalFileStorage, "write", failing_write)
    response = upload_images(client, token_a, EVENT_A, [image_bytes()])

    assert response.status_code == 500
    assert media_db_session.scalars(select(EventMedia)).all() == []


def test_two_concurrent_uploads_from_four_existing_media_allow_at_most_one(client, token_a, media_db_session, storage_root):
    assert upload_images(client, token_a, EVENT_A, [image_bytes()] * 4).status_code == 201

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: upload_images(client, token_a, EVENT_A, [image_bytes()]), range(2)))

    assert sum(result.status_code == 201 for result in results) == 1
    assert sum(result.status_code == 409 for result in results) == 1
    rows = media_db_session.scalars(select(EventMedia).where(EventMedia.event_id == EVENT_A)).all()
    assert len(rows) == 5
    orders = [row.display_order for row in rows]
    assert len(orders) == len(set(orders))
    stored_files = [path for path in storage_root.rglob("*") if path.is_file()]
    assert len(stored_files) == 5
