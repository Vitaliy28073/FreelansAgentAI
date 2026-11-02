from __future__ import annotations

from datetime import datetime, timezone

from app.connectors.cursor import cursor_is_bootstrapped, select_new_jobs
from app.domain.enums import SourceCode
from app.domain.models import RawJob


def _raw(external_id: str, published: str) -> RawJob:
    return RawJob(
        source=SourceCode.FL_RSS,
        external_id=external_id,
        url=f"https://www.fl.ru/projects/{external_id}/x.html",
        title=f"Job {external_id}",
        published_at=datetime.fromisoformat(published).replace(tzinfo=timezone.utc),
    )


def test_empty_cursor_bootstraps_without_returning_jobs() -> None:
    jobs, cursor = select_new_jobs(
        [_raw("1", "2026-11-02T12:00:00"), _raw("2", "2026-11-02T11:00:00")],
        {},
        40,
    )
    assert jobs == []
    assert cursor["bootstrapped"] is True
    assert cursor["seen_ids"] == ["1", "2"]
    assert cursor["last_published"] == "2026-11-02T12:00:00+00:00"


def test_bootstrapped_cursor_returns_only_unseen() -> None:
    baseline = {
        "bootstrapped": True,
        "seen_ids": ["1", "2"],
        "last_published": "2026-11-02T12:00:00+00:00",
    }
    jobs, cursor = select_new_jobs(
        [
            _raw("3", "2026-11-02T13:00:00"),
            _raw("1", "2026-11-02T12:00:00"),
            _raw("2", "2026-11-02T11:00:00"),
        ],
        baseline,
        40,
    )
    assert [item.external_id for item in jobs] == ["3"]
    assert cursor["seen_ids"][0] == "3"
    assert "1" in cursor["seen_ids"]


def test_cursor_is_bootstrapped() -> None:
    assert cursor_is_bootstrapped(None) is False
    assert cursor_is_bootstrapped({}) is False
    assert cursor_is_bootstrapped({"seen_ids": ["1"]}) is True
    assert cursor_is_bootstrapped({"bootstrapped": True}) is True
