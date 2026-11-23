from app.db import connect, init_db


def test_init_db_creates_core_tables(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"accounts", "tweets", "marks", "sync_log"}.issubset(names)


def test_init_db_is_idempotent(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    init_db(conn)  # must not raise


def test_accounts_has_backfill_columns(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)")}
    assert {"backfill_cursor", "backfill_done"}.issubset(cols)


def test_init_db_migrates_legacy_accounts_table(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    conn.execute(
        """
        CREATE TABLE accounts (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            display_name TEXT,
            profile_json TEXT,
            created_at TEXT,
            last_sync_at TEXT
        )
        """
    )
    conn.commit()
    init_db(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)")}
    assert {"backfill_cursor", "backfill_done"}.issubset(cols)
