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
