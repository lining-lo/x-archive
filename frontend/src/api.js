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

export const syncStatus = (username) =>
  fetch(`/api/accounts/${encodeURIComponent(username)}/sync/status`).then(json);

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
