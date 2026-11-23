import json
import sqlite3
from datetime import datetime, timezone

from app.provider_base import Account, Tweet


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tweet_exists(conn: sqlite3.Connection, tweet_id: str) -> bool:
    return conn.execute("SELECT 1 FROM tweets WHERE id = ?", (tweet_id,)).fetchone() is not None


def upsert_account(conn: sqlite3.Connection, account: Account) -> None:
    conn.execute(
        """
        INSERT INTO accounts (id, username, display_name, profile_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            display_name = excluded.display_name,
            profile_json = excluded.profile_json
        """,
        (
            account.id,
            account.username,
            account.display_name,
            json.dumps(account.raw, ensure_ascii=False),
            _now(),
        ),
    )
    conn.commit()


def upsert_tweets(conn: sqlite3.Connection, tweets: list[Tweet]) -> int:
    new_count = 0
    now = _now()
    for t in tweets:
        if not tweet_exists(conn, t.id):
            new_count += 1
        conn.execute(
            """
            INSERT INTO tweets (
                id, account_id, text, lang, created_at, is_reply, is_retweet, is_quote,
                has_media, media_json, url, conversation_id, like_count, retweet_count,
                reply_count, quote_count, view_count, raw_json, inserted_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                text = excluded.text,
                lang = excluded.lang,
                is_reply = excluded.is_reply,
                is_retweet = excluded.is_retweet,
                is_quote = excluded.is_quote,
                has_media = excluded.has_media,
                media_json = excluded.media_json,
                like_count = excluded.like_count,
                retweet_count = excluded.retweet_count,
                reply_count = excluded.reply_count,
                quote_count = excluded.quote_count,
                view_count = excluded.view_count,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """,
            (
                t.id, t.account_id, t.text, t.lang, t.created_at,
                int(t.is_reply), int(t.is_retweet), int(t.is_quote),
                int(t.has_media), json.dumps(t.media, ensure_ascii=False),
                t.url, t.conversation_id, t.like_count, t.retweet_count,
                t.reply_count, t.quote_count, t.view_count,
                json.dumps(t.raw, ensure_ascii=False), now, now,
            ),
        )
    conn.commit()
    return new_count


_KIND_CLAUSES = {
    "original": "(t.is_reply = 0 AND t.is_retweet = 0 AND t.is_quote = 0)",
    "quote": "t.is_quote = 1",
    "reply": "t.is_reply = 1",
    "retweet": "t.is_retweet = 1",
}


def query_tweets(
    conn: sqlite3.Connection,
    account_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    until: str | None = None,
    has_media: bool | None = None,
    kinds: list[str] | None = None,
    starred_only: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    sql = [
        "SELECT t.*, COALESCE(m.starred, 0) AS starred, COALESCE(m.note, '') AS note",
        "FROM tweets t LEFT JOIN marks m ON m.tweet_id = t.id",
        "WHERE 1 = 1",
    ]
    params: list = []
    if account_id:
        sql.append("AND t.account_id = ?")
        params.append(account_id)
    if keyword:
        sql.append("AND t.text LIKE ?")
        params.append(f"%{keyword}%")
    if since:
        sql.append("AND t.created_at >= ?")
        params.append(since)
    if until:
        sql.append("AND t.created_at <= ?")
        params.append(until)
    if has_media is not None:
        sql.append("AND t.has_media = ?")
        params.append(1 if has_media else 0)
    if kinds:
        clauses = [_KIND_CLAUSES[k] for k in kinds if k in _KIND_CLAUSES]
        if clauses:
            sql.append("AND (" + " OR ".join(clauses) + ")")
    if starred_only:
        sql.append("AND COALESCE(m.starred, 0) = 1")
    sql.append("ORDER BY t.created_at DESC LIMIT ? OFFSET ?")
    params += [limit, offset]
    return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def set_mark(
    conn: sqlite3.Connection,
    tweet_id: str,
    starred: bool | None = None,
    note: str | None = None,
) -> None:
    row = conn.execute(
        "SELECT starred, note FROM marks WHERE tweet_id = ?", (tweet_id,)
    ).fetchone()
    cur_starred = row["starred"] if row else 0
    cur_note = row["note"] if row else ""
    new_starred = cur_starred if starred is None else (1 if starred else 0)
    new_note = cur_note if note is None else note
    conn.execute(
        """
        INSERT INTO marks (tweet_id, starred, note, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tweet_id) DO UPDATE SET
            starred = excluded.starred, note = excluded.note, updated_at = excluded.updated_at
        """,
        (tweet_id, new_starred, new_note, _now()),
    )
    conn.commit()


def list_accounts(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute("SELECT * FROM accounts ORDER BY username").fetchall()
    ]


def get_sync_state(conn: sqlite3.Connection, account_id: str) -> dict:
    row = conn.execute(
        "SELECT backfill_cursor, backfill_done FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if row is None:
        return {"cursor": None, "done": False}
    return {"cursor": row["backfill_cursor"], "done": bool(row["backfill_done"])}


def set_backfill_state(
    conn: sqlite3.Connection, account_id: str, *, cursor: str | None, done: bool
) -> None:
    conn.execute(
        "UPDATE accounts SET backfill_cursor = ?, backfill_done = ? WHERE id = ?",
        (cursor, 1 if done else 0, account_id),
    )
    conn.commit()
