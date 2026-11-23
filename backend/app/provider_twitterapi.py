from datetime import timezone
from email.utils import parsedate_to_datetime

import httpx

from app.provider_base import Account, Tweet, TweetPage


def parse_created_at(value: str | None) -> str | None:
    if not value:
        return None
    return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()


def extract_media(raw: dict) -> list:
    entities = raw.get("entities") or {}
    extended = raw.get("extendedEntities") or raw.get("extended_entities") or {}
    return raw.get("media") or entities.get("media") or extended.get("media") or []


def parse_tweet(raw: dict) -> Tweet:
    media = extract_media(raw)
    author = raw.get("author") or {}
    return Tweet(
        id=str(raw["id"]),
        account_id=str(author.get("id") or ""),
        text=raw.get("text") or "",
        created_at=parse_created_at(raw.get("createdAt")) or "",
        lang=raw.get("lang") or None,
        is_reply=bool(raw.get("isReply")),
        is_retweet=bool(raw.get("isRetweet")),
        is_quote=bool(raw.get("isQuote")),
        has_media=bool(media),
        media=media,
        url=raw.get("url"),
        conversation_id=raw.get("conversationId") or None,
        like_count=raw.get("likeCount"),
        retweet_count=raw.get("retweetCount"),
        reply_count=raw.get("replyCount"),
        quote_count=raw.get("quoteCount"),
        view_count=raw.get("viewCount"),
        raw=raw,
    )


class TwitterApiIoError(Exception):
    pass


class TwitterApiIoProvider:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.twitterapi.io",
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)

    def _get(self, path: str, params: dict) -> dict:
        if not self.api_key:
            raise TwitterApiIoError("缺少 TWITTERAPI_IO_KEY，请在 .env 中配置")
        resp = self._client.get(
            self.base_url + path,
            params=params,
            headers={"X-API-Key": self.api_key},
        )
        if resp.status_code == 401:
            raise TwitterApiIoError("API key 无效 (401)")
        if resp.status_code == 429:
            raise TwitterApiIoError("触发限速 (429)，请稍后再试")
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            raise TwitterApiIoError(data.get("msg") or "接口返回错误")
        return data

    def resolve_account(self, username: str) -> Account:
        data = self._get("/twitter/user/info", {"userName": username})
        user = data.get("data") or {}
        return Account(
            id=str(user.get("id") or ""),
            username=user.get("userName") or username,
            display_name=user.get("name"),
            raw=user,
        )

    def last_tweets(
        self, username: str, cursor: str | None, include_replies: bool
    ) -> TweetPage:
        params = {
            "userName": username,
            "includeReplies": "true" if include_replies else "false",
        }
        if cursor:
            params["cursor"] = cursor
        data = self._get("/twitter/user/last_tweets", params)
        tweets = [
            parse_tweet(t)
            for t in (data.get("data") or {}).get("tweets") or []
        ]
        return TweetPage(
            tweets=tweets,
            has_next=bool(data.get("has_next_page")),
            cursor=data.get("next_cursor") or None,
        )
