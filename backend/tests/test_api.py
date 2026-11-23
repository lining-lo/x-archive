import time

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


def run_sync(c, username="demo", timeout=5.0):
    assert c.post(f"/api/accounts/{username}/sync").status_code == 200
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = c.get(f"/api/accounts/{username}/sync/status").json()
        if job["state"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("sync did not finish in time")


def test_health(tmp_path):
    assert client(tmp_path).get("/api/health").json() == {"status": "ok"}


def test_sync_status_is_idle_before_any_run(tmp_path):
    assert client(tmp_path).get("/api/accounts/demo/sync/status").json() == {"state": "idle"}


def test_sync_then_list(tmp_path):
    c = client(tmp_path)
    job = run_sync(c)
    assert job["state"] == "done"
    assert job["new_count"] == 2
    assert job["mode"] == "backfill"
    assert job["backfill_done"] is True

    accounts = c.get("/api/accounts").json()
    assert accounts[0]["username"] == "demo"
    assert accounts[0]["backfill_done"] == 1
    tweets = c.get("/api/tweets", params={"account_id": "42"}).json()
    assert len(tweets) == 2


def test_mark_and_starred_filter(tmp_path):
    c = client(tmp_path)
    run_sync(c)
    r = c.post("/api/tweets/1/mark", json={"starred": True, "note": "选题"})
    assert r.status_code == 200
    starred = c.get("/api/tweets", params={"starred": 1}).json()
    assert [t["id"] for t in starred] == ["1"]
    assert starred[0]["note"] == "选题"


def test_keyword_filter(tmp_path):
    c = client(tmp_path)
    run_sync(c)
    rows = c.get("/api/tweets", params={"q": "hello"}).json()
    assert len(rows) == 2
    rows = c.get("/api/tweets", params={"q": "nope"}).json()
    assert rows == []
