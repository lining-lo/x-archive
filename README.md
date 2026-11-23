# X 选题档案

抓取指定 X（推特）账号的发帖，本地归档，支持关键词 / 时间 / 是否带图的检索筛选，
以及标星和备注。手动触发抓取，不做定时任务。

## 准备

1. 安装后端依赖：`pip install -r requirements.txt`
2. 安装前端依赖：`cd frontend && npm install`
3. 复制 `.env.example` 为 `.env`，按下面的「数据源」二选一填好。

### 数据源一：twscrape（推荐，免费）

用你自己的 X 账号登录态抓取，不花钱、不需要 API key。需要一个能访问 X 的网络环境。

```bash
# 1) 把 X 账号的 cookie 写进本地账号库（auth_token + ct0，从浏览器 F12 里拿）
pip install twscrape
python -m twscrape --db .twscrape/accounts.db add_cookie main

# 2) 在 .env 里选它，并配好代理（国内直连不了 X）
XARCHIVE_SOURCE=twscrape
TWSCRAPE_DB=.twscrape/accounts.db
XARCHIVE_PROXY=http://127.0.0.1:7890
```

### 数据源二：twitterapi.io（要 key、按量付费）

到 https://twitterapi.io 注册获取 key，然后在 `.env` 里：

```
XARCHIVE_SOURCE=twitterapi
TWITTERAPI_IO_KEY=你的key
```

## 运行

后端（项目根目录）：

    python -m uvicorn app.api:app --app-dir backend --port 8000

前端（另一个终端）：

    cd frontend && npm run dev

打开 http://localhost:5173 ，在右上角输入账号名（不含 @）点「抓取 / 刷新」。

## 测试

    python -m pytest backend/tests -v

## 说明

- 首次抓取是「补历史」：从最新往回翻页，每轮最多 50 页（可用 `pages` 参数调大）。
  一轮没抓完会记住翻页位置，**再点一次会从上次的位置继续**，直到整段历史抓完。
- 历史抓完之后自动切换成「增量」模式：每次只从最新往回拉，遇到已入库的帖子即停止。
- 默认不收纯转推。回复默认也不收，需要时勾选右上角的「含回复」再抓。
- 关键词检索为子串匹配（`LIKE %关键词%`），对中文可直接用。
- 数据库文件默认是项目根目录的 `xarchive.db`，可用环境变量 `XARCHIVE_DB` 改。
