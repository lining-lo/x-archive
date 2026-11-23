from app.db import connect, init_db
from app.provider_base import Account, Tweet
from app.store import (
    list_accounts,
    query_tweets,
    set_mark,
    tweet_exists,
    upsert_account,
    upsert_tweets,
)


def make_tweet(tid="1", text="hello", media=False, reply=False):
    return Tweet(
        id=tid, account_id="42", text=text, created_at="2024-12-10T07:00:30+00:00",
        lang="zh", is_reply=reply, is_retweet=False, is_quote=False,
        has_media=media, media=[{"type": "photo"}] if media else [],
        url=f"https://x.com/demo/status/{tid}", conversation_id=tid,
        like_count=1, retweet_count=0, reply_count=0, quote_count=0, view_count=5,
        raw={"id": tid, "text": text},
    )


def fresh():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_upsert_account_then_list():
    conn = fresh()
    upsert_account(conn, Account(id="42", username="demo", display_name="Demo", raw={}))
    accounts = list_accounts(conn)
    assert len(accounts) == 1
    assert accounts[0]["username"] == "demo"


def test_upsert_tweets_is_idempotent_and_counts_new():
    conn = fresh()
    assert upsert_tweets(conn, [make_tweet("1"), make_tweet("2")]) == 2
    assert upsert_tweets(conn, [make_tweet("2"), make_tweet("3")]) == 1
    assert tweet_exists(conn, "1") is True
    assert tweet_exists(conn, "3") is True
    count = conn.execute("SELECT COUNT(*) AS c FROM tweets").fetchone()["c"]
    assert count == 3


def test_query_filters_keyword_and_media():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1", "苹果"), make_tweet("2", "香蕉", media=True)])
    assert [t["id"] for t in query_tweets(conn, keyword="苹果")] == ["1"]
    assert [t["id"] for t in query_tweets(conn, has_media=True)] == ["2"]


def test_query_excludes_retweets_by_kind():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1")])
    rows = query_tweets(conn, kinds=["original"])
    assert [t["id"] for t in rows] == ["1"]


def test_mark_star_and_note_roundtrip():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1")])
    set_mark(conn, "1", starred=True, note="选题A")
    row = query_tweets(conn, starred_only=True)[0]
    assert row["starred"] == 1
    assert row["note"] == "选题A"
    set_mark(conn, "1", starred=False)
    assert query_tweets(conn, starred_only=True) == []
    assert query_tweets(conn)[0]["note"] == "选题A"
