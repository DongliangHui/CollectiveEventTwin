# 数据获取与爬虫技术储备

Date: 2026-05-08

Status: 技术储备，不进入当前 P0 生产运行时依赖

## 1. 结论

本轮调研的核心结论：

```text
爬虫/公开页采集可以作为数据获取体系的一部分，
但不能作为抖音、快手、小红书、头条、B站等高传播平台的主生产数据管道。
```

更合适的路线是组合式数据获取：

```text
公开 Web / 分享链接采集
+ 热榜 / RSS / 搜索聚合
+ 第三方合规数据服务
+ 客户授权导出
+ 人工/半自动证据补采
+ 少量隔离 POC 的非官方采集器
-> raw_records
-> SourcePolicyService
-> RawRecordNormalizer
-> PlatformSignalAnalyst Agents
-> Signal / Evidence / RiskFactor / Mainline
```

技术上，GitHub 上存在能抓取抖音、快手、小红书、B站、微博、贴吧、知乎、今日头条等内容的项目；但多数项目依赖登录态、Cookie、代理、签名参数、浏览器自动化或非官方接口。它们适合用于技术边界验证、字段可得性评估、平台语境分析样本建设，不适合直接作为生产承诺。

## 2. 本项目边界

CollectiveEventTwin 当前 P0 明确允许的来源类型：

- `public_web`
- `official_api`
- `authorized_export`
- `manual_upload`
- `third_party_contract`
- `test_fixture` 仅限测试或本地开发

当前 P0 明确不应进入产品运行时的来源类型：

- `private_or_bypassed`
- `cookie_pool`
- `captcha_bypass`
- `private_chat`
- 未明确授权或来源不清的数据

因此，本技术储备只作为后续 SourceAdapter、Data Acquisition Operator Agent、PlatformSignalAnalyst Agent 的设计参考。

## 3. 调研对象速览

### 3.1 通用网页采集 / 爬虫框架

| 项目 | 定位 | 适合度 | 备注 |
| --- | --- | --- | --- |
| Scrapling | Python 自适应网页抓取库 | 适合公开 Web、新闻、政务、论坛公开页 | 有 HTTP、Playwright 动态页、Stealthy、Spider、代理、重试、adaptive selector；不解决 App 授权和合规问题 |
| Crawlee Python / Node | 通用爬虫与浏览器自动化框架 | 适合公开 Web 大规模调度 | 比 Scrapling 更偏 crawler runtime；仍需自己写平台适配和合规边界 |
| Scrapy | 成熟 Python 爬虫框架 | 适合公开 Web 和稳定网页源 | 对现代强动态 App 页不够直接 |
| EasySpider | 可视化采集工具 | 适合人工配置型采集验证 | 更像可视化浏览器自动化，不适合作为长期后端核心 |

### 3.2 多平台 App / 社媒采集项目

| 项目 | 覆盖 | 适合度 | 主要风险 |
| --- | --- | --- | --- |
| MediaCrawler | 小红书、抖音、快手、B站、微博、贴吧、知乎 | 最贴近“定点抓取内容/评论/主页/搜索”的技术验证 | README 明确学习用途、禁止商用；依赖浏览器上下文、登录态、代理等能力 |
| ShilongLee/Crawler | 抖音、快手、B站、小红书、淘宝、京东、微博 | 可作为多平台能力上限参考 | 需要账号、Cookie、代理池；生产合规风险高 |
| Douyin_TikTok_Download_API | 抖音、TikTok、快手、Bilibili 解析/下载/API | 抖音/TikTok 解析能力参考 | 涉及 Web API 签名、Cookie、风控对抗；不适合作生产主链路 |
| TikTokDownloader | 抖音/TikTok 账号、评论、搜索、热榜、直播等 | 抖音专项能力参考 | Cookie、账号、下载链路、GPL-3.0 许可约束 |
| Nemo2011/bilibili-api | B站常用 API 调用 | B站专项 POC 候选 | 非官方 API，接口可能变更，部分功能需登录凭据 |
| SocialSisterYi/bilibili-API-collect | B站 API 文档集合 | 不建议作为依据 | 已归档，README 提到收到律师函警告 |

### 3.3 热榜 / RSS / 新闻聚合

| 项目 | 覆盖 | 适合度 | 备注 |
| --- | --- | --- | --- |
| TrendRadar | 多平台热点、RSS、关键词监控、AI 简报 | 适合城市态势和热点入口 | 不是深度评论爬虫，风险相对低 |
| NewsCrawler | 微信公众号、今日头条、网易、搜狐、腾讯、海外新闻等 | 适合头条/新闻/公开文章源 | 输出 JSON/Markdown，适合 public_web 或 authorized_export |
| RSSHub | 大量站点 RSS 路由 | 适合低风险公开订阅源 | 不适合拿评论、互动细节、深层 App 数据 |
| newsnow | 实时热点阅读/聚合 | 可作为热点源参考 | 更偏热点聚合，不是证据级原始采集器 |

### 3.4 第三方数据 API / SDK

