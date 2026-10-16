# 微信读书官方 Agent API 数据字典

本项目的微信读书数据全部来自**官方** Agent API Gateway，不再抓取网页接口、不再需要 Cookie。

- 官方入口（获取 API Key）：<https://weread.qq.com/r/weread-skills>
- 官方示例仓库：<https://github.com/Tencent/WeChatReading>
- 官方 Skill 包：<https://cdn.weread.qq.com/skills/weread-skills.zip>
- 统一网关：`POST https://i.weread.qq.com/api/agent/gateway`
- 鉴权：请求头 `Authorization: Bearer wrk-xxxx`
- 请求体：`{"api_name": "/xxx/yyy", ...业务参数平铺..., "skill_version": "1.0.5"}`

> 服务端会随接口调整下发 `upgrade_info`。收到时客户端会抛出明确提示，需要更新
> `WEREAD_SKILL_VERSION` / 重新下载官方 Skill 包后再同步。

## 可同步的数据

### 1. 书架（`/shelf/sync`）

| 数据 | 字段 | 去向 |
|---|---|---|
| 电子书条目 | `books[]` | 书架库 |
| 有声书/专辑 | `albums[]`（`albumInfo.*`、`albumInfoExtra.*`） | 书架库（`kind=album`） |
| 文章收藏入口 | `mp`（非空表示有 1 个条目，不含内容） | 仅计入数量 |
| 书单 | `archive[].name` / `archive[].bookIds` | 暂未同步 |
| 书籍 ID / 书名 / 作者 / 封面 / 分类 | `bookId` `title` `author` `cover` `category` | 书架库 |
| 最近阅读时间 | `readUpdateTime` | 书架库 · 最后阅读时间 |
| 是否读完 | `finishReading`（1=读完） | 书架库 · 状态 |
| 置顶 / 私密 | `isTop` `secret` | 暂未同步 |

> 数量口径：`books.length + albums.length + (mp 非空 ? 1 : 0)`。

### 2. 书籍详情（`/book/info`）

译者、简介、出版社、出版时间、ISBN、总字数、评分（百分制）、评分人数、`readerLink`。

### 3. 阅读进度（`/book/getprogress`）

| 字段 | 说明 | 去向 |
|---|---|---|
| `book.progress` | 0–100 整数，**1 表示 1%** | 书架库 · 阅读进度（转换为 0–1） |
| `book.recordReadingTime` | **累计阅读时长，秒** | 书架库 · 阅读时长（格式化为「X小时Y分钟」） |
| `book.updateTime` | 最后阅读时间 | 书架库 · 最后阅读时间 |
| `book.finishTime` | 读完时间（仅 progress=100 时存在） | 用于判定「已读」 |

### 4. 笔记（`/user/notebooks` + `/book/bookmarklist` + `/review/list/mine`）

| 数据 | 字段 | 去向 |
|---|---|---|
| 有笔记的书 + 各口径计数 | `reviewCount` `noteCount` `bookmarkCount` | 仅用于筛选与排序 |
| 划线原文 | `/book/bookmarklist` → `updated[].markText` | 划线库 · 内容 |
| 划线样式 | `colorStyle` | 划线库 · 样式 |
| 划线所在章节 | `chapterUid` + `chapters[].title` | 划线库 · 章节 |
| 划线时间 | `createTime` | 划线库 · 创建时间 |
| 想法 / 章节点评 | `/review/list/mine` → `reviews[].review.content` | 笔记库 · 内容（类型=想法） |
| 想法对应的划线原文 | `reviews[].review.abstract` | 暂未写入 Notion |
| 整本书评 | 无 `chapterUid` 的个人点评 | 笔记库 · 内容（类型=书评） |
| 我的评分 | `reviews[].review.star` | 暂未写入 Notion |

> **笔记数口径** = `reviewCount + noteCount + bookmarkCount`。
> `noteCount` 是划线数，不是总笔记数。
> **书签**（bookmark）只能拿到数量，官方不提供书签内容导出。

### 5. 阅读统计（`/readdata/detail`）

`mode` 取 `weekly` / `monthly` / `annually` / `overall`，`baseTime` 可回溯历史周期。

- `totalReadTime` / `readTimes` / `dailyReadTimes`：阅读与收听时长，**单位统一为秒**
- **实测口径**（与文档描述有出入，以实测为准）：`readTimes` 的分桶精度随 `mode` 变化
  - `overall` → 按**年**分桶，键为 `YYYY` 时间戳
  - `annually` → 按**月**分桶，键为 `YYYY-MM` 时间戳
  - `monthly` → 按**天**分桶，键为 `YYYY-MM-DD` 时间戳
- `dailyReadTimes` 文档里说有，实测各年份均返回空，**不可依赖**
- `readDays`：有效阅读天数（单日满 1 分钟）
- `dayAverageReadTime`：自然日日均（不是阅读日日均）
- `readLongest[]`：读得最多的书/有声内容排行（含 `readTime`）
- `readStat[]`：读过 / 读完 / 阅读 / 笔记 等摘要
- `preferCategory` / `preferAuthor` / `preferTime`：分类、作者、时段偏好

