from app.db import connect, init_db
from app.provider_base import Account, TweetPage
from app.store import query_tweets, upsert_tweets
from app.sync import sync_account
from tests.test_store import make_tweet


class FakeProvider:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def resolve_account(self, username):
        return Account(id="42", username=username, display_name="Demo", raw={})

    def last_tweets(self, username, cursor, include_replies):
        page = self.pages[self.calls]
        self.calls += 1
        return page


def fresh():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_first_sync_paginates_until_no_next():
    conn = fresh()
    provider = FakeProvider([
        TweetPage([make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),
    ])
    result = sync_account(conn, provider, "demo")
    assert result["new_count"] == 3
    assert result["pages"] == 2
    assert len(query_tweets(conn)) == 3


def test_incremental_stops_when_reaching_known_tweet():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("2"), make_tweet("1")])
    provider = FakeProvider([
        TweetPage([make_tweet("4"), make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),  # must not be fetched
    ])
    result = sync_account(conn, provider, "demo")
    assert result["new_count"] == 2
    assert result["pages"] == 1
    assert provider.calls == 1
    assert len(query_tweets(conn)) == 4
