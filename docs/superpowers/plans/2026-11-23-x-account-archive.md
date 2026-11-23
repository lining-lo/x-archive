# X 账号归档与选题检索站 —— 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抓取指定 X 账号的发帖，本地归档，并提供可检索、可标星、可写备注的本地网页。

**Architecture:** 三个模块 —— 抓取（provider 抽象 + twitterapi.io 实现）、存储（SQLite，upsert 幂等）、
界面（FastAPI 提供 API，Vite + React 单页前端）。刷新为手动触发，做增量抓取直到遇到已入库的 tweet id。

**Tech Stack:** Python 3.12 + FastAPI + SQLite + httpx + pytest；React 18 + Vite + lucide-react。

---

## 文件结构

```
x-archive/
  pyproject.toml                 # pytest 配置（pythonpath=backend）
  requirements.txt               # 后端依赖
  .env.example                   # 环境变量示例
  README.md                      # 运行说明
  backend/
    app/
      __init__.py
      config.py                  # 读取环境变量
      db.py                      # 连接 + 建表
      provider_base.py           # Account / Tweet / TweetPage / Provider 接口
      provider_twitterapi.py     # twitterapi.io 实现 + 解析
      store.py                   # upsert / 查询 / 标星备注
      sync.py                    # 同步流程（增量，遇到已入库即停）
      api.py                     # FastAPI 应用与路由
    tests/
      conftest.py
      fixtures/
        user_info.json
        last_tweets_page.json
      test_provider_parse.py
      test_provider_http.py
      test_store.py
      test_sync.py
      test_api.py
  frontend/
    package.json
    vite.config.js
    index.html
    src/
      main.jsx
      App.jsx
      api.js
      styles.css
      components/
        FilterBar.jsx
        TweetList.jsx
        TweetCard.jsx
```

---

## Task 1: 后端脚手架与健康检查

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/api.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: 写依赖与 pytest 配置**

`requirements.txt`：

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
python-dotenv==1.0.1
pytest==8.3.4
```

`pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["backend"]
testpaths = ["backend/tests"]
```

`backend/app/__init__.py` 与 `backend/tests/__init__.py` 为空文件。

- [ ] **Step 2: 写失败的测试**

`backend/tests/test_api.py`：

```python
from fastapi.testclient import TestClient

from app.api import create_app


def test_health(tmp_path):
    app = create_app(db_path=str(tmp_path / "t.db"))
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_api.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app'` 或 `ImportError: cannot import name 'create_app'`）

- [ ] **Step 4: 写最小实现**

`backend/app/config.py`：

```python
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
```

`backend/app/api.py`：

```python
from fastapi import FastAPI


def create_app(db_path: str | None = None, provider_factory=None) -> FastAPI:
    app = FastAPI(title="X Archive")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml requirements.txt backend
git commit -m "feat: backend scaffold with health endpoint"
```

---

## Task 2: SQLite 连接与建表

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_db.py`：

```python
from app.db import connect, init_db


def test_init_db_creates_core_tables(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"accounts", "tweets", "marks", "sync_log"}.issubset(names)


