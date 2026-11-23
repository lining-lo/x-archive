import threading

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.config import load_settings
from app.db import connect, init_db
from app.jobs import SyncJobs
from app.provider_twitterapi import TwitterApiIoProvider
from app.provider_twscrape import TwscrapeProvider
from app.store import list_accounts, query_tweets, set_mark


class MarkBody(BaseModel):
    starred: bool | None = None
    note: str | None = None


def create_app(db_path: str | None = None, provider_factory=None) -> FastAPI:
    settings = load_settings()
    resolved_db = db_path or settings.db_path
    conn = connect(resolved_db)
    init_db(conn)
    lock = threading.Lock()

    if provider_factory is None:
        if settings.source == "twscrape":
            provider_factory = lambda: TwscrapeProvider(  # noqa: E731
                settings.twscrape_db, proxy=settings.proxy
            )
        else:
            provider_factory = lambda: TwitterApiIoProvider(  # noqa: E731
                settings.api_key, settings.base_url
            )

    # twscrape streams a timeline that cannot be resumed by cursor, so its
    # backfill runs uncapped. The paid API is cheaper to keep in bounded chunks.
    jobs = SyncJobs(
        resolved_db,
        provider_factory,
        max_pages=None if settings.source == "twscrape" else 50,
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
        return jobs.start(username.lower(), username, include_replies)

    @app.get("/api/accounts/{username}/sync/status")
    def sync_status(username: str) -> dict:
        job = jobs.status(username.lower())
        return job if job is not None else {"state": "idle"}

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
