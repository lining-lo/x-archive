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
