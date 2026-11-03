# Skills

认知棱镜  StratCore-Agent-Skills
工具是人类意志的延伸。

面向战略顾问与垂直行业的专家级 Agent 技能库：涵盖医疗信息化、战略情报分析、认知解构与高阶交付物工程。
Production-grade Agent Skills for strategic advisors: Domain expertise in Healthcare IT, OSINT, cognitive modeling, and executive-level delivery.

这是一套专为高阶战略顾问、行业分析师与知识工程师构建的专家级 Agent 技能库（Skills for LLM/Agents）。

不同于常规泛化或玩具级的 Prompt 模板，本项目将严苛的咨询方法论、垂直行业认知壁垒与工业级交付标准工程化封装：
- **行业深度纵深**：穿透医疗信息化（HIS/EMR/集成平台解耦）、临床 AI 决策支持、企业商业模式与价值链解构；
- **硬核认知推理**：融合开源战略情报（OSINT）、系统动力学、第一性原理、战略北极星对账与严密假设证伪（Kill Criteria）；
- **生理与资本底盘**：覆盖长周期认知算力底盘（睡眠/HRV/心肺耐力 VO₂max/力量负荷）管理与跨周期多元资产抗脆弱审计；
- **生产级交付物**：直接驱动交互式网页报告（Web-Slide）、出版级排版、刊物级视觉与高信噪比文本输出。

当前库存为 51 个用户技能，覆盖学术与认知研究、医疗数字化、视觉与系统流程、个人工作流及文档工具。本目录是 Pi 的本地安装库，不是独立 Git 工作树。

