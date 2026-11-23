from dataclasses import dataclass
from typing import Protocol


@dataclass
class Account:
    id: str
    username: str
    display_name: str | None
    raw: dict


@dataclass
class Tweet:
    id: str
    account_id: str
    text: str
    created_at: str
    lang: str | None
    is_reply: bool
    is_retweet: bool
    is_quote: bool
    has_media: bool
    media: list
    url: str | None
    conversation_id: str | None
    like_count: int | None
    retweet_count: int | None
    reply_count: int | None
    quote_count: int | None
    view_count: int | None
    raw: dict


@dataclass
class TweetPage:
    tweets: list[Tweet]
    has_next: bool
    cursor: str | None


class Provider(Protocol):
    def resolve_account(self, username: str) -> Account: ...

    def last_tweets(
        self, username: str, cursor: str | None, include_replies: bool
    ) -> TweetPage: ...
