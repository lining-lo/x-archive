import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    profile_json TEXT,
    created_at TEXT,
    last_sync_at TEXT,
    backfill_cursor TEXT,
    backfill_done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    text TEXT NOT NULL,
    lang TEXT,
    created_at TEXT NOT NULL,
    is_reply INTEGER NOT NULL DEFAULT 0,
    is_retweet INTEGER NOT NULL DEFAULT 0,
    is_quote INTEGER NOT NULL DEFAULT 0,
    has_media INTEGER NOT NULL DEFAULT 0,
    media_json TEXT,
    url TEXT,
    conversation_id TEXT,
    like_count INTEGER,
    retweet_count INTEGER,
    reply_count INTEGER,
    quote_count INTEGER,
    view_count INTEGER,
    raw_json TEXT,
    inserted_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_account_created
    ON tweets(account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS marks (
    tweet_id TEXT PRIMARY KEY,
    starred INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    mode TEXT,
    started_at TEXT,
    finished_at TEXT,
    new_count INTEGER,
    status TEXT,
    message TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_accounts(conn)
    conn.commit()


def _migrate_accounts(conn: sqlite3.Connection) -> None:
    """Add backfill columns to pre-existing databases."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)")}
    if "backfill_cursor" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN backfill_cursor TEXT")
    if "backfill_done" not in cols:
        conn.execute(
            "ALTER TABLE accounts ADD COLUMN backfill_done INTEGER NOT NULL DEFAULT 0"
        )
