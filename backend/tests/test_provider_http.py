import httpx
import pytest

from app.provider_twitterapi import TwitterApiIoError, TwitterApiIoProvider


def make_provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TwitterApiIoProvider(api_key="k", client=client)


def test_resolve_account():
    def handler(request):
        assert request.headers["X-API-Key"] == "k"
        assert request.url.params["userName"] == "demo"
        return httpx.Response(
            200,
            json={"status": "success", "data": {"id": "42", "userName": "demo", "name": "Demo"}},
        )

    account = make_provider(handler).resolve_account("demo")
    assert account.id == "42"
    assert account.username == "demo"
    assert account.display_name == "Demo"


def test_last_tweets_parses_page():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "tweets": [
                        {
                            "id": "1",
                            "text": "hi",
                            "createdAt": "Tue Dec 10 07:00:30 +0000 2024",
                            "author": {"id": "42", "userName": "demo", "name": "Demo"},
                        }
                    ]
                },
                "has_next_page": True,
                "next_cursor": "tl:abc",
            },
        )

    page = make_provider(handler).last_tweets("demo", None, False)
    assert len(page.tweets) == 1
    assert page.tweets[0].id == "1"
    assert page.has_next is True
    assert page.cursor == "tl:abc"


def test_missing_api_key_raises():
    provider = TwitterApiIoProvider(api_key=None)
    with pytest.raises(TwitterApiIoError):
        provider.resolve_account("demo")


def test_401_raises_clear_error():
    def handler(request):
        return httpx.Response(401, json={"error": 401, "message": "bad key"})

    with pytest.raises(TwitterApiIoError):
        make_provider(handler).resolve_account("demo")
