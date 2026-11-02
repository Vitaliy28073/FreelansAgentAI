from __future__ import annotations

from typing import Any

from app.domain.models import RawJob

SEEN_IDS_CAP = 500


def cursor_is_bootstrapped(cursor: dict[str, Any] | None) -> bool:
    if not cursor:
        return False
    return bool(cursor.get("bootstrapped") or cursor.get("seen_ids") or cursor.get("last_published"))


def next_cursor(
    seen_ids: list[str],
    last_published: str | None,
    *,
    bootstrapped: bool = True,
) -> dict[str, Any]:
    return {
        "seen_ids": list(dict.fromkeys(seen_ids))[:SEEN_IDS_CAP],
        "last_published": last_published,
        "bootstrapped": bootstrapped,
    }


def select_new_jobs(
    raw_jobs: list[RawJob],
    cursor: dict[str, Any] | None,
    limit: int,
) -> tuple[list[RawJob], dict[str, Any]]:
    bootstrapped = cursor_is_bootstrapped(cursor)
    seen_ids = list((cursor or {}).get("seen_ids") or [])
    seen_set = set(seen_ids)
    last_published = (cursor or {}).get("last_published")
    newest = last_published
    all_ids: list[str] = []
    selected: list[RawJob] = []

    for raw in raw_jobs:
        all_ids.append(raw.external_id)
        published_iso = raw.published_at.isoformat() if raw.published_at else None
        if published_iso and (newest is None or published_iso > newest):
            newest = published_iso
        if not bootstrapped:
            continue
        if raw.external_id in seen_set:
            continue
        if last_published and published_iso and published_iso <= last_published:
            continue
        selected.append(raw)
        if len(selected) >= limit:
            break

    if not bootstrapped:
        return [], next_cursor([*all_ids, *seen_ids], newest, bootstrapped=True)

    new_ids = [item.external_id for item in selected]
    return selected, next_cursor([*new_ids, *seen_ids], newest, bootstrapped=True)