| 项目 | 定位 | 适合度 | 备注 |
| --- | --- | --- | --- |
| TikHub API Python SDK | 商业社媒数据 API SDK | 可按 `third_party_contract` 评估 | 需要 API key、合同、数据来源审查 |
| MoreAPI | 非官方 RESTful API 平台 | 可做供应商候选审查 | 需要 Token/积分，需核查合规与来源 |

第三方数据 API 不应被当作“开源爬虫”处理。它们更接近数据供应商，需要进入采购、合同、授权、数据来源说明、留痕审计流程。

## 4. 平台层判断

| 平台 | 公开定点 URL | 搜索/话题/主页 | 评论/互动指标 | 生产建议 |
| --- | --- | --- | --- | --- |
| B站 | 相对可行 | 部分可行 | 部分可行，但接口和权限不稳定 | 可优先做 POC；高风险功能需授权或供应商 |
| 今日头条 | 文章页相对可行 | 部分可行 | 评论/推荐流不稳定 | 先做公开文章和新闻聚合 |
| 抖音 | 分享页/公开视频页部分可行 | 不稳定 | 深度评论、搜索、热榜依赖非官方机制 | 优先授权、第三方数据、人工补证；爬虫仅隔离 POC |
| 快手 | 分享页有限可行 | 不稳定 | 评论、直播、搜索不可靠 | 同抖音 |
| 小红书 | 公开页受限明显 | 风控高 | 评论、搜索、主页批量风险高 | 不建议作为爬虫主路；走授权/供应商/人工补证 |

## 5. Agent 获取数据的边界

Agent 不是数据来源本身。它可以作为数据获取辅助操作员，但不能作为绕过平台边界的主采集器。

可行用法：

- 分析员给定公开 URL，Agent 读取可见内容并结构化。
- 官方后台或客户账号已授权时，Agent 辅助导出数据。
- 半自动证据补采：打开页面、截图、记录 URL、时间戳、页面 hash、可见字段。
- 对采集失败分类：登录要求、验证码、限流、404、内容删除、动态不可见。
- 生成补采关键词、平台检索策略和证据缺口清单。

不应使用：

- 模拟真人长期刷 App 页面。
- 自动维护账号池、Cookie 池、代理池。
- 绕验证码、滑块、设备指纹或平台风控。
- 抓私信、私域群、非公开页面。
- 自动点赞、评论、关注、私信、发帖或引导舆论。

建议新增概念：

```text
DataAcquisitionOperatorAgent
```

职责：

- 读取采集任务和 policy。
- 判断某 URL 是否属于允许来源。
- 规划补采关键词和时间窗口。
- 对公开页面可见信息做结构化。
- 生成失败原因和补采建议。
- 将结果交给 SourceAdapter 写入 `raw_records`，不直接写业务结论。

## 6. 专业平台 Agent 的可复用方向

类似 `marketing-xiaohongshu-operator` 的专业 Agent 可以借鉴“平台语境理解”，但必须重写成只读分析型 Agent。

推荐 Agent 组合：

| Agent | 作用 |
| --- | --- |
| XiaohongshuSignalAnalystAgent | 分析种草、避坑、测评、维权、口碑扩散、消费语境 |
| DouyinKuaishouSpreadAnalystAgent | 分析短视频爆点、同城扩散、直播切片、评论风向、情绪感染 |
| BilibiliCommunityAnalystAgent | 分析 UP 主叙事、弹幕/评论梗、圈层传播、长视频解释框架 |
| ToutiaoNewsNarrativeAgent | 分析媒体叙事、标题导向、转载链、官方回应锚点 |
| RumorEvidenceVerifierAgent | 识别旧视频错配、截图缺上下文、断章取义、来源链缺口 |
| ComplianceAgent | 判断隐私、未成年人、敏感个人信息、越权数据风险 |

硬规则：

- Agent 输出不是事实来源。
- 每条 claim 必须绑定 `evidence_refs`。
- 不确定内容进入 `needs_review` 或 `blocked_claims`。
- Agent 不执行运营动作。
- Prompt 必须按本项目证据链、合规和公共风险研判语境重写。

## 7. 推荐 POC 路线

### POC A: 公开 Web 定点采集

候选工具：

- Scrapling
- Crawlee
- NewsCrawler

输入：

- 每个平台 10 到 20 个公开 URL。
- 类型：新闻、政务公告、今日头条文章、B站公开视频页、公开论坛帖、公开分享页。

输出字段：

- 标题。
- 正文/描述。
- 作者公开名。
- 发布时间。
- 公开互动计数。
- 来源 URL。
- 抓取时间。
- HTML hash / screenshot ref。
- 失败原因。

通过标准：

- 不登录、不用 Cookie、不绕验证码。
- 输出进入 `raw_records`。
- 每条记录有 `access_mode=public_web` 和 policy decision。

### POC B: 多平台 App 能力边界验证

候选工具：

- MediaCrawler
- B站专项 `bilibili-api`
- 抖音专项库只做隔离评估

