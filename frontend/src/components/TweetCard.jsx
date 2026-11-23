import { useState } from "react";
import { Heart, Image as ImageIcon, MessageCircle, Repeat2, Star } from "lucide-react";
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
          <span className="metric">
            <Heart size={13} />
            {tweet.like_count ?? 0}
          </span>
          <span className="metric">
            <Repeat2 size={13} />
            {tweet.retweet_count ?? 0}
          </span>
          <span className="metric">
            <MessageCircle size={13} />
            {tweet.reply_count ?? 0}
          </span>
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
