import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { listAccounts, listTweets, syncAccount, syncStatus } from "./api.js";
import FilterBar from "./components/FilterBar.jsx";
import TweetList from "./components/TweetList.jsx";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
  const [includeReplies, setIncludeReplies] = useState(false);

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
    setError("");
    try {
      let job = await syncAccount(username, includeReplies);
      while (job.state === "running") {
        setMessage(`抓取中… 已入库 ${job.new_count} 条（第 ${job.pages} 页）`);
        await sleep(1500);
        job = await syncStatus(username);
      }
      if (job.state === "error") {
        setError(job.error || "抓取失败");
      } else if (job.state === "done") {
        const hint = job.backfill_done ? "" : "（历史还没抓完，再点一次继续）";
        setMessage(
          `已同步 ${username}，新增 ${job.new_count} 条（共 ${job.pages} 页）${hint}`
        );
      } else {
        setMessage(`已同步 ${username}`);
      }
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
          <label className="check">
            <input
              type="checkbox"
              checked={includeReplies}
              onChange={(e) => setIncludeReplies(e.target.checked)}
            />
            含回复
          </label>
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
