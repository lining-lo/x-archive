from app.provider_twitterapi import (
    extract_media,
    parse_created_at,
    parse_tweet,
)


def test_parse_created_at_to_iso_utc():
    assert parse_created_at("Tue Dec 10 07:00:30 +0000 2024") == (
        "2024-12-10T07:00:30+00:00"
    )


def test_extract_media_from_entities():
    raw = {"entities": {"media": [{"type": "photo", "media_url_https": "u"}]}}
    assert extract_media(raw) == [{"type": "photo", "media_url_https": "u"}]


def test_parse_tweet_maps_core_fields():
    raw = {
        "type": "tweet",
        "id": "1001",
        "url": "https://x.com/demo/status/1001",
        "text": "hello",
        "likeCount": 3,
        "retweetCount": 1,
        "replyCount": 2,
        "quoteCount": 0,
        "viewCount": 10,
        "createdAt": "Tue Dec 10 07:00:30 +0000 2024",
        "lang": "zh",
        "isReply": False,
        "isRetweet": False,
        "isQuote": False,
        "conversationId": "1001",
        "author": {"type": "user", "id": "42", "userName": "demo", "name": "Demo"},
        "entities": {"media": [{"type": "photo", "media_url_https": "u"}]},
    }
    tweet = parse_tweet(raw)
    assert tweet.id == "1001"
    assert tweet.account_id == "42"
    assert tweet.text == "hello"
    assert tweet.created_at == "2024-12-10T07:00:30+00:00"
    assert tweet.has_media is True
    assert tweet.like_count == 3
    assert tweet.is_reply is False
