# X 选题档案

抓取指定 X（推特）账号的发帖，本地归档，支持关键词 / 时间 / 是否带图的检索筛选，
以及标星和备注。手动触发抓取，不做定时任务。

## 准备

1. 到 https://twitterapi.io 注册并获取 API Key。
2. 复制 `.env.example` 为 `.env`，填入 `TWITTERAPI_IO_KEY`。
3. 安装后端依赖：`pip install -r requirements.txt`
4. 安装前端依赖：`cd frontend && npm install`

## 运行

后端（项目根目录）：

    python -m uvicorn app.api:app --app-dir backend --port 8000

前端（另一个终端）：

    cd frontend && npm run dev

打开 http://localhost:5173 ，在右上角输入账号名（不含 @）点「抓取 / 刷新」。

## 测试

    python -m pytest backend/tests -v

## 说明

- 首次抓取会从最新往回翻页，尽量回捞历史；之后每次刷新只拉新增，遇到已入库的帖子即停止。
- 默认不收纯转推。回复默认也不收，需要时勾选右上角的「含回复」再抓。
- 关键词检索为子串匹配（`LIKE %关键词%`），对中文可直接用。
- 数据库文件默认是项目根目录的 `xarchive.db`，可用环境变量 `XARCHIVE_DB` 改。
