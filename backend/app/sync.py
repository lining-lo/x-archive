import sqlite3
from datetime import datetime, timezone

from app.provider_base import Provider, Tweet
from app.store import tweet_exists, upsert_account, upsert_tweets


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
    max_pages: int = 200,
) -> dict:
    started = _now()
    account = provider.resolve_account(username)
    upsert_account(conn, account)

    cursor = None
    pages = 0
    new_count = 0
    status = "ok"
    message = ""
    try:
        while pages < max_pages:
            page = provider.last_tweets(account.username, cursor, include_replies)
            pages += 1
            tweets = _filter(page.tweets, include_retweets, include_replies)
            if not tweets:
                if not page.has_next:
                    break
                cursor = page.cursor
                continue
            reached_known = any(tweet_exists(conn, t.id) for t in tweets)
            new_count += upsert_tweets(conn, tweets)
            if reached_known or not page.has_next:
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
            (account.id, "incremental", started, _now(), new_count, status, message),
        )
        conn.commit()
    return {"account_id": account.id, "new_count": new_count, "pages": pages, "status": status}
