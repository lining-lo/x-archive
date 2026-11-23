from datetime import datetime, timezone
from types import SimpleNamespace

from app.provider_twscrape import parse_twscrape_tweet, parse_twscrape_user


def make_tw():
    return SimpleNamespace(
        id=1001,
        id_str="1001",
        url="https://x.com/demo/status/1001",
        date=datetime(2024, 12, 10, 7, 0, 30, tzinfo=timezone.utc),
        lang="zh",
        rawContent="hello",
        likeCount=3,
        retweetCount=1,
        replyCount=2,
        quoteCount=0,
        viewCount=10,
        conversationId=1001,
        conversationIdStr="1001",
        inReplyToTweetId=None,
        retweetedTweet=None,
        quotedTweet=None,
        media=SimpleNamespace(
            photos=[SimpleNamespace(url="https://pbs.twimg.com/x.jpg")],
            videos=[],
            animated=[],
        ),
        user=SimpleNamespace(id=42, id_str="42", username="demo", displayname="Demo"),
    )


def test_parse_twscrape_tweet_maps_fields():
    t = parse_twscrape_tweet(make_tw())
    assert t.id == "1001"
    assert t.account_id == "42"
    assert t.text == "hello"
    assert t.created_at == "2024-12-10T07:00:30+00:00"
    assert t.has_media is True
    assert t.media[0]["media_url_https"] == "https://pbs.twimg.com/x.jpg"
    assert t.like_count == 3
    assert t.is_reply is False
    assert t.is_retweet is False
    assert t.is_quote is False
    assert t.conversation_id == "1001"


def test_parse_twscrape_tweet_flags_retweet_quote_reply():
    tw = make_tw()
    tw.retweetedTweet = object()
    assert parse_twscrape_tweet(tw).is_retweet is True

    quoted = make_tw()
    quoted.quotedTweet = object()
    assert parse_twscrape_tweet(quoted).is_quote is True

    reply = make_tw()
    reply.inReplyToTweetId = 5
    assert parse_twscrape_tweet(reply).is_reply is True


def test_parse_twscrape_user():
    user = parse_twscrape_user(
        SimpleNamespace(
            id=42, id_str="42", username="demo", displayname="Demo", followersCount=5
        )
    )
    assert user.id == "42"
    assert user.username == "demo"
    assert user.display_name == "Demo"
