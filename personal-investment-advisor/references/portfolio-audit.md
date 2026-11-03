# 组合审计与情景分析

## 持仓契约

仅对明确标记的假设资产标签与用户提供的权重做算术时，核验权重有限、非负、单位与口径一致、合计为 1（或 100%），不自动归一化；注明输入来源与假设范围，不要求真实持仓 Schema、行情或数量成本，不得声称当前权重或当前组合审计完成。此范围不适用下述真实持仓当前权重重算要求，也不得用于绕过情景脚本、分配实验或主动研究门禁。真实持仓组合必须通过 `portfolio_schema.json` v3.0，行情、来源与授权门保持不变。每条记录显式提供：

- `symbol`、`quantity`、`avg_cost`、`currency`；
- `market`：`CN`、`HK`、`US` 或 `CASH`；
- `asset_type`：`stock`、`etf`、`fund`、`index`、`cash` 或 `other`。

旧 `market_type` 只能作为被忽略的展示字段，不能满足或覆盖身份。现金身份必须同时满足 `CASH` 或 `CASH_*` 代码、`market=CASH` 和 `asset_type=cash`。

`quantity > 0` 才是活动持仓；零数量记录保留供审计，但排除市值、权重、风险、观察边界和情景计算。负数、非有限数字以及零数量配正权重必须失败关闭。现有旧组合不能根据代码或名称自动推断新字段，迁移前应逐项确认。

持仓文件中的旧 `current_weight` 只作为陈旧派生字段留痕，加载时会被剥离，不参与集中度、市场暴露或约束判断。当前权重必须由本次通过门禁的行情与汇率重新计算。

真实持仓导入是独立数据维护任务，不属于 advisory 参数建议的执行步骤；用户另行明确授权导入券商 CSV 后才运行 `broker_sync.py`。每行须由来源提供上述六个字段；任一关键字段缺失或无效时整批拒绝并保持原文件不变。验证通过后的快照通过唯一同目录临时文件、`fsync` 和原子替换提交，避免并发导入共享固定临时文件或中断写入截断原快照。

