"""twscrape-backed provider.

twscrape logs in with your own X account (here: cookies) and calls X's internal
GraphQL endpoints. No paid API key involved.

The timeline is streamed: twscrape hands tweets newest-first and handles
rate-limit driven account switching itself. Because the stream cannot be seeked
by a cursor, `last_tweets` continues an in-memory stream for the lifetime of one
provider instance and reports `cursor=None`. Use an uncapped page budget for a
single backfill run so the whole history is walked in one pass.
"""

import asyncio
import threading

from app.provider_base import Account, Tweet, TweetPage


class TwscrapeError(Exception):
    pass


class _LoopRunner:
    """Runs twscrape coroutines on one background event loop."""

    _instance: "_LoopRunner | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "_LoopRunner":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(
            target=self._main, name="twscrape-loop", daemon=True
        ).start()

    def _main(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


def _media_list(media) -> list[dict]:
    items: list[dict] = []
    if not media:
        return items
    for photo in getattr(media, "photos", None) or []:
        url = getattr(photo, "url", None)
        items.append({"type": "photo", "url": url, "media_url_https": url})
    for video in getattr(media, "videos", None) or []:
        url = getattr(video, "thumbnailUrl", None)
        items.append({"type": "video", "url": url, "media_url_https": url})
    for anim in getattr(media, "animated", None) or []:
        url = getattr(anim, "thumbnailUrl", None)
        items.append({"type": "animated_gif", "url": url, "media_url_https": url})
    return items


def parse_twscrape_tweet(tw) -> Tweet:
    media = _media_list(getattr(tw, "media", None))
    user = getattr(tw, "user", None)
    created = getattr(tw, "date", None)
    conversation = (
        getattr(tw, "conversationIdStr", None)
        or getattr(tw, "conversationId", None)
    )
    return Tweet(
        id=str(getattr(tw, "id_str", None) or getattr(tw, "id")),
        account_id=str(getattr(user, "id_str", None) or getattr(user, "id", "")),
        text=getattr(tw, "rawContent", None) or "",
        created_at=created.isoformat() if created else "",
        lang=getattr(tw, "lang", None) or None,
        is_reply=getattr(tw, "inReplyToTweetId", None) is not None,
        is_retweet=getattr(tw, "retweetedTweet", None) is not None,
        is_quote=getattr(tw, "quotedTweet", None) is not None,
        has_media=bool(media),
        media=media,
        url=getattr(tw, "url", None),
        conversation_id=str(conversation) if conversation is not None else None,
        like_count=getattr(tw, "likeCount", None),
        retweet_count=getattr(tw, "retweetCount", None),
        reply_count=getattr(tw, "replyCount", None),
        quote_count=getattr(tw, "quoteCount", None),
        view_count=getattr(tw, "viewCount", None),
        raw={"id": str(getattr(tw, "id_str", None) or getattr(tw, "id")), "source": "twscrape"},
    )


def parse_twscrape_user(user) -> Account:
    return Account(
        id=str(getattr(user, "id_str", None) or getattr(user, "id", "")),
        username=getattr(user, "username", "") or "",
        display_name=getattr(user, "displayname", None),
        raw={
            "id": str(getattr(user, "id_str", None) or getattr(user, "id", "")),
            "username": getattr(user, "username", ""),
            "followers": getattr(user, "followersCount", None),
        },
    )


class TwscrapeProvider:
    def __init__(
        self,
        db_path: str,
        proxy: str | None = None,
        page_size: int = 100,
        api=None,
    ) -> None:
        self._db_path = db_path
        self._proxy = proxy
        self._page_size = page_size
        self._api = api
        self._users: dict[str, str] = {}
        self._streams: dict[tuple[str, bool], object] = {}

    def _get_api(self):
        if self._api is None:
            from twscrape import API

            self._api = API(self._db_path, proxy=self._proxy)
        return self._api

    def resolve_account(self, username: str) -> Account:
        user = _LoopRunner.get().run(self._get_api().user_by_login(username))
        if user is None:
            raise TwscrapeError(f"找不到 X 账号 @{username}")
        account = parse_twscrape_user(user)
        self._users[username.lower()] = account.id
        return account

    async def _next_page(self, username: str, include_replies: bool) -> TweetPage:
        key = (username.lower(), include_replies)
        gen = self._streams.get(key)
        if gen is None:
            uid = self._users.get(username.lower())
            if uid is None:
                user = await self._get_api().user_by_login(username)
                if user is None:
                    raise TwscrapeError(f"找不到 X 账号 @{username}")
                uid = str(getattr(user, "id_str", None) or getattr(user, "id", ""))
                self._users[username.lower()] = uid
            api = self._get_api()
            gen = (
                api.user_tweets_and_replies(int(uid))
                if include_replies
                else api.user_tweets(int(uid))
            )
            self._streams[key] = gen

        tweets: list[Tweet] = []
        exhausted = False
        try:
            while len(tweets) < self._page_size:
                tw = await gen.__anext__()
                tweets.append(parse_twscrape_tweet(tw))
        except StopAsyncIteration:
            exhausted = True

        if exhausted:
            self._streams.pop(key, None)
        return TweetPage(tweets=tweets, has_next=not exhausted, cursor=None)

    def last_tweets(
        self, username: str, cursor: str | None, include_replies: bool
    ) -> TweetPage:
        return _LoopRunner.get().run(self._next_page(username, include_replies))
