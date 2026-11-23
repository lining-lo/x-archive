import threading

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.config import load_settings
from app.db import connect, init_db
from app.provider_twitterapi import TwitterApiIoError, TwitterApiIoProvider
from app.store import list_accounts, query_tweets, set_mark
from app.sync import sync_account


class MarkBody(BaseModel):
    starred: bool | None = None
    note: str | None = None


def create_app(db_path: str | None = None, provider_factory=None) -> FastAPI:
    settings = load_settings()
    conn = connect(db_path or settings.db_path)
    init_db(conn)
    lock = threading.Lock()

    if provider_factory is None:
        provider_factory = lambda: TwitterApiIoProvider(  # noqa: E731
            settings.api_key, settings.base_url
        )

    app = FastAPI(title="X Archive")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/accounts")
    def accounts() -> list[dict]:
        return list_accounts(conn)

    @app.post("/api/accounts/{username}/sync")
    def sync(username: str, include_replies: bool = False) -> dict:
        provider = provider_factory()
        try:
            with lock:
                return sync_account(conn, provider, username, include_replies=include_replies)
        except TwitterApiIoError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/tweets")
    def tweets(
        account_id: str | None = None,
        q: str | None = None,
        since: str | None = None,
        until: str | None = None,
        has_media: int | None = None,
        kind: list[str] | None = Query(default=None),
        starred: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        return query_tweets(
            conn,
            account_id=account_id,
            keyword=q,
            since=since,
            until=until,
            has_media=None if has_media is None else bool(has_media),
            kinds=kind,
            starred_only=bool(starred),
            limit=limit,
            offset=offset,
        )

    @app.post("/api/tweets/{tweet_id}/mark")
    def mark(tweet_id: str, body: MarkBody) -> dict:
        with lock:
            set_mark(conn, tweet_id, starred=body.starred, note=body.note)
        return {"status": "ok"}

    return app


app = create_app()
