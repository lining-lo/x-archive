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
    const next = new Set(filters.kinds);
    if (next.has(kind)) {
      next.delete(kind);
    } else {
      next.add(kind);
    }
    set({ kinds: [...next] });
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
