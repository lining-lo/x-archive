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
    try {
      const result = await syncAccount(username, includeReplies);
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
