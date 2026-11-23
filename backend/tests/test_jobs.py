import time

from app.db import connect, init_db
from app.jobs import SyncJobs
from app.provider_base import Account, TweetPage
from tests.test_store import make_tweet


class FakeProvider:
    def resolve_account(self, username):
        return Account(id="42", username=username, display_name="Demo", raw={})

    def last_tweets(self, username, cursor, include_replies):
        return TweetPage([make_tweet("1"), make_tweet("2")], False, None)


def wait_done(jobs, key, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.status(key)
        if job and job["state"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish in time")


def make_db(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(connect(db))
    return db


def test_job_runs_to_completion(tmp_path):
    jobs = SyncJobs(make_db(tmp_path), FakeProvider)
    started = jobs.start("demo", "demo")
    assert started["state"] == "running"
    job = wait_done(jobs, "demo")
    assert job["state"] == "done"
    assert job["new_count"] == 2
    assert job["mode"] == "backfill"
    assert job["backfill_done"] is True
    assert job["finished_at"] is not None


def test_job_reports_provider_error(tmp_path):
    class Boom:
        def resolve_account(self, username):
            raise RuntimeError("boom")

    jobs = SyncJobs(make_db(tmp_path), Boom)
    jobs.start("x", "x")
    job = wait_done(jobs, "x")
    assert job["state"] == "error"
    assert "boom" in job["error"]


def test_start_while_running_returns_same_job(tmp_path):
    class Slow(FakeProvider):
        def last_tweets(self, username, cursor, include_replies):
            time.sleep(0.3)
            return super().last_tweets(username, cursor, include_replies)

    jobs = SyncJobs(make_db(tmp_path), Slow)
    first = jobs.start("demo", "demo")
    second = jobs.start("demo", "demo")
    assert first["state"] == "running"
    assert second["started_at"] == first["started_at"]
    wait_done(jobs, "demo")
