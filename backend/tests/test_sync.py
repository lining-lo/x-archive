from app.db import connect, init_db
from app.provider_base import Account, TweetPage
from app.store import query_tweets
from app.sync import sync_account
from tests.test_store import make_tweet


class FakeProvider:
    def __init__(self, pages):
        self.pages = pages
        self.seen_cursors = []

    def resolve_account(self, username):
        return Account(id="42", username=username, display_name="Demo", raw={})

    def last_tweets(self, username, cursor, include_replies):
        self.seen_cursors.append(cursor)
        return self.pages[len(self.seen_cursors) - 1]


def fresh():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_first_sync_is_backfill_and_completes():
    conn = fresh()
    provider = FakeProvider([
        TweetPage([make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),
    ])
    result = sync_account(conn, provider, "demo")
    assert result["mode"] == "backfill"
    assert result["backfill_done"] is True
    assert result["new_count"] == 3
    assert result["pages"] == 2
    assert len(query_tweets(conn)) == 3


def test_backfill_resumes_from_saved_cursor_on_next_click():
    conn = fresh()
    first = FakeProvider([TweetPage([make_tweet("3"), make_tweet("2")], True, "c2")])
    r1 = sync_account(conn, first, "demo", max_pages=1)
    assert r1["mode"] == "backfill"
    assert r1["backfill_done"] is False
    assert r1["new_count"] == 2

    second = FakeProvider([TweetPage([make_tweet("1")], False, None)])
    r2 = sync_account(conn, second, "demo")
    assert second.seen_cursors == ["c2"]  # resumed, not restarted from newest
    assert r2["mode"] == "backfill"
    assert r2["backfill_done"] is True
    assert r2["new_count"] == 1
    assert len(query_tweets(conn)) == 3


def test_incremental_continues_until_a_fully_known_page():
    conn = fresh()
    sync_account(
        conn,
        FakeProvider([TweetPage([make_tweet("2"), make_tweet("1")], False, None)]),
        "demo",
    )

    provider = FakeProvider([
        TweetPage([make_tweet("4"), make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),  # all known -> stop here
    ])
    result = sync_account(conn, provider, "demo")
    assert result["mode"] == "incremental"
    assert result["backfill_done"] is True
    assert provider.seen_cursors == [None, "c2"]
    assert result["new_count"] == 2
    assert result["pages"] == 2
    assert len(query_tweets(conn)) == 4


def test_incremental_stops_immediately_when_nothing_new():
    conn = fresh()
    sync_account(
        conn,
        FakeProvider([TweetPage([make_tweet("2"), make_tweet("1")], False, None)]),
        "demo",
    )
    provider = FakeProvider([
        TweetPage([make_tweet("2"), make_tweet("1")], False, None),
        TweetPage([make_tweet("x")], False, None),  # must not be fetched
    ])
    result = sync_account(conn, provider, "demo")
    assert result["mode"] == "incremental"
    assert result["new_count"] == 0
    assert result["pages"] == 1
    assert provider.seen_cursors == [None]