def test_init_db_is_idempotent(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    init_db(conn)  # must not raise
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_db.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.db'`）

- [ ] **Step 3: 写实现**

`backend/app/db.py`：

```python
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    profile_json TEXT,
    created_at TEXT,
    last_sync_at TEXT
);

CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    text TEXT NOT NULL,
    lang TEXT,
    created_at TEXT NOT NULL,
    is_reply INTEGER NOT NULL DEFAULT 0,
    is_retweet INTEGER NOT NULL DEFAULT 0,
    is_quote INTEGER NOT NULL DEFAULT 0,
    has_media INTEGER NOT NULL DEFAULT 0,
    media_json TEXT,
    url TEXT,
    conversation_id TEXT,
    like_count INTEGER,
    retweet_count INTEGER,
    reply_count INTEGER,
    quote_count INTEGER,
    view_count INTEGER,
    raw_json TEXT,
    inserted_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_account_created
    ON tweets(account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS marks (
    tweet_id TEXT PRIMARY KEY,
    starred INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    mode TEXT,
    started_at TEXT,
    finished_at TEXT,
    new_count INTEGER,
    status TEXT,
    message TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: sqlite schema and connection"
```

---

## Task 3: Provider 数据类型与推文解析

**Files:**
- Create: `backend/app/provider_base.py`
- Create: `backend/app/provider_twitterapi.py`
- Create: `backend/tests/test_provider_parse.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_provider_parse.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_provider_parse.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.provider_twitterapi'`）

- [ ] **Step 3: 写实现**

`backend/app/provider_base.py`：

```python
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
```

`backend/app/provider_twitterapi.py`：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_provider_parse.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/provider_base.py backend/app/provider_twitterapi.py backend/tests/test_provider_parse.py
git commit -m "feat: provider types and tweet parsing"
```

---

## Task 4: twitterapi.io HTTP 客户端

**Files:**
- Modify: `backend/app/provider_twitterapi.py`
- Create: `backend/tests/test_provider_http.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_provider_http.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_provider_http.py -v`
Expected: FAIL（`ImportError: cannot import name 'TwitterApiIoProvider'`）

- [ ] **Step 3: 写实现**

把 `provider_twitterapi.py` 顶部的 import 区块替换为下面这段（新增 `httpx`）：

```python
from datetime import timezone
from email.utils import parsedate_to_datetime

import httpx

from app.provider_base import Account, Tweet, TweetPage
```

在文件末尾追加：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_provider_http.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/provider_twitterapi.py backend/tests/test_provider_http.py
git commit -m "feat: twitterapi.io http client"
```

---

## Task 5: 存储层（upsert / 查询 / 标星备注）

**Files:**
- Create: `backend/app/store.py`
- Create: `backend/tests/test_store.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_store.py`：

```python
from app.db import connect, init_db
from app.provider_base import Account, Tweet
from app.store import (
    list_accounts,
    query_tweets,
    set_mark,
    tweet_exists,
    upsert_account,
    upsert_tweets,
)


def make_tweet(tid="1", text="hello", media=False, reply=False):
    return Tweet(
        id=tid, account_id="42", text=text, created_at="2024-12-10T07:00:30+00:00",
        lang="zh", is_reply=reply, is_retweet=False, is_quote=False,
        has_media=media, media=[{"type": "photo"}] if media else [],
        url=f"https://x.com/demo/status/{tid}", conversation_id=tid,
        like_count=1, retweet_count=0, reply_count=0, quote_count=0, view_count=5,
        raw={"id": tid, "text": text},
    )


def fresh():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_upsert_account_then_list():
    conn = fresh()
    upsert_account(conn, Account(id="42", username="demo", display_name="Demo", raw={}))
    accounts = list_accounts(conn)
    assert len(accounts) == 1
    assert accounts[0]["username"] == "demo"


def test_upsert_tweets_is_idempotent_and_counts_new():
    conn = fresh()
    assert upsert_tweets(conn, [make_tweet("1"), make_tweet("2")]) == 2
    assert upsert_tweets(conn, [make_tweet("2"), make_tweet("3")]) == 1
    assert tweet_exists(conn, "1") is True
    assert tweet_exists(conn, "3") is True
    count = conn.execute("SELECT COUNT(*) AS c FROM tweets").fetchone()["c"]
    assert count == 3


def test_query_filters_keyword_and_media():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1", "苹果"), make_tweet("2", "香蕉", media=True)])
    assert [t["id"] for t in query_tweets(conn, keyword="苹果")] == ["1"]
    assert [t["id"] for t in query_tweets(conn, has_media=True)] == ["2"]


def test_query_excludes_retweets_by_kind():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1")])
    rows = query_tweets(conn, kinds=["original"])
    assert [t["id"] for t in rows] == ["1"]


def test_mark_star_and_note_roundtrip():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("1")])
    set_mark(conn, "1", starred=True, note="选题A")
    row = query_tweets(conn, starred_only=True)[0]
    assert row["starred"] == 1
    assert row["note"] == "选题A"
    set_mark(conn, "1", starred=False)
    assert query_tweets(conn, starred_only=True) == []
    assert query_tweets(conn)[0]["note"] == "选题A"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_store.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.store'`）

- [ ] **Step 3: 写实现**

`backend/app/store.py`：

```python
import json
import sqlite3
from datetime import datetime, timezone

from app.provider_base import Account, Tweet


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tweet_exists(conn: sqlite3.Connection, tweet_id: str) -> bool:
    return conn.execute("SELECT 1 FROM tweets WHERE id = ?", (tweet_id,)).fetchone() is not None


def upsert_account(conn: sqlite3.Connection, account: Account) -> None:
    conn.execute(
        """
        INSERT INTO accounts (id, username, display_name, profile_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            display_name = excluded.display_name,
            profile_json = excluded.profile_json
        """,
        (
            account.id,
            account.username,
            account.display_name,
            json.dumps(account.raw, ensure_ascii=False),
            _now(),
        ),
    )
    conn.commit()


def upsert_tweets(conn: sqlite3.Connection, tweets: list[Tweet]) -> int:
    new_count = 0
    now = _now()
    for t in tweets:
        if not tweet_exists(conn, t.id):
            new_count += 1
        conn.execute(
            """
            INSERT INTO tweets (
                id, account_id, text, lang, created_at, is_reply, is_retweet, is_quote,
                has_media, media_json, url, conversation_id, like_count, retweet_count,
                reply_count, quote_count, view_count, raw_json, inserted_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                text = excluded.text,
                lang = excluded.lang,
                is_reply = excluded.is_reply,
                is_retweet = excluded.is_retweet,
                is_quote = excluded.is_quote,
                has_media = excluded.has_media,
                media_json = excluded.media_json,
                like_count = excluded.like_count,
                retweet_count = excluded.retweet_count,
                reply_count = excluded.reply_count,
                quote_count = excluded.quote_count,
                view_count = excluded.view_count,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """,
            (
                t.id, t.account_id, t.text, t.lang, t.created_at,
                int(t.is_reply), int(t.is_retweet), int(t.is_quote),
                int(t.has_media), json.dumps(t.media, ensure_ascii=False),
                t.url, t.conversation_id, t.like_count, t.retweet_count,
                t.reply_count, t.quote_count, t.view_count,
                json.dumps(t.raw, ensure_ascii=False), now, now,
            ),
        )
    conn.commit()
    return new_count


_KIND_CLAUSES = {
    "original": "(t.is_reply = 0 AND t.is_retweet = 0 AND t.is_quote = 0)",
    "quote": "t.is_quote = 1",
    "reply": "t.is_reply = 1",
    "retweet": "t.is_retweet = 1",
}


def query_tweets(
    conn: sqlite3.Connection,
    account_id: str | None = None,
    keyword: str | None = None,
    since: str | None = None,
    until: str | None = None,
    has_media: bool | None = None,
    kinds: list[str] | None = None,
    starred_only: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    sql = [
        "SELECT t.*, COALESCE(m.starred, 0) AS starred, COALESCE(m.note, '') AS note",
        "FROM tweets t LEFT JOIN marks m ON m.tweet_id = t.id",
        "WHERE 1 = 1",
    ]
    params: list = []
    if account_id:
        sql.append("AND t.account_id = ?")
        params.append(account_id)
    if keyword:
        sql.append("AND t.text LIKE ?")
        params.append(f"%{keyword}%")
    if since:
        sql.append("AND t.created_at >= ?")
        params.append(since)
    if until:
        sql.append("AND t.created_at <= ?")
        params.append(until)
    if has_media is not None:
        sql.append("AND t.has_media = ?")
        params.append(1 if has_media else 0)
    if kinds:
        clauses = [_KIND_CLAUSES[k] for k in kinds if k in _KIND_CLAUSES]
        if clauses:
            sql.append("AND (" + " OR ".join(clauses) + ")")
    if starred_only:
        sql.append("AND COALESCE(m.starred, 0) = 1")
    sql.append("ORDER BY t.created_at DESC LIMIT ? OFFSET ?")
    params += [limit, offset]
    return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def set_mark(
    conn: sqlite3.Connection,
    tweet_id: str,
    starred: bool | None = None,
    note: str | None = None,
) -> None:
    row = conn.execute(
        "SELECT starred, note FROM marks WHERE tweet_id = ?", (tweet_id,)
    ).fetchone()
    cur_starred = row["starred"] if row else 0
    cur_note = row["note"] if row else ""
    new_starred = cur_starred if starred is None else (1 if starred else 0)
    new_note = cur_note if note is None else note
    conn.execute(
        """
        INSERT INTO marks (tweet_id, starred, note, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tweet_id) DO UPDATE SET
            starred = excluded.starred, note = excluded.note, updated_at = excluded.updated_at
        """,
        (tweet_id, new_starred, new_note, _now()),
    )
    conn.commit()


def list_accounts(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute("SELECT * FROM accounts ORDER BY username").fetchall()
    ]
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_store.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/store.py backend/tests/test_store.py
git commit -m "feat: sqlite store with upsert, query and marks"
```

---

## Task 6: 同步流程（增量，遇到已入库即停）

**Files:**
- Create: `backend/app/sync.py`
- Create: `backend/tests/test_sync.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_sync.py`：

```python
from app.db import connect, init_db
from app.provider_base import Account, Tweet, TweetPage
from app.store import query_tweets, upsert_tweets
from app.sync import sync_account
from tests.test_store import make_tweet


class FakeProvider:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def resolve_account(self, username):
        return Account(id="42", username=username, display_name="Demo", raw={})

    def last_tweets(self, username, cursor, include_replies):
        page = self.pages[self.calls]
        self.calls += 1
        return page


def fresh():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_first_sync_paginates_until_no_next():
    conn = fresh()
    provider = FakeProvider([
        TweetPage([make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),
    ])
    result = sync_account(conn, provider, "demo")
    assert result["new_count"] == 3
    assert result["pages"] == 2
    assert len(query_tweets(conn)) == 3


def test_incremental_stops_when_reaching_known_tweet():
    conn = fresh()
    upsert_tweets(conn, [make_tweet("2"), make_tweet("1")])
    provider = FakeProvider([
        TweetPage([make_tweet("4"), make_tweet("3"), make_tweet("2")], True, "c2"),
        TweetPage([make_tweet("1")], False, None),  # must not be fetched
    ])
    result = sync_account(conn, provider, "demo")
    assert result["new_count"] == 2
    assert result["pages"] == 1
    assert provider.calls == 1
    assert len(query_tweets(conn)) == 4
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_sync.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.sync'`）

- [ ] **Step 3: 写实现**

`backend/app/sync.py`：

```python
import sqlite3
from datetime import datetime, timezone

from app.provider_base import Provider, Tweet
from app.store import tweet_exists, upsert_account, upsert_tweets


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter(tweets: list[Tweet], include_retweets: bool, include_replies: bool) -> list[Tweet]:
    kept = []
    for t in tweets:
        if t.is_retweet and not include_retweets:
            continue
        if t.is_reply and not include_replies:
            continue
        kept.append(t)
    return kept


def sync_account(
    conn: sqlite3.Connection,
    provider: Provider,
    username: str,
    include_replies: bool = False,
    include_retweets: bool = False,
    max_pages: int = 200,
) -> dict:
    started = _now()
    account = provider.resolve_account(username)
    upsert_account(conn, account)

    cursor = None
    pages = 0
    new_count = 0
    status = "ok"
    message = ""
    try:
        while pages < max_pages:
            page = provider.last_tweets(account.username, cursor, include_replies)
            pages += 1
            tweets = _filter(page.tweets, include_retweets, include_replies)
            if not tweets:
                if not page.has_next:
                    break
                cursor = page.cursor
                continue
            reached_known = any(tweet_exists(conn, t.id) for t in tweets)
            new_count += upsert_tweets(conn, tweets)
            if reached_known or not page.has_next:
                break
            cursor = page.cursor
        conn.execute(
            "UPDATE accounts SET last_sync_at = ? WHERE id = ?",
            (_now(), account.id),
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - surface any provider error
        status = "error"
        message = str(exc)
        raise
    finally:
        conn.execute(
            """
            INSERT INTO sync_log (account_id, mode, started_at, finished_at, new_count, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (account.id, "incremental", started, _now(), new_count, status, message),
        )
        conn.commit()
    return {"account_id": account.id, "new_count": new_count, "pages": pages, "status": status}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests/test_sync.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/sync.py backend/tests/test_sync.py
git commit -m "feat: incremental sync that stops at known tweets"
```

---

## Task 7: FastAPI 路由

**Files:**
- Modify: `backend/app/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: 写失败的测试**

把 `backend/tests/test_api.py` 替换为：

```python
from fastapi.testclient import TestClient

from app.api import create_app
from app.provider_base import Account, TweetPage
from tests.test_store import make_tweet


class FakeProvider:
    def resolve_account(self, username):
        return Account(id="42", username=username, display_name="Demo", raw={})

    def last_tweets(self, username, cursor, include_replies):
        return TweetPage([make_tweet("1"), make_tweet("2")], False, None)


def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "t.db"), provider_factory=FakeProvider)
    return TestClient(app)


