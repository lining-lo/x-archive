"""Background sync jobs.

Backfilling an account's history can take many minutes (rate limits), so a sync
runs on its own thread with its own SQLite connection and the UI polls its state.
"""

import threading
from datetime import datetime, timezone
from typing import Callable

from app.db import connect
from app.sync import sync_account


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncJobs:
    def __init__(
        self,
        db_path: str,
        provider_factory: Callable[[], object],
        max_pages: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._provider_factory = provider_factory
        self._max_pages = max_pages
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def status(self, key: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(key)
            return dict(job) if job else None

    def start(self, key: str, username: str, include_replies: bool = False) -> dict:
        with self._lock:
            existing = self._jobs.get(key)
            if existing and existing["state"] == "running":
                return dict(existing)
            job = {
                "state": "running",
                "username": username,
                "started_at": _now(),
                "finished_at": None,
                "pages": 0,
                "new_count": 0,
                "mode": None,
                "backfill_done": None,
                "error": None,
            }
            self._jobs[key] = job
        threading.Thread(
            target=self._run,
            args=(key, username, include_replies),
            name=f"sync-{key}",
            daemon=True,
        ).start()
        return dict(job)

    def _update(self, key: str, **fields) -> None:
        with self._lock:
            if key in self._jobs:
                self._jobs[key].update(fields)

    def _run(self, key: str, username: str, include_replies: bool) -> None:
        conn = connect(self._db_path)
        try:
            provider = self._provider_factory()
            result = sync_account(
                conn,
                provider,
                username,
                include_replies=include_replies,
                max_pages=self._max_pages,
                on_page=lambda p: self._update(
                    key, pages=p["pages"], new_count=p["new_count"], mode=p["mode"]
                ),
            )
            self._update(
                key,
                state="done",
                finished_at=_now(),
                pages=result["pages"],
                new_count=result["new_count"],
                mode=result["mode"],
                backfill_done=result["backfill_done"],
            )
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            self._update(key, state="error", finished_at=_now(), error=str(exc))
        finally:
            conn.close()