- [技能目录](#5-skill-inventory)：按交付物查找入口，点击技能名查看 `SKILL.md`。
- [触发分工](#6-trigger-ownership)：区分相近入口，避免重复启动流程。
- [检查与维护](#7-gate)：按任务范围选择检查；历史通过记录不代表当前全库已验证。
- 源码仓库：[shawnshi/shawnshi-skills](https://github.com/shawnshi/shawnshi-skills)。


## 1. Runtime contract

- 本目录为当前 Pi 使用的本地技能库；每个技能目录中的 `SKILL.md` 是该技能的入口，执行仍受当前运行时能力与上位指令约束。
- 每个技能聚焦一个可描述、可触发、可验证的工作。
- 执行遵循宿主已加载的指令及适用的仓库 `AGENTS.md`；本地安装目录不一定包含仓库级文件。本 README 只记录库级 Schema、库存和维护说明，不得扩张权限或凌驾上位指令。
- 外部系统能力由真实工具、插件或 MCP 提供。技能不得用散文虚构工具接口。

## 2. Required shape

根目录结构：

```text
skills/
├── <skill-name>/           # 一级用户技能
├── scripts/                # 本库门禁、资源索引和共享校验脚本
├── shared/                 # 活跃的跨模型核验、结构模板与触发所有权矩阵
└── README.md               # 本文件，库级合同
```

每个一级技能目录必须包含：

```text
skill-name/
├── SKILL.md
├── agents/openai.yaml       # 可选：界面元数据或外部能力声明
├── scripts/                 # 可选：确定性、可重复执行的脚本
├── references/              # 可选：按需读取的领域资料
├── assets/                  # 可选：生成产物使用的模板和素材
└── resource-manifest.json   # 本库门禁使用的资源索引
```

`SKILL.md` 的 frontmatter 至少包含：

```yaml
---
name: skill-name
description: 说明技能做什么，以及用户在什么场景下应使用它。
---
```

约束：

- `name` 必须与目录名一致，只使用小写字母、数字和单连字符，长度不超过 64。
- `description` 必须同时写明能力和触发场景，长度为 1–1024 个字符。
- 可选字段限于 Pi 当前支持的 `license`、`compatibility`、`metadata`、`allowed-tools` 与 `disable-model-invocation`；低频或有外部副作用的手动技能用 `disable-model-invocation: true` 从自动路由提示中隐藏。
- 不加入 `version`、`tier`、`triggers`、`benefits-from` 等未被当前运行时消费的字段；版本等机器契约可放入 `metadata`。
- 正文写清目标、必要上下文、真实边界、可用工具或命令、交付物、验证和失败处理，不规定隐藏推理步骤。
- 不强制固定章节名。门禁不得因为缺少 `When to Use`、`Workflow`、`Telemetry` 等标题而失败。
- `SKILL.md` 不超过 500 行；大段模板、规范和示例放入 `references/`。
- 所有技能内资源使用相对技能目录的路径引用，避免深层引用链。

## 3. Execution boundaries

- 不要求输出 `<thought>`、`<Thinking>` 或其他内部推理稿。以证据、假设、验证结果和残余风险替代。
- 不硬编码用户目录、`.gemini`、`.kimi`、会话 ID 或 `file:///` 链接。
- 不把其他运行时的工具名当作当前可调用接口。通过自然语言描述所需能力，并核对宿主实际暴露的工具；`agents/openai.yaml` 仅在对应消费者支持时生效。
- 子代理只在任务可以独立拆分且并行能力可用时采用；必须保留单代理降级路径。
- 联网、安装依赖、控制外部应用、发送消息、发布、合并、删除和永久写入都属于显式授权分支；只有下表声明的窄化归档合同，才可把对应的生成请求本身视为向封闭档案或状态目标写入的授权。
- 临时文件放入当前任务可写的临时目录；最终产物写入用户指定或当前工作区的输出位置。
- Vector Lake、MEMORY、日志和用户偏好不默认写入。除下表声明的目标外，只有用户明确要求保存或同步时才执行。
- 处理医疗、金融、隐私、凭据和个人数据时，声明数据来源、适用范围、不确定性和升级条件。
- 不承诺 100% 成功、零错误或无法验证的效果。

### 3.1 Declared automatic persistence contracts

普通最终产物仍按上一节写入用户指定位置或当前工作区；下表只治理无需单独“保存”请求就会写入 canonical 档案、历史索引或其他长期状态的例外。每项例外必须同时限定触发请求、封闭目标集合和只读退出条件。未列入此表的技能不得把分析、生成或审计请求解释为长期归档授权；根门禁会拒绝未声明、重复、字段不完整或缺少只读退出边界的合同。

<!-- automatic-persistence-exceptions:start -->
| Skill | 构成写入授权的请求 | 封闭目标集合 | 只读退出条件 |
|---|---|---|---|
| `personal-cognitive-auditor` | 生成当前自然周、月或季度的精确 canonical 个人日志审计请求 | `personal-diary-writer` 权威入口返回的 canonical 季度个人日志内同周期审计区块 | 草稿、预览、只读、不保存、日度、年度、自定义路径或第二处存储 |
| `personal-diary-writer` | 生成通过受保护 `personal-diary-request-v1` 与内容门的完整个人日记，或承接 `personal-cognitive-auditor` 的当前自然周、月、季度审计请求 | 对应权威入口返回的 canonical 季度个人日志 | 草稿、预览、只读、不保存、专用操作日志写入、自定义路径或第二处存储 |
| `personal-health-analysis` | 明确启用 Garmin 自动同步 | 绑定的 GarminDB 本地数据库、一个当前用户计划任务及单一脱敏运行状态文件 | 仅诊断、预览、试运行、不同步、禁用、移除自动同步或自定义第二处存储 |
| `personal-intelligence-hub` | 生成正式日简报 | 正式新闻文件及新闻目录内的去重索引 | 预览或明确不保存时不归档；生产预览仍产生运行中间态 |
| `hit-weekly-brief` | 生成正式数字健康周报 | DigitalHealthWeeklyBrief 本地归档 | 草稿、预览或明确不保存 |
| `hit-industry-radar` | 生成正式医疗行业雷达 | HealthcareIndustryRadar 本地归档 | 草稿、预览或明确不保存 |
| `hit-lectures-scout` | 生成正式医疗数字化文献侦察报告 | DigitalHealthLecturesScout 本地归档 | 草稿、预览或明确不保存 |
<!-- automatic-persistence-exceptions:end -->

## 4. Resource and dependency rules

- 优先使用现有脚本。技能专属脚本按当前任务和实际风险选择检查；共享门禁或实际数据/外部操作按上位合同执行必要的正向、负向与恢复验证。
- 外部命令、操作系统、浏览器、桌面应用、Python/Node 包和凭据要求必须在正文的依赖或边界部分写明。
- 不提交 `node_modules`、缓存、日志、临时下载、测试输出或生成音频。
- 不把同一说明同时复制到 `SKILL.md` 和 `references/`。
- `resource-manifest.json` 只记录资源与引用状态，不定义技能语义。

## 5. Skill inventory

截至 2026-10-09，按一级目录内的 `SKILL.md` 盘点为 51 个用户技能；不计 `.system`、`scripts`、`shared`、缓存及运行产物。以下为入口功能摘要，完整触发条件、授权范围和退出边界以对应 `SKILL.md` 为准。

### Academic and cognitive research

| Skill | 功能说明 |
|---|---|
| [`academic-paper-reader`](academic-paper-reader/SKILL.md) | 深入拆解目标学术论文，核验身份与版本，审查方法、数据、关键数字、证据强度、局限及复现条件，并提供页码、章节和表图证据索引 |
| [`academic-scientific-visualization`](academic-scientific-visualization/SKILL.md) | 设计、生成和审查可投稿的科学图表，包括多面板布局、误差棒、显著性标注、防色盲编码、期刊尺寸和矢量导出 |
| [`automate-github-issues`](automate-github-issues/SKILL.md) | 审计、设计或配置 GitHub Issue 分析、任务拆分、冲突检测、代理分派和受控合并流程 |
| [`cognitive-book-mirror`](cognitive-book-mirror/SKILL.md) | 将书籍或长文重构为“原文主张—个人映射”的伴读分析，在保留作者原意的同时结合用户明确提供并授权使用的个人材料 |
| [`cognitive-ceo-review`](cognitive-ceo-review/SKILL.md) | 审计已有战略、产品或项目计划的经营价值、资源配置、收益路径、范围取舍和退出机制；不自动接管普通技术架构审查或开放式脑暴 |
| [`cognitive-deep-reader`](cognitive-deep-reader/SKILL.md) | 分析非论文文章的核心机制、因果链、承重前提、反例及适用边界；普通摘要、论文方法审查和视频转录另走对应入口 |
| [`cognitive-hv-analysis`](cognitive-hv-analysis/SKILL.md) | 结合纵向演化与横向同期比较，解释公司、产品、技术、政策或社会现象的关键转折与当前差异；纯市场规模或供应商选型交行业研究 |
| [`cognitive-ideation-brainstorming`](cognitive-ideation-brainstorming/SKILL.md) | 将模糊创意或产品需求收敛为可验证的问题、范围、方案和设计决策 |
| [`cognitive-logic-adversary`](cognitive-logic-adversary/SKILL.md) | 对计划、论证和关键决策执行红队压力测试，识别矛盾、脆弱假设、单点故障和激励错位，并重构为更可防守的方案 |
| [`cognitive-morphism-mapper`](cognitive-morphism-mapper/SKILL.md) | 把业务或组织问题抽象为对象、关系和约束，再映射到控制论、生态学、博弈论等成熟领域，借用可验证机制生成跨领域方案 |
| [`cognitive-personal-roundtable`](cognitive-personal-roundtable/SKILL.md) | 对存在真实取舍的复杂议题开展证据化多视角压力测试，识别事实冲突、底层假设、遗漏变量和可执行决策路径；不替代检索与专业审查 |
| [`cognitive-storm-research`](cognitive-storm-research/SKILL.md) | 对跨证据域、存在实质争议或证据冲突的复杂公开议题开展综合研究，建立证据账本、比较解释与决策选项并给出证伪条件；不用于私人调查或实时监控 |
| [`industry-strategy-analyst`](industry-strategy-analyst/SKILL.md) | 以公开且可追溯的证据开展行业与市场研究，形成市场边界、规模、需求、价值链、竞争格局、供应商比较、情景预测、风险和可执行建议 |
| [`senior-osint-analyst`](senior-osint-analyst/SKILL.md) | 使用合法公开来源核验实体身份、任职、实体关系、事件时序和争议事实；不开展私人调查，也不替代市场选型或专业意见 |

### Healthcare strategy

| Skill | 功能说明 |
|---|---|
| [`hit-customer-analyst`](hit-customer-analyst/SKILL.md) | 医疗机构或医疗数字化企业的客户研究与拜访准备，提供会前速览、标准拜访包、战略客户包及待审核客户信；当前为 2.6.3 交付候选，实名 RACI 与必要授权不足时仅交付事实简报和阻塞项 |
| [`hit-digital-strategy-partner`](hit-digital-strategy-partner/SKILL.md) | 为医疗机构或医疗信息化企业开展数字化战略、方案选择、投资排序、可审计 ROI/TCO 和高管决策备忘录；不用于详细技术架构或临床审批 |
| [`hit-industry-radar`](hit-industry-radar/SKILL.md) | 检索指定周期的医疗 IT 政策、厂商及采购项目阶段事件，提供来源、事件日期与影响判断；正式雷达按声明合同自动归档 |
| [`hit-lectures-scout`](hit-lectures-scout/SKILL.md) | 检索、筛选和解释医疗AI、数字医疗与临床信息学论文及预印本，按研究类型评估证据质量，并将学术信号转化为可验证的研发、产品或市场假设 |
| [`hit-solution-architect`](hit-solution-architect/SKILL.md) | 设计或评审医疗机构技术方案，交付系统边界、数据流、接口、NFR、迁移回退与技术验收；投资取舍交战略入口，患者数据、跨境或临床影响须执行安全门 |
| [`hit-weekly-brief`](hit-weekly-brief/SKILL.md) | 面向中国医疗机构管理层及医疗 IT 经营决策者汇总数字健康、政策、医疗 AI 与信息化动态；正式周报验证后归档，速览及预览不保存 |

### Image and system workflows

| Skill | 功能说明 |
|---|---|
| [`image-prompt-gen`](image-prompt-gen/SKILL.md) | 将简短主题或现有视觉要求转化为原创、可执行的平面设计图像提示词，也可在用户明确要求时直接生成或编辑图片 |
| [`image-studio-architect`](image-studio-architect/SKILL.md) | 使用当前图像生成能力创建或编辑海报、封面、插画、概念图、社交媒体图片和其他视觉资产，并根据输入完整度补足构图、色彩、光线、材质与画幅 |
| [`magazine-illustrator`](magazine-illustrator/SKILL.md) | 为文章、博客、公众号、报告和演示文稿设计并直接生成杂志式位图插画，包括头图、封面、章节插图、系列配图和可复制的图像生成提示词 |
| [`reson-collaboration-audit`](reson-collaboration-audit/SKILL.md) | 基于真实会话、日志、工具调用和遥测审计执行效率与协作摩擦，按需生成 Markdown 报告或 HTML 面板；默认只读，不自动修改或持久化 |
| [`reson-skill-creator`](reson-skill-creator/SKILL.md) | 仅在用户显式调用时维护当前 Pi 本地技能库的根治理合同、资源清单、触发所有权、批量迁移与发布门禁；通用新技能、无关单技能更新及插件打包不触发 |

### Personal workflows

| Skill | 功能说明 |
|---|---|
| [`personal-cognitive-auditor`](personal-cognitive-auditor/SKILL.md) | 基于授权日志、日历与 Garmin 数据进行日、周、月、季、年事实复盘；核验整块深度工作时间与碎片损耗，执行战略北极星时间账本对账并输出季度止损清单（Kill List），精确个人周、月、季度请求过门后保存 canonical 日志 |
| [`personal-cognitive-prescription`](personal-cognitive-prescription/SKILL.md) | 从用户提供的近期问题、决策或复盘材料中识别认知盲区，并给出可核验到具体章节的跨领域阅读处方 |
| [`personal-diary-writer`](personal-diary-writer/SKILL.md) | 生成并保存个人日记或周期审计；完整日记通过内容门后保存到 canonical 季度日志，周期审计走受保护请求门。历史Reson操作日志仅按授权日期只读，专用写入已退役；纯当次草稿不读取私人数据、不保存 |
| [`personal-health-analysis`](personal-health-analysis/SKILL.md) | 本地优先分析恢复支撑（睡眠结构/HRV）与长期底盘（心肺耐力 VO₂max/力量训练负荷），生成非诊断报告或零外联面板；登录、同步及轨迹下载需独立授权 |
| [`personal-intelligence-hub`](personal-intelligence-hub/SKILL.md) | 生成基线优先、跨技术与医疗数字化且带历史去重的日资讯简报；正式简报自动保存，生产预览仍产生运行中间态 |
| [`personal-investment-advisor`](personal-investment-advisor/SKILL.md) | 开展证券财报与估值研究、跨周期多元资产配置与流动性跑道审计、主业与投资双重集中度（Double-Exposure）穿透审计、Daily Sync、主动研究与判断复盘；默认免费公开来源，支持 `research_only` / `advisory` / `actionable` 产出标注，不下单或执行订单 |
| [`personal-musicbee-dj`](personal-musicbee-dj/SKILL.md) | 管理本地 MusicBee 歌单与播放；明确标签补全请求使用专用 JSON 研究角色串行研究并受控回写五字段，支持只生成不播放及只读预览，不改播放统计或应用设置 |
| [`personal-travel-research`](personal-travel-research/SKILL.md) | 为城市或地区制作历史、考古、古建筑、博物馆与重点文物的出发前研究资料，并核验当前开放信息 |
| [`personal-write-humanizer`](personal-write-humanizer/SKILL.md) | 在不改变事实、业务含义与立场的前提下自然化改写已有中文稿；不伪装身份、规避检测或篡改证据，领域核验交医疗写作入口 |
| [`personal-writing-assistant`](personal-writing-assistant/SKILL.md) | 起草、重构、核验和审校医疗卫生与医疗数字化专业文章，负责领域主张、证据、政策含义与发布风险；纯自然化和事实定稿后的忠实编辑分别交相邻入口 |

### Meetings and utility workflows

| Skill | 功能说明 |
|---|---|
| [`officecli`](officecli/SKILL.md) | 使用 officecli CLI 创建、分析、校对和修改 DOCX、XLSX 与 PPTX 文档，并检查格式、定位问题、添加图表或执行结构化编辑 |
| [`tencent-meeting-mcp`](tencent-meeting-mcp/SKILL.md) | 通过已安装并授权的腾讯会议 CLI 或本地代理查询会议、成员、录制、转写和智能纪要，并在明确确认后创建、更新或取消会议 |
| [`tool-archive-crawler`](tool-archive-crawler/SKILL.md) | 对用户明确指定的历史文件、旧笔记或档案目录进行只读盘点、文本提取、去重、主题归类和可追溯摘要 |
| [`tool-blogger-publisher`](tool-blogger-publisher/SKILL.md) | 将 Markdown 转为 Blogger、微信公众号或邮件订阅系统适用的内联样式 HTML，检查结构、链接、图片与基础安全；只生成制品，不自动发布 |
| [`tool-concept-synthesis`](tool-concept-synthesis/SKILL.md) | 跨来源梳理概念、实体与关系，形成有证据支撑的体系图和战略长文 |
| [`tool-document-summarizer`](tool-document-summarizer/SKILL.md) | 提取医疗信息化、商业方案、招标材料和政策文件的结构化摘要与标签 |
| [`technical-diagram-renderer`](technical-diagram-renderer/SKILL.md) | 将已确认的系统关系或流程描述规范化为结构化 JSON，并生成经过结构与安全校验的静态 SVG 技术图，按需单向导出基础 `.drawio`/mxGraph 文件 |
| [`tool-markdown-converter`](tool-markdown-converter/SKILL.md) | 将 PDF、Office、HTML、富文本和杂乱笔记转换为结构清晰的 Markdown |
| [`tool-slide-architect`](tool-slide-architect/SKILL.md) | 设计、审阅与重构高管汇报、咨询路演、项目提案及培训材料的叙事结构、逐页蓝图和讲稿；为实际 PPTX 制作提供内容交接 |
| [`tool-smart-latex`](tool-smart-latex/SKILL.md) | 将 Markdown 或结构化内容排版为 LaTeX，依赖可用时编译并视觉验收 PDF；不因一般文档任务强制转 TeX |
| [`tool-text-forger`](tool-text-forger/SKILL.md) | 对事实定稿的现有文本进行忠实校对、轻度润色、受控重组或压缩，保留立场、限定条件和格式；自然化与领域核验另走对应入口 |
| [`tool-tts`](tool-tts/SKILL.md) | 将用户提供的文本合成为语音并在明确要求时播放 |
| [`tool-tuanbiao-downloader`](tool-tuanbiao-downloader/SKILL.md) | 仅下载全国团体标准信息平台公开可访问的 kkfileview 图片型标准并合并为 PDF；需显式调用并提供图片查看链接或已核实的路径 ID，不支持其他站点或普通 PDF 链接 |
| [`tool-url-markdown`](tool-url-markdown/SKILL.md) | 提取指定网页正文为 Markdown，或按请求总结；仅在要求保存时写文件，普通读取不足才使用获准浏览器会话，不采集其他标签页 |
| [`tool-web-slide`](tool-web-slide/SKILL.md) | 将演示内容构建为可在浏览器运行、验证和交付的 HTML 幻灯片、离线演示包或单文件 HTML；不用于原生 PPTX 或仅需故事线的任务 |
| [`tool-youtube-summary`](tool-youtube-summary/SKILL.md) | 从 YouTube 视频、字幕或音视频转录稿提取论点与证据，生成摘要、时间轴、观点矩阵或改写文章；不自动接管普通长文摘要 |

## 6. Trigger ownership

相近技能按产物区分：

- 医疗领域新稿、主张变更、证据/政策判断与发布审校：`personal-writing-assistant`
- 事实定稿后的忠实校对、轻润色、受控重组与压缩：`tool-text-forger`
- 明确去 AI 味/更自然且无需领域判断：`personal-write-humanizer`
- 演示文稿蓝图：`tool-slide-architect`
- 可运行的 HTML 幻灯片与离线演示包：`tool-web-slide`
- 位图提示词：`image-prompt-gen`
- 位图生成或编辑：`image-studio-architect`
- 文章与报告的杂志式插画：`magazine-illustrator`
- 科研论文图表与成品 QA：`academic-scientific-visualization`
- 系统结构图：`technical-diagram-renderer`
- 单篇论文身份、方法与结果（快速问答按需核验）：`academic-paper-reader`
- 非论文长文论证拆解（非普通摘要/压缩）：`cognitive-deep-reader`
- 视频、字幕与转录内容：`tool-youtube-summary`
- 纵向演化＋横向同期对照：`cognitive-hv-analysis`
- 市场、行业、供应商决策：`industry-strategy-analyst`
- 实体身份、事实、时序与公开材料核查：`senior-osint-analyst`
- 跨证据域、真实争议或冲突的综合研究：`cognitive-storm-research`
- 医疗文档摘要：`tool-document-summarizer`
- 通用文件转 Markdown：`tool-markdown-converter`

详细所有权由 `shared/trigger-ownership-matrix.json` 维护；其中引用的技能必须真实存在。

写作按主任务而非医疗名词分流：纯语言请求不启动完整医疗写作项目；混合请求仅按需组合，不强制串联三个入口。矩阵新增 `faithful_controlled_editing` 表达 S46 的忠实编辑所有权，保留既有类 ID；`secondary_skills` 只表示可选协作，不要求加载。研究入口收窄自动触发，不禁止用户显式要求的合法深研。

当前 `SKILL.md` 声明 `disable-model-invocation: true` 的手动入口为：`automate-github-issues`、`image-prompt-gen`、`image-studio-architect`、`reson-skill-creator`、`personal-travel-research`、`tencent-meeting-mcp`、`tool-blogger-publisher`、`tool-tts`、`tool-tuanbiao-downloader`。此清单只描述 Pi 入口声明，不证明外部消费者的调用策略或实际模型选路。

`hit-customer-analyst` 已启用受限自动触发；当前候选版本为 2.6.3，进入完整流程仍须满足实名 RACI 与授权门。下列历史 Gate 和测试记录保持原日期，不作为当前验证结果。

## 7. Gate

跨平台单一入口（缺 PowerShell 7 或 Python 3.10+ + PyYAML 时失败关闭，不自动安装）：

```sh
sh scripts/gate.sh                    # 全库确定性检查，不运行测试或写清单
sh scripts/gate.sh <skill-name> ...   # 按技能作用域，同上
sh scripts/gate.sh --tests            # 显式全库测试，另需 pytest；允许受控临时写入
sh scripts/gate.sh --refresh-manifests <skill-name> # 仅在该清单更新已获授权时使用
```

默认 Gate 不需要 pytest，并禁用 Python 字节码写入。测试与清单生成不是零写入审计；若测试预计超过单次执行预算，按用例分组直接运行，不盲目拉长超时。

刷新资源索引：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/generate_resource_manifests.ps1 -Root .
```

只检查不写入时增加 `-Check`；局部维护时增加 `-IncludeSkills <skill-name>`，先检查、获授权后再刷新，并用同一范围复检。

严格资源与界面元数据检查需要 Python 3 与 PyYAML；依赖缺失时 Gate 失败关闭，不得静默跳过，安装依赖仍须用户明确授权。

运行阻断门禁：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/repair_skills.ps1 -Mode Gate -Root .
```

脚本还支持：

- `-Mode Audit`：只输出检查结果，不写报告。
- `-Mode Report`：在报告目录生成 `skills-audit.json`。
- `-Mode Gate`：发现任一阻断项时返回非零退出码。

门禁必须检查：

- 一级用户技能数与 README 库存一致。
- frontmatter 包含 `name` 和 `description`，且可选字段仅使用 Pi 当前支持的集合。
- 名称、描述、行数、估算 token 和本地引用有效。行数与估算 token 双指标均按 `>0` 即失败：`SKILL.md` 默认不得超过 500 行或 8000 估算 token（`-LineThreshold` / `-TokenThreshold`）。
- 每个用户技能存在 schema v3 `resource-manifest.json`；清单字段、规范化哈希、全部受管资源、声明依赖和可移植路径与磁盘一致。
- 可选 `agents/openai.yaml` 必须能安全解析，界面字段、精确 `$skill-name` 默认提示、图标路径、颜色、调用策略和 MCP 依赖类型有效；调用策略与 `SKILL.md` 的 `disable-model-invocation` 不得互相矛盾。仅声明一侧时以 `OpenAiPolicyWarnings` 非阻断警告报告，不代替技能所有者决定路由。
- 对 `SKILL.md`、脚本、参考资料、配置和界面元数据执行一致检查，读取或解码失败必须保留诊断并阻断，不能静默跳过。
- 旧工具、外来宿主、推理词汇、模型版本、强制子代理和持久化的正则计数属于非阻断候选告警，须按上下文、真实工具和授权做语义审查；不能用匹配数证明违规或用零匹配证明安全。否定句、合法工具名和兼容性说明不应为消除告警被删除。上位的隐私、授权和禁止披露内部推理规则仍然有效。
- `_runtime`、`.venv`、`node_modules`、`__pycache__` 与构建输出目录属于用户运行产物或依赖副本，不进入源码一致性扫描，也不得被当作技能资源或业务事实。因此技能内自带虚拟环境不会产生误判。
- 触发所有权矩阵不存在未知技能和重复信号。

关键失败必须返回非零退出码；报告模式不得代替门禁。

## 8. Maintenance sequence

1. 读取目标技能及其直接引用资源，区分本地技能维护与共享门禁、全局治理或实际数据/外部操作。
2. 本地技能正文、配套资料、模板及专属脚本适用上位维护豁免，不统一要求基线、Diff 制品、测试或 Gate；按当前任务和实际风险选择工程措施。豁免不覆盖共享门禁、全局治理或实际数据/外部操作。
3. 只补丁式修改授权范围。必要脚本检查使用有意义的正向与负向用例，零写入审计不运行会写临时文件的测试。
4. 只有清单检查或更新属于当前任务时才选用 `scripts/generate_resource_manifests.ps1 -Check`；默认 `scripts/gate.sh` 只封装确定性检查，测试另用显式 `--tests`。
5. 共享脚本变更先核对语义，再按授权更新受影响的选中清单并复检。封闭写集或其他技能清单未获授权时，不顺带刷新；分别披露依赖漂移和未闭环项。
6. 编辑后的 Pi 加载验收使用 `/reload` 或新加载器/会话探针；区分磁盘检查、实际加载和模型行为，不以任一层替代其他层。必要检查通过后停止，不机械扩大测试。
7. 只有验证结果真实变化且更新获授权时，才同步本 README 的库存和基线数字；旧基线保留其日期，不改写成当前验证。



### 8.1 Current documentation snapshot (2026-10-09)

- 依据当前一级目录及 `SKILL.md` 入口元数据更新 51 个技能的目录、功能摘要与手动入口清单。
- 修正客户研究候选版本、投资研究产出等级、MusicBee 标签回写、网页提取保存边界及资讯预览中间态说明。
- 此次仅更新根 README；不修改技能入口、脚本、资源清单、触发矩阵或授权门，也不重跑全库 Gate、测试或新会话行为验证。
- 本地安装目录与 Git 发布副本分离。此前于 2026-10-09 同步至仓库 `main` 的提交为 [`36458502`](https://github.com/shawnshi/shawnshi-skills/commit/36458502f75043da9d5a07788fe214ce6395d9d6)，远端提交已核验；本节 README 更新尚未包含在该提交中。
- 发布同步排除缓存、临时文件、Cookie 数据库、运行审计记录及编辑状态；不得仅凭 `.gitignore` 假定所有敏感文件均已排除。

### 8.2 Historical validation (2026-09-24)

环境：Windows 主机；`pwsh`（PowerShell Core）；Python 3.13 + PyYAML。

- 全库 `sh scripts/gate.sh` 通过。`repair_skills.ps1 -Mode Gate` 的 28 类阻断项全为 0，退出码 0：`InventoryMismatch=False`（声明 52、实际 52）、`FrontmatterFailures=0`、`OversizedSkills=0`、`OversizedByEstimatedTokens=0`（最大估算 6600）、`MissingResourceManifests=0`、`InvalidResourceManifests=0`、`ManifestDependencyIssues=0`、`OpenAiMetadataFailures=0`、`ValidatorIntegrationFailures=0`、`DeprecatedToolSkills=0`、`ForeignRuntimeSkills=0`、`ReasoningDirectiveSkills=0`、`HardcodedModelSkills=0`、`SkillJsonFiles=0`、`NodeModulesDirectories=0`、`TriggerOwnershipClasses=19`、`TriggerOwnershipConflicts=0`。
- 非阻断项：`OpenAiPolicyWarnings=3`（`industry-strategy-analyst`、`personal-health-analysis`、`senior-osint-analyst` 的 `agents/openai.yaml` 关闭隐式调用，但 `SKILL.md` 未声明 `disable-model-invocation`，因此本宿主仍会自动触发）。属路由决策，待技能所有者确认后再改任一侧。
- 测试：`python -m pytest scripts -q` 运行 102 项，通过，67 项子测试通过。
- 资源清单：52 个技能各一份 schema v3 manifest，`-Check` 报过期 0。
- 修复项（本轮）：
  - 恢复丢失的 `scripts/validate_openai_yaml.py` 及其测试；同步 `scripts/resource_manifest.py` 与 `scripts/test_resource_manifest.py` 的 Lua 换行归一化修复。修复前 `repair_skills.ps1` 会在 `validator_integration_failures` 上恒失败，19 份 `agents/openai.yaml` 处于无校验状态。
  - 为 52 个技能补齐 `resource-manifest.json`（此前仅 2 份，缺失 39 份）。
  - 修正 `Get-SkillTextCorpus`：它未跳过 `.venv` 等依赖目录，导致 `personal-health-analysis` 的虚拟环境被当作技能正文扫描，误报 `deprecated_tool_skills=1`；同时使全库门禁耗时从数分钟降到约 7 秒。
  - 新增估算 token 指标（`CharCount`、`EstimatedTokens`、`OversizedByEstimatedTokens`、`MaxEstimatedTokens`、`-TokenThreshold`）；纯行数口径看不出一份 85 行、每行 118 字节的中文正文。
  - 新增调用策略一致性检查：`disable-model-invocation` 与 `allow_implicit_invocation` 矛盾时阻断，仅声明一侧时警告。
  - 新增 `scripts/gate.sh`，使门禁有可被第三方复现的跨平台入口。
  - `reson-skill-creator`：夹具从 8 条扩到 12 条并标明宿主表面（`pi` 用 `/skill:` 入口，`codex-openai` 用 `$<skill>`）；新增 `references/host-routing-eval.md` 定义宿主路由与档位评测的责任人、判据和运行记录格式；`SKILL.md` 增加门禁判定表，并按维护豁免把基线制品降为按需。
  - 独立修复（与本轮修改无关的既有漂移）：`scripts/test_autonomy_contracts.py` 的 `a02` 断言沿用 `pai/coding.md` 改词前的字面串，自 2026-09-24 起失败；已改为当前子句 `验收集合内存在不可归因的失败测试`。同步注意：该契约现允许可归因的既有失败单列披露，与 §10 既有段落一致。
- 未运行：宿主级路由与档位评测（本宿主未配置上游档位，夹具只证明合同完整）；`scripts/gate.sh` 的 POSIX 分支仅在 Windows Git Bash 下验证，未在 Linux/macOS 实测。
- 声明：上述结果只证明静态合同、资源一致性与单元测试通过，不代表所有技能已在新会话中端到端验证。

### 8.3 Historical validation (2026-09-09)

- 按当时本地一级 `SKILL.md` 盘点为 51 个技能；两个已退役后台/专用日志技能不在本目录，已从库存表移除。
- 自动持久化例外表保留 7 项现存技能合同；移除缺失技能的独立条目，不改变其他技能入口中已有的受保护写入边界。
- 已清理 `shared/trigger-ownership-matrix.json` 中对缺失专用日志技能的 3 处引用：移除其独占触发类别及两处辅助技能引用，不把相关请求转派给其他技能。触发所有权由 19 类调整为 18 类。
- 全库 `repair_skills.ps1 -Mode Gate` 通过：51 个技能、7 项自动持久化例外、18 类触发所有权，阻断项为 0。此结果仅证明静态合同与资源一致性，不代表所有技能已在新会话中端到端验证。
- 本地安装目录不含 `.git`；源码发布目标为 [shawnshi/shawnshi-skills](https://github.com/shawnshi/shawnshi-skills) 的 `main` 分支，通过独立 Git 工作副本同步，排除缓存、运行产物及敏感信息。发布副本按实际文件和 Git 字节表示生成资源清单，不保留空目录或运行日志的清单条目。
- 发布副本全库 Gate 通过。测试分别在适用环境运行：本地安装目录根测试 94 项通过；日记测试运行 63 项，跳过 4 项缺少已退役专用日志技能的可选集成，其余通过；发布副本资讯测试运行 337 项，跳过 1 项，其余通过。发布副本单独复验日记写入器 36 项，跳过相同 4 项，其余通过。
- 新增缺失专用日志证据门时拒绝写入且不创建目标目录的回归测试，未放宽生产写入门。依赖宿主目录布局的根合同及日记入口测试在本地安装目录验证，不将独立克隆中的路径不匹配写成代码通过。

### 8.4 Historical validation (2026-09-07)

- 本次全库 `repair_skills.ps1 -Mode Gate` 通过：53 个技能，8 项自动持久化例外，19 类触发所有权，阻断项为 0。
- 资源索引独立检查：53 个技能，过期或缺失清单为 0；界面元数据独立检查：19 份配置，错误为 0。
- 本次修复 `hit-customer-analyst` 的三项发布阻塞：生成缺失的资源清单，将默认提示中的技能标识改为 `$hit-customer-analyst`，移除校验器不接受的 `policy.products` 字段；未放宽校验规则或改变客户研究业务逻辑。
- `hit-customer-analyst` 仍为交付候选；静态门禁通过不改变其限定内部试用状态，真实发布验收以该技能的 `references/release-acceptance.md` 为准。
- Gate 只证明其覆盖的静态合同与资源一致性，不代表所有技能已在新会话中端到端验证，也不代替发布前的敏感信息检查。

### 8.5 Historical baseline (2026-09-05)

- 此前记录：全库 Gate 通过，53 个技能、8 项自动持久化例外、19 类触发所有权，阻断项为 0。
- 此前记录：已退役专用日志技能的 14 项测试当时通过；本次未重跑已移除模块。

Last updated: 2026-10-09
