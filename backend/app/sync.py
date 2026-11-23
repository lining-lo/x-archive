import sqlite3
from datetime import datetime, timezone
from typing import Callable

from app.provider_base import Provider, Tweet
from app.store import (
    get_sync_state,
    set_backfill_state,
    tweet_exists,
    upsert_account,
    upsert_tweets,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter(
    tweets: list[Tweet], include_retweets: bool, include_replies: bool
) -> list[Tweet]:
    kept = []
    for t in tweets:
        if t.is_retweet and not include_retweets:
            continue
        if t.is_reply and not include_replies:
            continue
        kept.append(t)
    return kept


def sync_account(
    conn: sqlite3.Connection,
    provider: Provider,
    username: str,
    include_replies: bool = False,
    include_retweets: bool = False,
    max_pages: int | None = None,
    on_page: Callable[[dict], None] | None = None,
) -> dict:
    started = _now()
    account = provider.resolve_account(username)
    upsert_account(conn, account)

    state = get_sync_state(conn, account.id)
    mode = "incremental" if state["done"] else "backfill"
    backfill_done = state["done"]

    pages = 0
    new_count = 0
    status = "ok"
    message = ""
    try:
        if mode == "backfill":
            # Walk deeper into history from the saved cursor. Never stop on a
            # known tweet here: everything below the resume point is new.
            cursor = state["cursor"]
            completed = False
            while max_pages is None or pages < max_pages:
                page = provider.last_tweets(account.username, cursor, include_replies)
                pages += 1
                tweets = _filter(page.tweets, include_retweets, include_replies)
                if tweets:
                    new_count += upsert_tweets(conn, tweets)
                if on_page:
                    on_page({"mode": "backfill", "pages": pages, "new_count": new_count})
                if not page.has_next:
                    completed = True
                    break
                cursor = page.cursor
                set_backfill_state(conn, account.id, cursor=cursor, done=False)
            set_backfill_state(
                conn, account.id, cursor=None if completed else cursor, done=completed
            )
            backfill_done = completed
        else:
            # Incremental refresh: newest first. Stop once a whole page is
            # already stored (a pinned tweet can appear first, so "any known
            # tweet" would stop too early and skip genuinely new posts).
            cursor = None
            while max_pages is None or pages < max_pages:
                page = provider.last_tweets(account.username, cursor, include_replies)
                pages += 1
                tweets = _filter(page.tweets, include_retweets, include_replies)
                if not tweets:
                    if not page.has_next:
                        break
                    cursor = page.cursor
                    continue
                all_known = all(tweet_exists(conn, t.id) for t in tweets)
                new_count += upsert_tweets(conn, tweets)
                if on_page:
                    on_page(
                        {"mode": "incremental", "pages": pages, "new_count": new_count}
                    )
                if all_known or not page.has_next:
                    break
                cursor = page.cursor
        conn.execute(
            "UPDATE accounts SET last_sync_at = ? WHERE id = ?",
            (_now(), account.id),
        )
        conn.commit()
    except Exception as exc:
        status = "error"
        message = str(exc)
        raise
    finally:
        conn.execute(
            """
            INSERT INTO sync_log (account_id, mode, started_at, finished_at, new_count, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (account.id, mode, started, _now(), new_count, status, message),
        )
        conn.commit()
    return {
        "account_id": account.id,
        "new_count": new_count,
        "pages": pages,
        "mode": mode,
        "backfill_done": backfill_done,
        "status": status,
    }
