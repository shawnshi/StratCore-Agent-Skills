# Daily Sync 只读协议

## 目的与边界

Daily Sync 计算命令核验持仓身份、行情覆盖、时效和已确认观察边界。命令本身不执行订单、不改写输入组合、不自动建立观察阈值，也不能在没有事件证据时宣布 Thesis 安全。`research_only` 与 `advisory` 报告均可给出买卖建议/倾向供用户参考或手动执行，但不修改实际持仓或真实账户，不执行订单；可执行参数须通过适用的行情、规则、资源与成本门，缺口或休市时明确待核验／待触发，不称立即可执行。已授权的 Dashboard、Thesis、独立风险政策或技能维护仍按 SKILL.md 执行；真实持仓导入／勘误是独立数据维护任务。维护与计算分开，修改相关输入后重新绑定并重跑必要门禁，不沿用旧报告的通过状态。

## 运行步骤

1. 用 `portfolio_loader.py` 验证已授权输入，按当次请求选择范围。完整清单用 `--analysis-scope all`，拆分 `quantity > 0` 实仓轨与 `quantity=0` 未购轨；仅实仓用 `held_only` 并列出范围外零股，不把实仓完成标为全部清单完成。单一证券或文档摘要不启动全清单流程。
2. 运行 `yf.py <代码...> --daily-sync --positions-file <portfolio.json> --cache-dir <task-dir>/yfinance-cache`，把标准输出保存到本任务隔离目录中的 `quotes.json`。该模式只取当前报价与身份字段，不计算历史技术指标或新闻，并默认以 1 个工作线程串行拉取独立标的；可用 `--daily-sync-workers 1..4` 调整。每个协调线程等待可终止的隔离提供方进程，单标的元数据操作默认 30 秒、最多 3 次进程尝试；启动、退避计入预算，终止与强杀分别最多追加 1 秒等待，结果按首次输入顺序排列。独立标的超时不阻塞其他有效结果。完整限制与迁移见 [free-data-policy.md](free-data-policy.md#provider-稳定性与迁移stage3a)。同一批次同时输出 `provider_receipt`（`provider`、`operation`、`outcomes`/`outcome_counts`、`transport_failures`、`circuit_breaker_signature` 与声明）；`error`、`no_data`、`skipped_circuit_open` 互相区分，熔断跳过与传输错误都不得读成“该标的无报价”。**备用报价（默认开启，`--no-fallback-source` 关闭）**：仅当某标的的主源结果为 `error` 或 `skipped_circuit_open` 时，才尝试已标注的备用源（CN/US，Tencent 公开行情接口）；主源已给出 `ok`/`no_data` 的标的绝不替换。成功时该记录带 `quote_provenance`（`tier=secondary`、`source`、`source_locator=fallback:tencent:<symbol>`、`primary_outcome`、`unverifiable`），并注入仅由源回印字段构成的元数据（价格、币种、回印场所、市场状态、观测时间）；`quoteType` 等源未提供字段为空，由报价契约记为 `unverifiable.secondary_source.*` **警告**而非不匹配。主源失败原因仍保留在 `outcomes` 中，收据新增 `fallback`（`policy`、`trigger_outcomes`、`attempted`、`used`、`outcomes`、`sources`、`coverage_tier`）；备用源自身失败同样逐笔记录，不留沉默。重放端：声明为 secondary 的记录必须在 `data_sources` 与 `quote_provenance` 中指向同一来源定位符，否则仍以 `identity_mismatch` 失败关闭；通过时列入 `secondary_quote_symbols` 与阶段警告，但**不计入主源匹配数**，可执行性就绪表的 provider 行保持**未核验**。重放端原样携带为 `supplied_provider_receipt`。确定性的 TLS、证书、协议、缓存权限或 SQLite 打开错误不做同参数重试；在尚无成功结果时，同批次连续出现相同系统性传输错误会熔断尚未提交的标的，并为每个标的保留显式失败记录，熔断不得计作行情成功。批次审计必须携带活动持仓规范化摘要，字段固定为 `symbol`、`quantity`、`currency`、`market`、`asset_type`，并以 SHA-256 绑定。未显式提供缓存目录时，Daily Sync 使用当前工作目录下的 `tmp/pia-yfinance-cache`，并在首个请求前做实际写入探针，避免不可写的 SQLite 缓存触发整批重试。
3. 行情包必须是一个对象，顶层只含本批次的 `records` 与单一 `portfolio_batch_audit`。列表根、每条记录内嵌审计、部分结果、重复代码、遗漏、额外代码、行情错误或身份冲突均失败关闭。
4. 运行 `daily_sync.py --positions-file <portfolio.json> --quotes-file <quotes.json> [--holiday-calendar-file <同一交易所休市表>] [--thesis-evidence-file <evidence.json>]` 做独立离线重放。若采集端使用了休市日历放宽，重放端必须显式指定同一受原件校验的表并重新计算报价年龄；只凭采集包自报的 `holiday_extension` 不能判定为新鲜。未提供或表被改写时该长假报价保持失败关闭。当前输出契约为 `pia_daily_sync_offline_v3`，同时绑定持仓快照、输入行情包、派生 `quote_snapshot` 以及可选事件证据包；缺少行情绑定的旧报告只能作为档案查看，不能供当前权重或历史重放计算使用。

`yf.py` 批次审计与重放结果的 `completeness.complete` 必须同时为真。请求数、返回数、有效报价数、身份匹配数和预期活动持仓数必须相等，所有缺失、额外、重复、失败、陈旧和未匹配清单必须为空。

授权数据源分别传入：`--dashboard-root <authorized-root>`、`--risk-bounds-policy <authorized-policy>`。不再从持仓父目录、默认政策文件或 `PIA_RISK_BOUNDS_POLICY` 隐式读取。没有 Dashboard 根时记录 `dashboard_root_not_authorized`；限定任务可显式 `--skip-watchlist`，不称边界已核验。风险政策未提供不派生限制；显式提供但文件缺失不能通过。

## 未购研究轨（自动纳入，不虚构实仓）

`pia.py daily-run --analysis-scope all` 对清单中的零持股证券执行 `unpurchased_analysis`，不受实仓 FX/权重上游失败连带排除；`held_only` 不启动未购采集，输出显式范围与排除项。行情以普通 `yf.py --json --info-only` 采集，仅发送公开证券代码，其独立 `research_binding` 绑定未购清单及实仓快照，不假设一股、不混入原持仓批次审计。

- 在 `all` 范围输出 `out/unpurchased_quotes.json`、`out/unpurchased_analysis.json`，统计实仓＋未购＝本次完整清单。`held_only` 明示未购范围外，不读取旧未购制品补齐当前范围；缺少行情、正式估值、Dashboard、Thesis 或边界时列出不足。
- 数量、市值、已投入成本为零，持仓浮盈亏不适用。EPS比值只在正EPS、同币种股票且行情通过时作指示性计算；亏损、币种缺失/不匹配或ETF不套股票PE。正式估值比较只使用索引验证且数学一致的同币种场景。
- 可用 `--unpurchased-quotes-file <本轨带绑定包>` 离线复核，`--reuse-artifacts` 对本轨仍重新核验绑定与行情时效，不洗掉陈旧或失败数据。缺失/错绑定不能静默改成新绑定。
- 本轨Thesis另用 `--unpurchased-thesis-evidence-file <包>`；`pia.py build thesis-pack --research-universe --quotes-file <out/unpurchased_quotes.json> ...` 生成 `inputs/unpurchased_thesis_evidence_pack.json`。仍遵守原证据Schema、真实发布时间和覆盖要求，不影响 `inputs/thesis_evidence_pack.json` 或实仓报价。
- 全部非现金证券未购时只运行研究轨；证券实仓及现金权重均明确未计算，不虚构证券分母，也不把现有现金说成不存在。请求不适用于无已购证券的附加阶段会明确列为未执行。

## 行情与观察边界

### 价格与观测时间绑定

允许采用提供方真实的盘前／盘后报价。统一选择器 `select_quote_observation()` 输出 `pia_quote_observation_v1`：

- REGULAR 使用 `regularMarketPrice/regularMarketTime`；仅价格字段缺少有效值时保留原有 `currentPrice` 兼容路径，时间仍须来自 `regularMarketTime`。
- PRE/PREPRE 优先 `preMarketPrice/preMarketTime`；POST/POSTPOST 优先 `postMarketPrice/postMarketTime`。两字段均未提供时，可带警告使用仍通过同一市场状态时效门的常规报价，明确标为 REGULAR；不可称盘前／盘后报价。仅一字段存在、已提供但无效、陈旧或超允许未来偏差时，不借用常规字段修补该对观测。
- CLOSED 在常规、盘前、盘后三对有有效时间戳的观测中选择最新一对，再执行现有 CLOSED 时效／日历门；不会将扩展时段观测改名为常规收盘。
- 不修改提供方原字段。采集审计、Daily Sync 快照、权重证据与报告保留 `session`、`price_field`、`timestamp_field`、价格及原观测秒级时点。权重消费者对新旧快照都重读绑定的原始行情包，核对价格、时间、币种和市场状态，不仅信任快照哈希。旧快照缺少 observation 时，仅按源 regular/currentPrice 与 regularMarketTime 兼容绑定，包括原常规时间的假日延期；删除或置空 observation 不得豁免源绑定。缺失或重复源记录失败关闭，不能用空 records 的声明包补证明。
- 盘前／盘后价格可能有较低流动性与较宽价差；用于组合观测不代表可成交保证。报告消费龄15分钟、FX72小时与现有市场状态报价门均不放宽。


逐项核对代码、交易所、币种、资产类型、报价时间和市场状态。时效阈值以 `yf.py` 输出的结构化 freshness policy 为准：`REGULAR` 为 900 秒，`PRE`、`PREPRE`、`POST`、`POSTPOST` 为 86400 秒，`CLOSED` 基础值为 259200 秒；仅显式提供且重新核验对应交易所原件的日历、且报价日期后的每一天均休市时，CLOSED 可在上限内增加已证实休市日；任何中间开市日都中断放宽。市场状态缺失或未知、报价超过允许的未来偏差、超过对应状态上限均失败关闭。不得用成本价、默认汇率、零值或其他标的价格补位。

先运行 `dashboard_catalog.py`，仅通过 `dashboard_index.json` 定位最新 Dashboard JSON。索引缺失、越界、损坏、代码不匹配或门禁失败均返回数据不足；不得搜索旧 Markdown 补位。

观察边界分两类，均不产生方向、数量或订单。

第一类是 Dashboard 的 `monitoring_boundaries`：只接受用户明确确认、带来源定位且 `decision_scope=observation_only` 的条目（`authority_status=user_confirmed`）。

第二类是**政策派生限制**：由 `position_limits.py` 从用户确认的风险政策（`pia_risk_bounds_policy_v1`，含 `max_single_position_weight`、`max_single_position_loss`、`upside_cost_multiple`）与本次 `weights.json` 自动推算，不使用任何手工逐笔阈值：`下行 = avg_cost × (1 − max_loss)`、`上行(成本) = avg_cost × upside_cost_multiple`、`上行(权重帽) = max_weight × 组合总市值 ÷ (数量 × 汇率)`。派生产物每条必须携带 `authority_status=derived_from_user_policy`、政策的 `source_locator` 与 `content_sha256`，以及可复核的 `derivation` 算式。该类别**只从显式传入的派生文件读取**（`watchlist_gate.py --derived-limits <position_limits.json>`），Dashboard 自身声明派生边界会被拒绝；派生文件 schema、authority、政策定位符、政策哈希或算式任一缺失/非法即失败关闭（`derived_limits_invalid`）。政策文件本身是用户确认资产；派生边界随持仓、行情和汇率刷新自动重算，不需要也不允许逐笔手填。

从本次 `quote_snapshot` 为每个标的生成临时行情对象，再运行 `watchlist_gate.py`。临时对象至少包含 `symbol`、`current_price`、`currency`、`as_of`、`source` 和 `market_state`。两个类别并列汇报、互不替代：第一类保持其历史确认值与日期，第二类随本次政策与组合规模变化。若 Dashboard 无观察边界但存在该标的的派生限制，则只评派生类别，`detail_status=derived_limits_only`。

不得读取归档 Dashboard 的旧价格作为当前行情，不得自动创建或迁移边界，也不得使用默认接近百分比。输出只描述已越界、接近、未越界、未定义或证据不足，不给方向、数量或订单。

接近规则（`near`）的来源必须显式：优先取 Dashboard 的 `monitoring_boundaries.proximity_policy`（用户确认值）；该字段缺位时回退到用户风险政策里的 `proximity`（由 `position_limits.py` 透传到派生文件），并在报告里以 `proximity_policy_source=dashboard|user_policy` 标注来源；两者均无时保持 `near_rule_undefined`。回退值是用户显式确认的常量，不是默认百分比，也不得来自代码内建常量。

手工档覆盖门：权威 Dashboard JSON 是手工档的唯一来源（见上）。若某个活动非现金标的的 `monitoring_boundaries_defined=false`，调用层必须在报告层列出该标的与 `manual_boundary_coverage_gap`；与上一轮运行目录的 `out/dashboard_catalog.json` 对比发现某标的的手工档从有到无时，同样必须报该缺口。缺口只说明本轮护栏覆盖不完整，不得用归档代补齐、不得自动迁移边界，也不得读作该标的无边界。该审计可直接运行：`python -B scripts/manual_boundary_audit.py --stocks-root <dashboard 根> --run-dir <本次运行目录> [--out <json>]`，输出越界/接近/未越界/未评估与 `manual_boundary_coverage_gap`（只读，不改任何 Dashboard 或运行制品）。

## 股票集中度核验

权重阶段完成后，按 [portfolio-audit.md 的股票集中度硬上限](portfolio-audit.md#股票集中度硬上限)核验：**单只股票 ≤ 30%，前三大股票合计 ≤ 65%**。分母为含现金的完整组合总市值；排名仅含实仓股票，不含ETF或零股观察标的。两项与价格观察边界、独立政策派生限制及其他已确认更严约束并列汇报，不互相替代。

报告必须给出最大单只股票、前三股票及各自权重、合计和两项结果。原生 `weights.json` 没有前三集中度字段时，用本次绑定的全组合市值确定性补算并注明补充检查；上游权重未通过或过期时标记未评估，不以旧权重、缺失值或股票子集归一化代替。集中度越界不等于公司致命事件，也不单独证明流程失败；完整行情不等于集中度符合约束。

## Thesis 红队

没有 `--thesis-evidence-file` 时，离线 `daily_sync.py` 把 Thesis 阶段标记为 `not_assessed/insufficient_evidence`，因此即使行情批次闭合，顶层仍为 `incomplete`。完成事件判断时，先批量读取发行人、交易所、监管机构和官方产品披露列表，只对窗口内新增且命中证伪条件的材料深读；再按 [thesis_red_team_schema.json](thesis_red_team_schema.json) 形成证据包。A 股发行人/交易所通道的取用要点、零结果对照规则与稳定失败码见 [cn_disclosure_channels.md](cn_disclosure_channels.md)；零结果无对照即为 `coverage_unproven`，不得读作无事件。

证据包必须绑定同一快照与评估窗口。v1 历史包仍可读，但 URL、哈希、结论或未来到期声明本身只属于 `declaration_only`，不能成为已验证命中或全局安全。`daily-sync`、`daily-run`、`build thesis-pack` 显式接收 `--conditions-file <获授权原生台账>` 与 `--evidence-root <获授权原件根>`；不得从包内路径自动发现权限。实仓与未购研究共用这两个显式绑定，未购包仍单独传入。

v2 见 [thesis_red_team_v2_schema.json](thesis_red_team_v2_schema.json)：台账原字节 `conditions_sha256`、当前 `condition_version/condition_ids`、原件相对 `local_path` 与 `/facts/N` 指针绑定后，重算数值条件。只支持严格期间/范围/单位一致的 UTF-8 JSON facts；定性条件、旧字符串期间和缺少确认的规则为不足，不推断策略。发布者真实性及宏观/板块/监管语义覆盖未由本数值切片证明，因此顶层仍保守 `incomplete`。即使其他标的或覆盖缺失，`verified_hits/fatal_symbols` 的已验证局部命中仍必须传播到报告；提交的 `fatal_breach` 不等于命中。builder 的 `artifact_build_status=complete` 只表示文件生成，不提升验证状态。

约束表面保留 `constraint_resolution` 的未确认/冲突/排除与 `weight_compliance`；已知 `weight_cap_breached` 不因其他规则未决而消失。权重帽价格仅是冻结 NAV 映射，不是动态权重触发价；`within_limit` 不表示全局安全。

没有新闻不能升级为“未发现致命事件”，股价变化也不能单独证明 Thesis 失效。最终报告必须把行情闭合度与 Thesis 证据状态分开呈现。

净值型条件（如 ETF 的 `nav_per_unit`）不得用市场价代替，也不得用期末口径冒充当日口径：管理人详情页每日可提供一个带净值日期的观测点，用 `scripts/fund_nav_ledger.py` 幂等累积成台账（`pia_fund_nav_point_v1`），条件核验引用「已累积观测点」而不依赖无法直取的历史序列；台账仍属单点观测的集合，不得表述为完整序列。

## 读取 Dashboard 7.2 的局部边界

目录可读取真实版本 7.0/7.1/7.2，不能改旧 JSON 版本或将档案价格用于当前行情。7.2 公开来源的日级/未知首次发布时间与实际 availability_observed_at 分离，详见 company-research；这只扩展 Dashboard 取证表达，不修改本文件 Thesis 红队 evidence 包或行情契约。不得把原件重验 verified_at、文件 mtime 或 retrieved_at 填入 published_at，也不得用来源观测时间替代报价秒级时效核验。缺事件证据仍不升级为 Thesis 安全。
