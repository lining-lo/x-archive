import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    db_path: str
    source: str
    twscrape_db: str
    proxy: str | None


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_key=os.environ.get("TWITTERAPI_IO_KEY"),
        base_url=os.environ.get("TWITTERAPI_BASE_URL", "https://api.twitterapi.io"),
        db_path=os.environ.get("XARCHIVE_DB", "xarchive.db"),
        source=os.environ.get("XARCHIVE_SOURCE", "twitterapi").strip().lower(),
        twscrape_db=os.environ.get("TWSCRAPE_DB", ".twscrape/accounts.db"),
        proxy=os.environ.get("XARCHIVE_PROXY") or None,
    )
