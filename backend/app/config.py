import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    db_path: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_key=os.environ.get("TWITTERAPI_IO_KEY"),
        base_url=os.environ.get("TWITTERAPI_BASE_URL", "https://api.twitterapi.io"),
        db_path=os.environ.get("XARCHIVE_DB", "xarchive.db"),
    )
