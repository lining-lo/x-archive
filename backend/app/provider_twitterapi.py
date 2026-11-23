from datetime import timezone
from email.utils import parsedate_to_datetime

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