> 该接口只支持固定自然周期，不支持任意起止日期；跨区间需按年/月组合。
> 目前通过 `uv run python main.py stats` 查看，尚未落库到 Notion。

## 书架库字段映射

| 微信读书 | Notion 属性 | 备注 |
|---|---|---|
| `title` | 书名 | title |
| `bookId` / `albumId` | 书籍ID | rich_text |
| `author` / `authorName` | 作者 | relation（自动建页） |
| `category` | 分类 | relation（自动建页） |
| `cover` | 封面 | external file |
| `isbn` | ISBN | |
| `publisher` | 出版社 | |
| `newRating/20` | — | 模板中无评分属性 |
| `progress/100` | 阅读进度 | number(percent) |
| `recordReadingTime` | 阅读时长 | text，「X小时Y分钟」 |
| `updateTime` | 最后阅读时间 | date |
| `finishReading` / `progress` | 状态 | 想读 / 在读 / 已读 |
| `updateTime` 年份 | 年份标签 | select，如「2026年」 |

## 同步语义：全量对账，不丢失

`sync` 不是「只追加」，而是对每个库做一次完整的增删改对账：

| 上游状态 | Notion 动作 |
|---|---|
| 新增 | 创建页面 |
| 内容/章节变化 | 更新同一页面 |
| 已删除 | 归档页面（`archived = true`，可在回收站恢复） |
| 无变化 | 跳过，不产生写请求 |

去重与更新依赖「笔记ID」属性（`bookmark_<bookmarkId>` / `review_<reviewId>`），
`setup-notion` 会自动在 **笔记** 与 **划线** 两个库里补齐该属性。
对于更早版本创建、没有 笔记ID 的历史记录，会按 (内容, 章节) 自动认领后补写 ID，
因此升级后不会产生重复行。

### 防误删设计

删除对账只在上游确认抓取成功时才执行：

- 划线抓取失败 → 跳过「划线」的删除对账（想法照常处理）
- 想法/点评抓取失败 → 跳过「笔记」的删除对账
- `/user/notebooks` 分页中途失败会直接抛出，整次同步中止，不会进入对账
- `/user/notebooks` 拿到的条数与服务端声明的 `totalBookCount` 不一致（索引不完整）时，
  跳过「书架上有、笔记本里没有」这类书籍的清理对账（这类书最容易因为索引缺失被误判成已删除）

也就是说，任何一次网络抖动都不会被误判成「上游已删除」。

### 内容完整性

- 笔记正文超过 Notion 标题上限（1900 字）时，完整内容按 ≤1900 字分片写入页面正文，不截断丢弃
- 同一长文本重复同步不会重复写正文；内容变短后正文会同步清空
- 只有当页面正文完全由本工具写入的分片组成时才重写；页面里如果有用户自己写的内容，跳过正文写入而不覆盖
- 书架上下架（有笔记但已不在书架）的书仍会被同步，避免笔记丢失
- 书签（bookmark）官方只提供数量，无法导出内容

## 阅读记录

`setup-notion` 会新建「阅读记录」数据库：

| 属性 | 类型 | 说明 |
|---|---|---|
| 日期 | title | `YYYY-MM-DD`；只有月粒度时 `YYYY-MM`；年汇总为 `YYYY` |
| 阅读时长 | number | 秒 |
| 时长 | text | 「X小时Y分钟」 |
| 年 / 月 | number | 便于分组与汇总 |
| 粒度 | select | `日` / `月` / `年`，标明该行是日明细、月汇总还是年汇总 |

历史抓取方式（`OfficialWeReadProvider.reading_history`）：

1. `overall` → 年粒度（`YYYY`），并据此推断最早阅读年份
2. 从最早年份到今年逐年调 `annually` → 月粒度（`YYYY-MM`）
3. 只对「月时长 > 0」的月份调 `monthly` → 日粒度（`YYYY-MM-DD`），避免空跑请求

单次失败只告警不中断（`_readdata_or_empty`），一次取不全不会污染已有数据。
日/月/年三类行键格式不同，互不重复计数。

同步是幂等的：`阅读时长` 与 `粒度` 都没变时直接跳过，不产生写请求。

「阅读记录」库里预置三个图表视图，可直接看趋势：

| 视图 | 类型 | 过滤 |
|---|---|---|
| 年度阅读时长 | 柱状图 | `粒度 = 年` |
| 月度阅读时长 | 折线图 | `粒度 = 月` |
| 每日阅读时长 | 折线图 | `粒度 = 日` |

三个视图的 x 轴都是 `日期`，按 `阅读时长` 求和。`日期` 是等宽的 `YYYY` / `YYYY-MM` /
`YYYY-MM-DD`，字典序即时间序，所以升序排列就是时间正序。

## 尚未同步、可后续补充

- 想法对应的划线原文（`abstract`）、我的评分（`star`）有数据，但模板里还没有对应属性
- 私密标记（`secret` / `isPrivate`）、置顶（`isTop`）未落库
- 书的简介、总字数、出版时间、译者：`BookInfo` 已就绪，模板加属性即可写入
- 公众号/文章收藏（`mp`）只计入数量，官方未提供内容接口
- 书单（`archive[]`）未同步