组合根不得内嵌 `rebalance_policy`；分配实验策略必须使用独立、显式版本的 policy 文件。用户提供的 `target_weight` 或 `max_weight` 在计算模块中作为输入约束，计算脚本不得自动重分配或写回。`advisory` 可在独立建议制品中给出价格、数量或目标仓位指令，但不写回实际持仓文件中的数量、成本、现金、成交状态或目标／约束字段。独立风险政策的已授权维护按 [SKILL.md](../SKILL.md#advisory-下的本地修改) 执行；不能借参数输出或维护绕过证据、可行性或 P0 门禁。

## 股票集中度硬上限

用户确认的通用规则：**单只股票权重 ≤ 30%；前三大股票权重之和 ≤ 65%**。这是组合风险约束，不是收益预测、目标仓位或公司 Thesis 致命条件；不依赖独立风险政策文件是否传入。

## 跨周期大类资产配置与双重集中度审计（Ten-Year Allocation & Anti-Fragility）

为支撑十年战略北极星并对冲单一行业/单一市场系统性风险，持仓全景审计在个股集中度基础上引入以下跨周期抗脆弱门禁：

1. **大类资产配置与流动性跑道（Liquidity Runway）**：
   - 审计权益资产（股票/权益类 ETF）、防御性资产与高流动性现金等价物（`market=CASH`、货币基金或短债）的配置比例；
   - 核验高流动性安全储备是否满足至少 18–24 个月的基础开支跑道，确保独立咨询、架构设计与专著创作不受资本市场短期周期的流动性挤兑。
2. **主业与资本双重集中度穿透门禁（Double-Exposure Concentration Gate）**：
   - 穿透核验持仓标的与个人主业（国内医疗数字化、医院 IT、公立医院信创）的产业重合度；
   - **双重敞口上限**：全组合中与国内医疗 IT 强相关的行业资产合计权重建议不超过 15%，防止主业收入（人力资本）与投资组合（金融资本）在行业调整期面临同向双重下挫的系统性脆弱。
3. **跨主权与跨币种分布（Geographic & Currency Diversification）**：
   - 结合持仓 `market`（`CN`、`HK`、`US`）与 `currency` 字段，审计多市场与多币种流动性资产的分布健康度，对冲单一主权货币与单一地缘市场的宏观周期波动；
   - **隐私脱敏铁律（`PRIVACY-SESSION-02`）**：大类配置比例与集中度审计仅在本地运行，对外行情与披露检索仅发送公开证券代码，严禁将持仓金额、数量或私有 Thesis 上传至外部网络。

- **分母**：通过本次行情、身份、覆盖和汇率门的全部活动持仓总市值，含现金、ETF及其他资产，统一换算至基础币种。不得改用股票子集市值或非现金市值重新归一化来核验这两项规则；分配实验的特殊分母不改变此处口径。
- **分子与排序范围**：只纳入 `quantity > 0` 且显式 `asset_type=stock` 的直接股票持仓，使用当前市值；按权重降序取前三只，并列时按证券代码排序以保证复算一致。ETF、基金、指数、现金及零持股观察标的不参与股票排名，也不自动穿透ETF。
- **算式**：`w_i = 股票i当前市值 / 全组合当前总市值`；`single_stock_breach = w_i > 0.30`；`top3_stock_breach = sum(前三只股票的w_i) > 0.65`。正好30%或65%不越界。少于三只时对实际持有股票求和，不虚构补足标的；没有实仓股票时标记不适用。
- **证据门**：只有完整、有效且满足下节时效的全组合权重才能给出通过或越界结论。分母不全、行情/FX失效、身份不明或只有部分持仓时标记未评估并列缺口，不把缺失当零。具名历史快照可作历史复核，但不得称为当前约束判断。
- **确定性计算与输出**：从本次已绑定市值重算未四舍五入的权重，再排序、求和和比较；不得靠展示百分比判断边界。报告必须列出最大单只股票及权重、前三只股票及各自权重、前三合计、30%/65%上限和两项判断。原生脚本未直接输出前三集中度时，在报告层使用确定性计算补核验，明确这是补充检查，不宣称原生CLI已经执行该门。
- **其他既有约束**：已授权输入中的更严单标的上限或观察边界仍单列核验；通用30%通过不等于更严上限通过。除非用户另行明确要求替换，不因本次技能规则更新自动撤销、更改这些约束，也不得由分析师临时新增更严上限。
- **状态与建议**：集中度越界是已评估的风险命中，不自动把流程记为技术失败，也不等于 `fatal_breach`。后续加仓或新建仓参数建议须按交易后同一全组合分母核验两项规则；若现仓已越界，减风险方案应明确其是否消除越界或仍有残余，不能把仍越界的方案标为满足约束。建议不回写真实持仓，不执行订单。

## 个别观察上限的有效性与未决

`position_limits.py` 的现有 `pia_risk_bounds_policy_v1` 全局已确认政策继续沿用其权威边界，不要求用户重复确认；股票另受本技能 30% 硬上限约束。前三股票 65% 仍由原组合审计门核验，本模块的单标的观察结果不能替代该门或 P0 Alpha／统计门。

仅当调用方明确提供获授权的政策文件时，可在其中新增可选 `individual_weight_constraints` 数组，用于明确确认的个别硬上限（不是新持仓格式或自动迁移）：

```json
{"constraint_id":"synthetic-limit","version":"1","source_locator":"synthetic://user-confirmation/1","symbol":"SYNTH","asset_type":"stock","market":"US","role":"hard_max_weight","denominator":"portfolio_total_market_value_base","value":0.1,"authority_status":"user_confirmed","status":"effective","confirmed_at":"2026-07-01","effective_from":"2026-07-01"}
```

`version` 是非空确认版本字符串；来源、确认日和生效日必须可回溯，不从数值大小、自然语言或文件存在推断已批准。确认日／生效日／可选 `effective_until` 为 ISO 日期，按输入 `evaluation_epoch` 的 UTC 日期计算，终止日当天仍有效。数值必须为有限 JSON number 且 `0 < value <= 1`，拒绝布尔／字符串；个别项仅接受上述字段及可选 `effective_until`，额外／矛盾的确认标志不静默忽略，归为未决。作用域须精确匹配 symbol（忽略大小写）、asset_type、market；只对同为组合总市值分母、同为 hard_max_weight 的有效规则求交。不同分母不做换算，不同角色（如目标权重）不充当硬上限。未来生效、已过期、`revoked`／`superseded` 不生效；同一 ID 多个有效版本／值或显式 `conflict` 不静默选更小值，不自动挑“最新”。新的版本须由独立授权的维护将旧项明确标为被替代。本技能不修改实际政策。

裸持仓 `max_weight` 继续可读，但在此观察组件中始终列为 `recorded_unconfirmed`，即使数字与确认政策相同也不自动给裸字段授权；`target_weight` 不参与求交。输出每行 `constraint_resolution` 包含 `active_items`、`recorded_unconfirmed`、`conflicts`、`gaps`、`inactive_items`、`excluded_items`、`effective_max_weight` 与 `status=complete|unresolved`，保留来源、版本、作用域及政策字节哈希。来源／版本／时钟缺失、不可比项或显式待确认均不得呈现全部有效。

每行 `weight_compliance` 用未舍入快照 `current_weight > effective_max_weight` 核验已生效上限，等于上限允许；`scope=active_constraints_only` 不代表所有未决条件安全。未决不遮蔽已知超限。观察门保留 `categories.weight_cap_breached` 和快照计算，同时将未决传播为 `constraint_authority_unresolved`／`evaluation_status=insufficient_data`，仍计算其他有证据的价格观察边界。调用方不能用“未评估未确认条件”推出安全结论；无有效运行行情时也保留已算出的快照超限。

### 仓位上限的冻结 NAV 价格映射

保留原公式 `effective_max_weight * portfolio_total_market_value_base / (quantity * fx)`。对应边界增加 `price_mapping.mode=snapshot_frozen_nav`、`denominator`、`frozen_nav`、`base_currency`、`evaluation_epoch` 和 `effective_max_weight`。这是计算时点总资产冻结后的截面映射，不是其他资产价值固定而本标的价格变化时重新计算分母的动态权重触发价。运行价格与该映射相等／交叉仅是价格观察事件，不等于权重违规；实际快照权重违规只看 `weight_compliance` 的严格大于比较。该映射不是买卖指令，不能保证之后的真实动态权重。权重快照来源与新运行行情不是同一时点时必须保留两者时点，不将旧权重冒充实时权重。

本组件不读取 Thesis、不新增或确认用户条件、不改写持仓或政策。政策字节哈希仅绑定所选输入，不独立认证确认来源；调用方仍负责授权文件选择、可信来源和现有组合数据验证。后续原生编排负责跨面状态汇总，不得将 `unresolved` 丢弃或把 `within_limit` 当全部安全。

## 当前权重与汇率

当前权重只能使用通过严格身份、覆盖和时效检查的 `pia_daily_sync_offline_v3` 报告；报告生成时间距本次计算超过 15 分钟时不再视为当前证据。计算端会重新读取并核对报告所绑定的持仓文件与原始行情包，按消费时点和 `market_state` 重算每条行情的实际年龄，不接受报告自报的空陈旧清单代替计算。持仓数量或身份字段在同一路径发生变化、原始行情包被改写、市场状态缺失或未知时均失败关闭。显式历史重放也执行相同绑定和时效核对，并标记为 `explicit_point_in_time_replay`，不得写成当前权重。

跨币种计算还必须有带 `pair`、`as_of`、`source`、`source_locator` 和 `retrieved_at` 的汇率快照；当前上限为 72 小时。旧平面汇率标记为 `undated_static`，陈旧或无法定位的快照不得据此声称得到当前权重。

需要刷新 USD/CNY 即期证据时，使用 `yf.py CNY=X --price-only --period 5d --lean --json --cache-dir <task-cache>`，优先使用真实 `info.regularMarketPrice` 与 `info.regularMarketTime`，字段不足才取有日期的日线 Close。保留实际观测时间和字段来源；未来或陈旧观测拒绝，不以抓取时间替代。外汇代码的 `=X` 身份可闭合为非 ETF 历史，不得套用 ETF 公司行动缺口文案。行情命令本身不授权改写持仓，当前权重实验应使用绑定同一持仓内容的隔离快照，并保留原文件哈希。

组合模块只报告原始权重、集中度、流动性数据缺口和约束状态。没有显式 `risk_profile` 时风险等级保持未知；不得把约束状态改写为组合动作。个人决策预算是**另一个由用户提供的研究输入**：仅在用户明确授权并给出投资期限、可承受损失、必要现金需求、单一行业／风格上限和情景假设时，才比较候选方案与其约束。资料不足时列出未知、保留部分风险诊断，不能把短窗口相关矩阵、已覆盖子集的归一权重或不含未测量资产的风险贡献写成全组合风险。不得为了风险预算自动读取账户号、完整净资产、其他目录或无关私人历史。仅在用户确认的上述比例预算与完整 v2 成本后情景报告均可用时，按 [personal-risk-budget.md](personal-risk-budget.md) 执行独立离线比较；只称已给场景的约束结果，不称全组合风险覆盖。

## 情景压力测试

`portfolio_scenario_analyzer.py` 只消费用户明确提供的情景收益与约束，不从历史涨跌自动生成预期收益。

当前情景计算只接受显式 `scenario_contract_version: "2.0"`。缺少版本、v1 或缺少来源化权重快照的输入只可作为旧档案查看，不得进入计算。v2 必须提供：

- 覆盖全部活动持仓的 `weight_snapshot`；其 `source_locator` 只接受公开 HTTP(S) URL、规范 SEC accession/CIK 标识或已登记的 `dataset://` 命名空间，并同时提供不晚于运行日的时区化 `retrieved_at` 与小写 `content_sha256`；
- 与活动持仓完全相等的收益标的集合；
- 跨币种资产所需的带日期、来源和定位的即期汇率；
- 显式、互斥且闭合的分桶范围和排除原因；
- 计算风险贡献时，闭合、对称、半正定的波动率与相关矩阵。

活动权重须在固定容差内合计为 1，不自动归一化。数字型 `asset_returns` 表示已经换算为基础币种的总收益；本币收益须使用 `local_total_return` 并配套 `fx_returns`，按 `(1+r_local)*(1+r_fx)-1` 换算。成本按 `weight*turnover*bps/10000` 逐项计算；成本不完整时成本后收益保持未知。波动贡献只是诊断，不得称为风险平价、优化权重或交易建议。

## 分配实验

分配计算按声明的 `decision_scope` 产出，可给出该级别允许的方向或参数；计算命令不得把实验结果自动写回持仓，也不得代客下单或路由订单。另行执行已授权的本地维护时遵守 SKILL.md 的本地修改边界；advisory 的建议数量和目标仓位只写独立方案，不直接或间接改实际持仓，未过提升门的实验权重不得写成候选或目标权重。策略遵循 `inverse_volatility_policy_schema.json`，结构参考 `inverse_volatility_policy.example.json`；具体离线参数和失败条件以 `rebalance_weights.py --help` 及专属测试为准。没有显式策略、已验证行情包、完整分桶和必要汇率时不计算。

当前方法名为 `inverse_volatility_allocation`。它忽略相关性，不能称为风险平价；波动率观测必须带期间、样本数、日期、来源和定位。实验输出使用 `experimental_weight`，不等于目标权重；提升为 `candidate_weight`/`target_weight` 必须按 `decision_scope` 声明并另行过对应门禁。免费数据无法通过主动 Alpha 门禁时，这一风险型实验仍可独立运行，不得把结果升级为 Rank/Yank、`candidate_weight` 或 `allocation_gap`。

### 现金与政策分母

默认口径要求桶成员覆盖每个活动标的（含现金），且一个现金桶恰含一个现金头寸。当已确认策略把一个以上现金头寸排除在分母外（例如用户确认的 80/20 非现金分母口径）时，可在 policy 中显式声明 `denominator: "active_non_cash_market_value"` 与 `excluded_policy_symbols`（每条必须给出非空原因）：此时 `bucket_targets` 只对非现金范围求和为 1.0、桶成员只需覆盖全部活动非现金标的，现金保留在全组合压力损益中但不出现在实验结果里；不得给现金造零波动率，也不得以事后缩放掩盖分母差异。`rebalance_weights.py --policy-file` 消费该 policy 时会把 `denominator`、`excluded_policy_symbols` 与 `scope_symbols` 原样回声，便于下游明确分母口径。

## 主动组合研究的额外门禁

若请求包含主动收益、Rank & Yank、风险平价候选权重或再平衡提案，必须另读 `active-research.md`。现有 `rebalance_weights.py` 和 `rebalance_optimizer.py` 是描述性分配实验，不构成 Alpha 验证；完整主动链路必须先通过 P0 Alpha 推广门禁，再使用完整协方差矩阵、成本、换手与单标的变化约束生成非执行研究候选；advisory 可在适用门禁闭合后另行给出供用户手动执行的具体参数方案，候选输出本身不是交易就绪证明。