def test_health(tmp_path):
    assert client(tmp_path).get("/api/health").json() == {"status": "ok"}


def test_sync_then_list(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/accounts/demo/sync")
    assert r.status_code == 200
    assert r.json()["new_count"] == 2
    accounts = c.get("/api/accounts").json()
    assert accounts[0]["username"] == "demo"
    tweets = c.get("/api/tweets", params={"account_id": "42"}).json()
    assert len(tweets) == 2


def test_mark_and_starred_filter(tmp_path):
    c = client(tmp_path)
    c.post("/api/accounts/demo/sync")
    r = c.post("/api/tweets/1/mark", json={"starred": True, "note": "选题"})
    assert r.status_code == 200
    starred = c.get("/api/tweets", params={"starred": 1}).json()
    assert [t["id"] for t in starred] == ["1"]
    assert starred[0]["note"] == "选题"


def test_keyword_filter(tmp_path):
    c = client(tmp_path)
    c.post("/api/accounts/demo/sync")
    rows = c.get("/api/tweets", params={"q": "hello"}).json()
    assert len(rows) == 2
    rows = c.get("/api/tweets", params={"q": "nope"}).json()
    assert rows == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest backend/tests/test_api.py -v`
Expected: FAIL（`AttributeError: 'FastAPI' object has no attribute ...` 或 404，说明路由尚未实现）

- [ ] **Step 3: 写实现（替换整个 `backend/app/api.py`）**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest backend/tests -v`
Expected: PASS（全部测试通过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/api.py backend/tests/test_api.py
git commit -m "feat: fastapi routes for sync, list, filter and marks"
```

---

## Task 8: 前端脚手架与 API 封装

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/api.js`

- [ ] **Step 1: 写脚手架文件**

`frontend/package.json`：

```json
{
  "name": "x-archive-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^0.469.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.7"
  }
}
```

`frontend/vite.config.js`：

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
```

`frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>X 选题档案</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/src/main.jsx`：

```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`frontend/src/api.js`：

```js
async function json(resp) {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export const listAccounts = () => fetch("/api/accounts").then(json);

export const syncAccount = (username, includeReplies = false) =>
  fetch(
    `/api/accounts/${encodeURIComponent(username)}/sync?include_replies=${includeReplies}`,
    { method: "POST" }
  ).then(json);

export function listTweets(filters) {
  const params = new URLSearchParams();
  if (filters.accountId) params.set("account_id", filters.accountId);
  if (filters.keyword) params.set("q", filters.keyword);
  if (filters.since) params.set("since", filters.since);
  if (filters.until) params.set("until", filters.until);
  if (filters.hasMedia) params.set("has_media", "1");
  if (filters.starredOnly) params.set("starred", "1");
  for (const k of filters.kinds || []) params.append("kind", k);
  return fetch(`/api/tweets?${params}`).then(json);
}

export const setMark = (tweetId, body) =>
  fetch(`/api/tweets/${tweetId}/mark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(json);
```

- [ ] **Step 2: 安装依赖**

Run: `cd frontend; npm install`
Expected: 生成 `node_modules` 与 `package-lock.json`，无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/index.html frontend/src/main.jsx frontend/src/api.js
git commit -m "feat: frontend scaffold and api client"
```

---

## Task 9: 前端界面（筛选栏、列表、标星备注）

**Files:**
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/FilterBar.jsx`
- Create: `frontend/src/components/TweetList.jsx`
- Create: `frontend/src/components/TweetCard.jsx`

- [ ] **Step 1: 写 `App.jsx`**

```jsx
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { listAccounts, listTweets, syncAccount } from "./api.js";
import FilterBar from "./components/FilterBar.jsx";
import TweetList from "./components/TweetList.jsx";

const EMPTY_FILTERS = {
  accountId: "",
  keyword: "",
  since: "",
  until: "",
  hasMedia: false,
  starredOnly: false,
  kinds: ["original", "quote"],
};

export default function App() {
  const [accounts, setAccounts] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [tweets, setTweets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [newAccount, setNewAccount] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [accts, rows] = await Promise.all([listAccounts(), listTweets(filters)]);
      setAccounts(accts);
      setTweets(rows);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, [filters]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSync(username) {
    if (!username) return;
    setBusy(true);
    setMessage("");
    try {
      const result = await syncAccount(username);
      setMessage(`已同步 ${username}，新增 ${result.new_count} 条`);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAdd() {
    const username = newAccount.trim().replace(/^@/, "");
    if (!username) return;
    await handleSync(username);
    setNewAccount("");
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>X 选题档案</h1>
        <div className="topbar-actions">
          <input
            className="input"
            placeholder="账号名（不含 @）"
            value={newAccount}
            onChange={(e) => setNewAccount(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <button className="btn primary" onClick={handleAdd} disabled={busy}>
            <RefreshCw size={16} className={busy ? "spin" : ""} />
            {busy ? "抓取中" : "抓取 / 刷新"}
          </button>
        </div>
      </header>

      <FilterBar
        accounts={accounts}
        filters={filters}
        onChange={setFilters}
        onReset={() => setFilters(EMPTY_FILTERS)}
        onSync={handleSync}
        busy={busy}
      />

      {message && <p className="notice ok">{message}</p>}
      {error && <p className="notice err">{error}</p>}

      <p className="count">共 {tweets.length} 条</p>
      <TweetList tweets={tweets} onChanged={refresh} />
    </div>
  );
}
```

- [ ] **Step 2: 写 `FilterBar.jsx`**

```jsx
import { Search } from "lucide-react";

const KINDS = [
  ["original", "原创"],
  ["quote", "引用"],
  ["reply", "回复"],
  ["retweet", "转推"],
];

export default function FilterBar({ accounts, filters, onChange, onReset, onSync, busy }) {
  function set(patch) {
    onChange({ ...filters, ...patch });
  }

  function toggleKind(kind) {
    const set1 = new Set(filters.kinds);
    set1.has(kind) ? set1.delete(kind) : set1.add(kind);
    set({ kinds: [...set1] });
  }

  return (
    <div className="filters">
      <select
        className="input"
        value={filters.accountId}
        onChange={(e) => set({ accountId: e.target.value })}
      >
        <option value="">全部账号</option>
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            @{a.username}
          </option>
        ))}
      </select>

      <div className="search">
        <Search size={16} />
        <input
          className="input"
          placeholder="关键词"
          value={filters.keyword}
          onChange={(e) => set({ keyword: e.target.value })}
        />
      </div>

      <input
        type="date"
        className="input"
        value={filters.since}
        onChange={(e) => set({ since: e.target.value })}
      />
      <input
        type="date"
        className="input"
        value={filters.until}
        onChange={(e) => set({ until: e.target.value })}
      />

      <div className="kinds">
        {KINDS.map(([value, label]) => (
          <button
            key={value}
            className={filters.kinds.includes(value) ? "chip on" : "chip"}
            onClick={() => toggleKind(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <label className="check">
        <input
          type="checkbox"
          checked={filters.hasMedia}
          onChange={(e) => set({ hasMedia: e.target.checked })}
        />
        带图
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={filters.starredOnly}
          onChange={(e) => set({ starredOnly: e.target.checked })}
        />
        只看标星
      </label>

      <button className="btn" onClick={onReset}>
        重置
      </button>
      {filters.accountId && (
        <button
          className="btn"
          onClick={() => {
            const acct = accounts.find((a) => a.id === filters.accountId);
            if (acct) onSync(acct.username);
          }}
          disabled={busy}
        >
          刷新该账号
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 写 `TweetList.jsx` 与 `TweetCard.jsx`**

`frontend/src/components/TweetList.jsx`：

```jsx
import TweetCard from "./TweetCard.jsx";

export default function TweetList({ tweets, onChanged }) {
  if (tweets.length === 0) {
    return <p className="empty">暂无数据。先在右上角输入账号名抓取一次。</p>;
  }
  return (
    <div className="list">
      {tweets.map((t) => (
        <TweetCard key={t.id} tweet={t} onChanged={onChanged} />
      ))}
    </div>
  );
}
```

`frontend/src/components/TweetCard.jsx`：

```jsx
import { useState } from "react";
import { Image as ImageIcon, Star } from "lucide-react";
import { setMark } from "../api.js";

function mediaUrls(mediaJson) {
  try {
    return (JSON.parse(mediaJson || "[]") || [])
      .map((m) => m.media_url_https || m.url)
      .filter(Boolean);
  } catch {
    return [];
  }
}

export default function TweetCard({ tweet, onChanged }) {
  const [note, setNote] = useState(tweet.note || "");
  const [editing, setEditing] = useState(false);
  const starred = Boolean(tweet.starred);

  async function toggleStar() {
    await setMark(tweet.id, { starred: !starred });
    onChanged();
  }

  async function saveNote() {
    await setMark(tweet.id, { note });
    setEditing(false);
    onChanged();
  }

  return (
    <article className="card">
      <div className="card-head">
        <span className="date">{new Date(tweet.created_at).toLocaleString("zh-CN")}</span>
        <div className="tags">
          {tweet.is_reply && <span className="tag">回复</span>}
          {tweet.is_quote && <span className="tag">引用</span>}
          {tweet.is_retweet && <span className="tag">转推</span>}
          {tweet.has_media && <ImageIcon size={14} />}
        </div>
        <button className={starred ? "icon starred" : "icon"} onClick={toggleStar} title="标星">
          <Star size={16} fill={starred ? "currentColor" : "none"} />
        </button>
      </div>

      <p className="text">{tweet.text}</p>

      <div className="media">
        {mediaUrls(tweet.media_json).map((u) => (
          <img key={u} src={u} alt="" loading="lazy" />
        ))}
      </div>

      <div className="card-foot">
        <span className="metrics">
          ♥ {tweet.like_count ?? 0} · ⇄ {tweet.retweet_count ?? 0} · 💬 {tweet.reply_count ?? 0}
        </span>
        {tweet.url && (
          <a href={tweet.url} target="_blank" rel="noreferrer">
            原帖
          </a>
        )}
      </div>

      {editing ? (
        <div className="note-edit">
          <input
            className="input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="备注 / 选题想法"
          />
          <button className="btn primary" onClick={saveNote}>
            保存
          </button>
        </div>
      ) : (
        <button className="note" onClick={() => setEditing(true)}>
          {note ? `备注：${note}` : "＋ 添加备注"}
        </button>
      )}
    </article>
  );
}
```

- [ ] **Step 4: 写 `styles.css`**

```css
:root {
  --bg: #f7f7f8;
  --panel: #ffffff;
  --line: #e3e3e6;
  --text: #1a1a1c;
  --muted: #6b6b73;
  --accent: #c2410c;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: system-ui, "Segoe UI", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
}

.app { max-width: 900px; margin: 0 auto; padding: 20px 16px 64px; }

.topbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
}
.topbar h1 { font-size: 20px; margin: 0; }
.topbar-actions { display: flex; gap: 8px; }

.input, .btn, select.input {
  font: inherit; padding: 7px 10px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--panel); color: var(--text);
}
.btn { cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.btn:hover { border-color: #c9c9cf; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn:disabled { opacity: 0.6; cursor: default; }

.filters {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 12px; margin-bottom: 12px;
}
.search { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }
.search .input { width: 140px; }
.kinds { display: inline-flex; gap: 6px; }
.chip {
  font: inherit; padding: 5px 10px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--line); background: var(--panel); color: var(--muted);
}
.chip.on { background: #fff1e9; border-color: var(--accent); color: var(--accent); }
.check { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--muted); }

.notice { padding: 8px 12px; border-radius: 6px; font-size: 14px; }
.notice.ok { background: #ecfdf5; color: #047857; }
.notice.err { background: #fef2f2; color: #b91c1c; }
.count { color: var(--muted); font-size: 13px; }

.list { display: flex; flex-direction: column; gap: 12px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.date { color: var(--muted); font-size: 13px; }
.tags { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--muted); }
.tag { font-size: 12px; border: 1px solid var(--line); border-radius: 4px; padding: 1px 6px; }
.icon { background: none; border: none; cursor: pointer; color: #c9c9cf; display: inline-flex; }
.icon.starred { color: #d97706; }
.text { margin: 0 0 10px; white-space: pre-wrap; line-height: 1.6; }
.media { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.media img { max-width: 160px; max-height: 160px; border-radius: 6px; border: 1px solid var(--line); }
.card-foot { display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: var(--muted); }
.card-foot a { color: var(--accent); }
.note { margin-top: 10px; background: none; border: none; color: var(--muted); cursor: pointer; padding: 0; font: inherit; }
.note-edit { display: flex; gap: 8px; margin-top: 10px; }
.note-edit .input { flex: 1; }
.empty { color: var(--muted); padding: 24px; text-align: center; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 5: 构建验证**

Run: `cd frontend; npm run build`
Expected: 构建成功，输出 `dist/`，无报错

- [ ] **Step 6: 提交**

```bash
git add frontend/src
git commit -m "feat: archive UI with filters, star and notes"
```

---

## Task 10: 运行说明与端到端验收

**Files:**
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: 写配置样例与说明**

`.env.example`：

```
TWITTERAPI_IO_KEY=your_key_here
XARCHIVE_DB=./xarchive.db
```

`README.md`：

```markdown
# X 选题档案

抓取指定 X（推特）账号的发帖，本地归档，支持关键词 / 时间 / 是否带图的检索筛选，
以及标星和备注。手动触发抓取，不做定时任务。

## 准备

1. 到 https://twitterapi.io 注册并获取 API Key。
2. 复制 `.env.example` 为 `.env`，填入 `TWITTERAPI_IO_KEY`。
3. 安装后端依赖：`pip install -r requirements.txt`
4. 安装前端依赖：`cd frontend && npm install`

## 运行

后端（项目根目录）：

    python -m uvicorn app.api:app --app-dir backend --port 8000

前端（另一个终端）：

    cd frontend && npm run dev

打开 http://localhost:5173 ，在右上角输入账号名（不含 @）点「抓取 / 刷新」。

## 测试

    python -m pytest backend/tests -v

## 说明

- 首次抓取会尽量回捞历史；之后每次刷新只拉新增，遇到已入库的帖子即停止。
- 默认不含回复（抓取框里的回复开关暂未接出），不含纯转推。
```

- [ ] **Step 2: 端到端验收**

Run（终端 A）: `python -m uvicorn app.api:app --app-dir backend --port 8000`
Run（终端 B）: `curl.exe http://127.0.0.1:8000/api/health`
Expected: `{"status":"ok"}`

Run: `cd frontend; npm run dev`
打开 http://localhost:5173 ，确认：
1. 页面加载无报错。
2. 未配置 Key 时点「抓取」会看到明确的错误提示（而不是白屏）。
3. 配置 Key 后抓取一个账号，列表出现推文。
4. 关键词 / 时间 / 带图 / 类型筛选生效。
5. 标星后勾选「只看标星」只剩该条；备注可保存并保留。

- [ ] **Step 3: 提交**

```bash
git add .env.example README.md
git commit -m "docs: run instructions and env example"
```

---

## 自查记录

- **Spec 覆盖**：数据源与接口 → Task 3/4；数据模型 → Task 2；全量/增量流程 → Task 6；
  API → Task 7；界面（筛选/标星/备注）→ Task 8/9；配置与运行 → Task 10；错误处理 →
  Task 4 + Task 7。
- **占位符**：无 TODO / TBD；所有代码步骤含完整代码。
- **一致性**：`Tweet`/`Account`/`TweetPage` 字段贯穿 provider → store → api；
  `query_tweets` 的 `kinds` 取值与前端 `KINDS` 一致。
- **已知取舍**：`has_media` 依据 `entities.media` / `extendedEntities.media` / 顶层 `media`
  三者之一判定，属尽力而为；若某账号媒体字段位置不同，抓一次看 `raw_json` 即可调整。