目标：

- 验证字段可得性。
- 验证失败类型。
- 验证账号/登录态依赖程度。
- 验证是否可做少量人工授权样本补采。

输出：

```text
platform
target_type
field
success_rate
requires_login
requires_cookie
captcha_or_risk_control
legal_or_license_risk
recommended_access_mode
```

通过标准：

- 不进入生产链路。
- 不保存敏感账号凭据。
- 不形成绕过方案文档。
- 只沉淀平台字段可得性和风险判断。

### POC C: 热点/RSS 入口

候选工具：

- TrendRadar
- RSSHub
- newsnow

目标：

- 提供城市态势页的热点入口。
- 做事件发现和关键词扩展。
- 与深度证据采集解耦。

通过标准：

- 可输出热点标题、来源、时间、链接、热度标记。
- 可进入 `signals` 候选，但不能直接形成正式 evidence。

### POC D: 第三方数据服务合规评估

候选：

- TikHub API
- MoreAPI
- 其他舆情/社媒数据供应商

评估清单：

- 是否有合同和授权说明。
- 是否能说明数据来源。
- 是否支持数据删除和保留策略。
- 是否支持审计日志。
- 是否有 SLA。
- 是否覆盖评论、搜索、账号、话题、互动指标。
- 是否允许政务/企业风险研判场景使用。

通过标准：

- 只以 `third_party_contract` 进入系统。
- 供应商数据不能绕过项目 SourcePolicyService。

## 8. 推荐系统接入形态

### 8.1 SourceAdapter 分层

```text
SourceAdapter
├─ PublicWebScraplingAdapter
├─ NewsCrawlerAdapter
├─ RSSHubAdapter
├─ AuthorizedExportAdapter
├─ ManualUploadAdapter
├─ ThirdPartyDataProviderAdapter
└─ ExperimentalAppCrawlerAdapter  # isolated POC only
```

### 8.2 采集结果进入对象链

```text
collection_jobs
-> collection_runs
-> raw_records
-> source_records
-> signals
-> evidence
-> risk_factors
-> mainlines
-> world_states
-> worldline_nodes
-> council_sessions
-> reports / tasks / audit_logs
```

所有采集器都必须：

- 写 `collection_runs`。
- 写 `raw_records`，不直接写下游业务对象。
- 写失败原因和 counters。
- 支持幂等去重。
- 写 `audit_logs`。
- 经过 `SourcePolicyService`。
- 对敏感内容默认脱敏或标记 `needs_review`。

## 9. 不进入生产的内容

以下内容可以作为外部风险知识，但不应沉淀为项目实现方案：

- Cookie 池搭建。
- 验证码绕过。
- App 签名参数逆向。
- 私有 API 逆向调用细节。
- 账号池、多账号轮换、封号规避。
- 私域群、私信、非公开内容采集。
- 自动点赞、评论、关注、发帖、私信。

## 10. 当前推荐排序

近期可做：

1. `NewsCrawler` / `RSSHub` / `TrendRadar` 做低风险热点和新闻入口。
2. `Scrapling` 做公开 Web 定点采集。
3. `MediaCrawler` 做隔离能力边界验证，不接产品链路。
4. `bilibili-api` 做 B站公开数据专项 POC。
5. 第三方数据服务按 `third_party_contract` 走供应商评估。

暂不做：

- 抖音/快手/小红书生产级非官方深爬。
- Cookie 池、验证码绕过、代理池规模化采集。
- 用 Agent 模拟真人刷 App。

## 11. 资料来源

- Scrapling: https://github.com/D4Vinci/Scrapling
- Scrapling docs: https://scrapling.readthedocs.io/en/latest/
- MediaCrawler: https://github.com/NanmiCoder/MediaCrawler
- TrendRadar: https://github.com/sansan0/TrendRadar
- NewsCrawler: https://github.com/NanmiCoder/NewsCrawler
- RSSHub: https://github.com/DIYgod/RSSHub
- newsnow: https://github.com/ourongxing/newsnow
- Douyin_TikTok_Download_API: https://github.com/Evil0ctal/Douyin_TikTok_Download_API
- TikTokDownloader: https://github.com/JoeanAmier/TikTokDownloader
- bilibili-api: https://github.com/Nemo2011/bilibili-api
- bilibili-API-collect: https://github.com/SocialSisterYi/bilibili-API-collect
- ShilongLee/Crawler: https://github.com/ShilongLee/Crawler
- TikHub API Python SDK: https://github.com/TikHub/TikHub-API-Python-SDK
- MoreAPI: https://github.com/wouldmissyou/MoreAPI
- Crawlee Python: https://github.com/apify/crawlee-python
- Crawlee Node: https://github.com/apify/crawlee
- Scrapy: https://github.com/scrapy/scrapy
- EasySpider: https://github.com/NaiboWang/EasySpider
- agency-agents-zh 小红书运营 Agent: https://github.com/jnMetaCode/agency-agents-zh/blob/main/marketing/marketing-xiaohongshu-operator.md
