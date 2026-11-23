# X 账号归档与选题检索站 — 设计文档

- 日期：2026-11-23
- 状态：已确认，待实现
- 用途：个人选题（单用户、本地运行、非商用）

## 1. 背景与目标

抓取指定 X（推特）账号的发帖内容，本地归档，提供关键词 / 时间 / 是否带图的检索筛选，
支持标星与备注，服务于个人选题。

### 目标

- 抓取一个（偶尔几个）X 账号的发帖，尽量覆盖全量历史，之后保证增量不再漏。
- 本地存储，可离线检索。
- 网页界面：筛选 + 全文搜索 + 标星 + 备注。
- 按需手动触发刷新，不做定时任务。

### 非目标

- 不做多用户 / 登录体系。
- 不做实时监控与推送提醒。
- 不做 AI 摘要 / 自动打标签（后续可扩展，当前不实现）。
- 不做公网部署。

## 2. 数据源

选用 **twitterapi.io**。按量计费，无月费、无最低消费，读推文约 $0.15 / 1000 条
（$0.00015 / 条），非常契合"偶尔手动拉一次"的用法。

用到的接口：

- `GET /twitter/user/info` —— 由 userName 解析出 userId 与资料。
- `GET /twitter/user/last_tweets` —— 按 userName / userId 获取推文，游标分页，
  每页最多 20 条，newest first，可选 `includeReplies`。用于**增量抓取**。
- `GET /twitter/user/timeline` —— 按 userId 获取时间线，顺序与 X 个人页一致。备用。
- Advanced Search（`from:账号 since: until:` 时间窗）—— 用于**全量回填**。

成本量级：2 万条历史回填约 $3；之后每次刷新只计新帖，可忽略。

**Provider 抽象**：抓取层定义统一接口，twitterapi.io 只是其中一种实现。
将来换 Apify / 官方 API / 自建抓取时，只需新增一个实现，不动其余代码。

## 3. 架构

三个模块：抓取模块、存储（SQLite）、界面（本地网页 + 后端 API）。

```
网页「刷新」按钮
      │
      ▼
后端 API ──► 抓取模块 ──► twitterapi.io
      │            │
      │            ▼
      └──► SQLite（upsert）──► 列表 / 检索 API ──► 网页
```

## 4. 数据模型（SQLite）

- `accounts`：`id`(userId, PK), `username`, `display_name`, `profile_json`,
  `created_at`, `last_sync_at`
- `tweets`：`id`(tweet id, PK), `account_id`(FK), `text`, `lang`, `created_at`,
  `is_reply`, `is_retweet`, `is_quote`, `has_media`, `media_json`, `url`,
  `conversation_id`, `like_count`, `retweet_count`, `reply_count`, `quote_count`,
  `view_count`, `raw_json`, `inserted_at`, `updated_at`
- `marks`：`tweet_id`(PK), `starred`(bool), `note`(text), `updated_at`
- `sync_log`：`id`, `account_id`, `mode`, `started_at`, `finished_at`,
  `new_count`, `status`, `message`

唯一键为 tweet id，所有写入走 upsert，保证重复抓取幂等。

关键词检索：直接用 SQL `LIKE %关键词%` 子串匹配。原因是数据量小（单账号量级）、
且帖子多为中文，LIKE 子串匹配对中文天然可用，比 FTS5 更简单可靠。若将来数据量
明显变大，再考虑引入全文索引。

## 5. 抓取流程

### 首次全量回填

1. 由 userName 解析 userId，写入 `accounts`。
2. 按时间窗（逐月，必要时自适应拆分窗口）用 Advanced Search 从最新往回捞，
   直到覆盖到账号最早可见推文或达到安全上限（如页数上限 / 时间下限）。
3. upsert 入库。

> 边界：X 上极早期或未被检索收录的少数帖子可能拿不到，这是数据源自身的限制；
> 但一旦建过档，之后的增量就不会再漏。

### 增量刷新（网页「刷新」按钮手动触发）

1. 用 `last_tweets` 从最新往回翻页。
2. 翻到已入库的 tweet id 即停止（先更新已存在帖的互动数据）。
3. upsert 新帖，写 `sync_log`，返回新增条数。

### 断点续抓

全量回填按「每轮最多 N 页」分次执行，翻页游标持久化在 `accounts.backfill_cursor`。
一轮没抓完就在下次点击时从保存的游标继续，直到 `backfill_done` 置位；此后自动切换
为上面的增量模式。这样即使单轮中断（超时、限速、关页面），历史也不会卡在 4000 条上限。

## 6. 界面

- 顶部：账号切换、「刷新」按钮、同步状态（上次同步时间 / 本次新增 N 条）。
- 筛选栏：关键词（子串匹配）、时间范围、是否带图、内容类型（原创 / 引用 / 回复 / 转推）。
- 列表：按时间倒序，展示正文、时间、媒体缩略图、互动数、回复/引用标记。
- 每条操作：标星（图标按钮）、备注（可就地编辑）。
- 视图：默认全部；可切换"只看标星"。

## 7. 配置与运行

- 密钥：`.env` 中的 `TWITTERAPI_IO_KEY`（不入库、不入版本控制）。
- 运行：本地启动后端服务，浏览器打开本地地址使用。
- 数据：SQLite 文件保存在本地项目目录下。

## 8. 错误处理

- 密钥缺失 / 401 / 额度不足 / 429 限速 → 返回明确错误，前端可见。
- 抓取失败不污染已有数据；部分成功则保留成功部分并在 `sync_log` 记为部分完成。
- 每账号记录 `last_sync_at`，便于判断"同步到哪了"。

## 9. 技术栈

- 后端：Python + FastAPI + SQLite + httpx。
- 前端：轻量单页应用（Vite + React），本地开发服务器运行。
- 测试：针对抓取解析与 upsert 幂等性的单元测试，用假 provider / 固定 JSON fixture，
  不依赖真实 API 计费。

## 10. 已决事项

- 内容口径：默认收**原创推文 + 引用推文**，排除**纯转推**，**回复默认不收**（保留开关）。
- 触发方式：**手动**，不做定时任务。
- 多账号：支持偶发新增，界面可切换。
