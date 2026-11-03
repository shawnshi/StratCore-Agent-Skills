# Garmin 多维健康画像合同

只在用户要求“全面健康分析”“深入健康指导”“多维健康画像”或比较睡眠、恢复、活动与夜间生理信号时读取本资料。画像是本地、只读、非诊断性分析，不生成健康总分、训练许可、疾病概率、药物或补剂建议。

## 1. 入口与读取范围

```bash
<SKILL_PYTHON> scripts/garmin_health_profile.py --days <N> --source local --timezone <IANA_TIMEZONE> --allow-health-data
```

- 未指定窗口时使用技能交互默认最近 14 天（N=14）；脚本允许 1–366 天，不得为了满足分析资格静默扩窗。
- 画像读取 `garmin.db` 中请求日期范围内的 `daily_summary|days_summary`、`sleep`、`hrv`、`weight`，`attributes` 中最新的 `vo2max_running|vo2max_cycling`，以及 `garmin_activities.db` 中非位置化的活动汇总字段。体重和活动各可额外读取截至窗口末端的单条最近记录，只用于报告新鲜度与 `outside_requested_window`，不得纳入请求窗口趋势。
- 活动查询只允许 `type`、起始日期、耗时、移动时间、距离、平均/最高心率、热量及 Garmin 训练负荷/效果字段；不得查询或输出活动 ID、名称、描述、设备序列号、起止坐标或原始轨迹。活动库缺失时只将该模块标为 `source_unavailable`，不能遮蔽其他健康模块。
- 睡眠起止时间缺少偏移时，只有调用方明确传入 IANA 时区才计算钟点规律；输出必须标记为 `caller_timezone_applied_to_naive_source`。没有时区时保持 `timezone_required`。
- `--adult-18-64-guideline` 只有在用户确认属于 18–64 岁成年人且明确要求公共卫生参考比较时才能附加。默认只展示 Garmin 强度分钟和用户设备中的目标，不判断是否达到 WHO 建议。
- 整次读取必须位于单一数据库指纹窗口内；数据库、Schema、WAL 或 SHM 在读取中变化时失败关闭。

## 2. 核心模块

| 模块 | 直接字段 | 允许派生 | 最低资格 | 禁止解释 |
|---|---|---|---|---|
| 睡眠健康 | 时长、起止、清醒、阶段、设备评分 | 窗口时长标准差、入睡/起床钟点圆周标准差、`总睡眠/(总睡眠+清醒)` 设备估算连续性 | 3 夜仅支持窗口描述；正式规律性需 14 日窗口、至少 7 夜及可比时期证据；描述性时点仍需明确时区 | 不把连续性称为临床睡眠效率，不用阶段比例诊断睡眠障碍 |
| 自主恢复 | 静息心率、昨夜 HRV、7 日 HRV、厂商基线区间与状态 | 7 日 HRV 相对厂商区间的位置 | 厂商基线字段同日齐全 | 不从 HRV 或静息心率推断感染、认知能力或训练许可 |
| 能量动态 | Body Battery 高、低、Charged | 日内峰谷跨度、中位 Charged | 至少 1 天可描述，趋势需逐项披露覆盖 | 不把 Body Battery、睡眠评分、HRV、压力当成相互独立证据或合成总分 |
| 日常活动 | 步数、活动热量、中高强度分钟、设备目标 | 最近 7 日中等分钟、剧烈分钟、Garmin 等效强度分钟、设备目标进度 | 强度比较需要完整披露有效天数 | 不使用通用“1 万步”阈值；不把目标进度当成训练处方或适运动证明 |
| 体重 | 体重 kg、测量日期 | 窗口中位数/范围；至少 3 次且跨 14 天后才计算首末变化和线性斜率 | 稀疏时只报告最近记录与新鲜度 | 不推断 BMI、体成分、目标体重、疾病或减重成效 |
| 已记录活动 | 类型、日期、耗时/移动时间、距离、心率、热量、厂商训练负荷/效果 | 窗口记录数、活跃记录日、总量、类型分布及厂商字段汇总；支持抗阻力/力量训练频次与负荷日聚类 | 事件流按实际记录汇总，空白日不补零 | 不读取位置/标识/名称/描述，不把无记录解释为无活动或训练建议 |
| 夜间生理 | 睡眠/醒时呼吸率、平均及最低 SpO₂ | 请求窗口内中位数、范围和覆盖 | 至少 1 天可描述 | 不设置缺氧、呼吸疾病或睡眠呼吸暂停诊断阈值 |
| 心肺估计 | 跑步或骑行 VO₂max 最新估计及时间戳 | 距今新鲜度；长周期窗口中记录相对既往有效估计的稳定区间与历史变动 | 单一模态最新有效值 | 不跨模态比较，不称为实验室测量，不用单点估计给训练许可 |

日度连续指标的派生结果要同时输出数据日期、单位、有效天数、覆盖率、最长缺失段和窗口末端缺失段。体重按稀疏测量序列输出测量次数与跨度；已记录活动按事件流输出记录数和有记录日期数，二者都不得把无记录日期补成生理值 0。当天尚未形成完整记录时返回 `partial`，不能写成同步失败。

### 睡眠描述与正式资格

- 兼容保留 `duration_regularity`、`timing_regularity` 及原 `status`，但 `status_scope=descriptive_availability_only`；其中 `eligible` 仅表示能计算窗口描述，不能称为“规律性合格”或“基线可比”。显示名称为“睡眠时长/时点窗口描述（非合格规律性）”。同日相同重复不增加夜数，冲突不计算该维度离散度。
- 正式资格只读取新增的 `qualified_regularity`，复用 `patterns.v1` 的末端 14 日、至少 7 夜合同，不扩窗。`duration_observed_nights`、`timing_observed_nights` 是实际来源有效日数；`sample_status` 只说明样本门，不代表时期门已通过。时期失败关闭后的 `*_valid_nights` 不是来源缺失计数。
- 本地画像没有逐观测设备归属及厂商算法时期证据，故 `qualified=false`、`baseline_comparable=null`；短窗为 `insufficient_window`，足窗仍为 `epoch_unknown`，不得输出正式规律性比较值。调用方给无偏移时间应用时区只支持描述，不能伪装为来源自带偏移；因此正式时点来源计数可能为 0，而描述性时点仍可用。

## 3. 指标血缘与避免重复计数

- HR、HRV 是压力、Body Battery 和部分睡眠指标的共同上游信号。
- Body Battery 还结合活动、休息和睡眠；睡眠评分结合时长、阶段、压力等输入。
- 强度分钟由设备型号、设置、心率区间或步频规则决定；新旧设备计算方法可能不同。
- 因此跨模块只能并列展示“相互一致或不一致的观察”，不能把同源变化累加成置信度、风险概率或总健康分。

## 4. 指导输出合同

画像输出按以下顺序形成建议，但不直接替用户作训练、医疗或日程决定：

1. 数据是否足够新、覆盖是否完整、是否存在佩戴或同步空档。
2. 区分窗口描述与 `qualified_regularity` 的正式资格，再说明睡眠时长、时点与连续性中可观察的变化；不得用描述字段的 `eligible` 推导规律性或基线可比，不设置未经配置的好坏阈值。
3. 体重与已记录活动是否足够新；稀疏或落在窗口外时只报告最近值和记录日期，不伪造趋势或零活动日。
4. 最近 7 日活动强度分布与用户自己的 Garmin 目标是否一致；人口指南比较必须单独满足年龄与意图门禁。
5. HRV 厂商状态、静息心率、压力和 Body Battery 是否出现同日一致变化，同时明确共同血缘与混杂因素。
6. 夜间呼吸/血氧仅在个人时间趋势中描述；持续变化伴随症状时建议携带原始记录咨询合格医疗人员。

禁止输出 `health_score`、`readiness_score`、红黄绿灯、疾病风险分数、强制训练/停训、补剂剂量、会议或工作能力判断。

### 生理底盘与认知续航架构（Physiological Reserve for Cognitive Longevity）

全面画像在分析框架上遵循 `AGENTS.md` §5 `PRIVACY-SESSION-01` 确立的双轮基线，将指标区分为“恢复支撑”与“长期底盘”：
1. **恢复支撑（短窗与周期适应）**：以睡眠结构（各阶段时长、睡眠连续性）与夜间 HRV（7 日均值相对厂商基线区间）评估短期自主神经系统平衡与能量复原状态；
2. **长期底盘（抗衰与长期认知算力）**：
   - **心肺耐力（VO₂max）纵向区间**：在季度或更长周期画像中，追踪心肺估计相对历史基准的稳定性与区间变化，关注心血管耐力对长期脑力输出的承载底盘（严格遵循非诊断边界，不跨跑步/骑行模态混用）；
   - **抗阻/力量训练负荷**：从已记录活动流中提取抗阻力运动天数与负荷累积，评估中长期骨骼肌储备维护情况（无记录不补零，不推断未穿戴活动，不替代专业力量训练规划）。

### 问题导向观察（P1）

画像在原 `garmin-health-profile.v2` 上新增 `problem_insights`（`schema=problem-insights.v1`），只消费本次已经生成的内存摘要，不新增查询、扩窗或保存。固定回答三个问题：睡眠机会与设备估算规律/连续性、HRV/静息心率能否支持恢复比较、活动记录与设备目标能否对照。

每项包括 `id`、`question`、带指标/日期/窗口/覆盖/证据指针的 `observations`、`interpretation`、`qualification`、明确未验证的 `possible_explanations`、`missing_evidence`、`optional_action_ids`、`next_observation_criteria` 及来源/方法信息。升级条件统一放在 `escalation`，各项仅引用，不重复堆叠建议；未复制任意来源正文、活动名称、序列号或本地路径。

- 睡眠时长不等于本人提供的睡眠机会。短窗时长、离散度和设备估算连续性可以描述；正式规律性未知或跨期时，资格仍明确阻断，不称作稳定趋势、好睡眠或临床睡眠效率。
- 当前画像没有 HRV/静息心率比较所需归属、算法和成对历史基线证据，`comparison_status=epoch_unknown`、`baseline_comparable=null`。同日且完整的 Garmin 7 日 HRV 与厂商区间仍可展示，不能称为已经恢复；不同日期指标不伪装成同日比较。
- 最近 7 日强度分钟分别披露中等/剧烈字段覆盖和目标记录日期。只有完整 7 日、两字段都有记录且存在带日期的正值设备目标，才展示完整周目标进度；短请求不补窗。缺少分钟观测时，新观察字段保持 `null`，不把旧汇总的空集合 0 当成真实 0；实际记录的 0 保留。目标存在不证明覆盖完整，也不证明本人仍采用此目标。记录日数不等于全部活动日数，不能据此推断每日分布或没有活动。
- 项目描述可用性考虑已有时长、时点、厂商字段或活动记录证据，与覆盖核验需求分开：缺少时长不抹掉有效时点描述；活动来源不可用时，即使分钟完整也优先核验。事件流无记录或空白日不单独构成覆盖失败，不代表零活动；缺少可选设备目标不抹掉已有分钟或活动记录证据。
- 全局最多两项不重复的可选行动：覆盖缺口先核验；有睡眠观测时可自愿补充睡眠机会/主观困倦；有带日期的设备目标及分钟记录时可自愿核对目标语境。无数据只提示核验，不生成生理结论；没有正式比较资格也不抹掉可用短窗描述。行动不以分数为目标，不提供训练或日程指令。
- 不推定用户已有某种习惯，不自动给出睡眠卫生干预。可选 P2 本人情境输入见下节；长期习惯追踪和 P3 图表渲染未实施，本节不改变年龄/WHO 比较门。

### 本人情境与观察行动复盘（P2，可选）

```bash
<SKILL_PYTHON> scripts/garmin_health_profile.py --days <N> --source local --allow-health-data --context-file <LOCAL_JSON>
```

只有本人主动提供并明确选择的本地 JSON 才传入 `--context-file`。健康权限门通过后读取一次，并在任何数据库路径解析或读取前验证；省略参数时，P1 输出与行为不变。最多读取 131072 字节，记录数不超过请求天数且至多 366 条；UTF-8 JSON、重复键、重复日期、未知字段、错误类型、非有限数、越界或未来日期均失败关闭，不回读补窗。网络路径、映射网络盘、符号链接、重解析点、目录及非普通文件不接受；错误不回显路径或内容，文件读取错误与输入错误分开返回，不伪装为数据库无数据。

封闭输入结构：顶层恰有 `schema_version`（整数 `1`）和 `records`（可为空的数组）。每条必须有请求窗口内的严格 `YYYY-MM-DD` 日期，其余仅允许：

- `sleep_opportunity_minutes`：本人留给睡眠的时间，整数 0–1440，不是设备睡眠时长；不接受布尔、浮点或数值字符串。
- `subjective_daytime_sleepiness`：本人选择的 `low`、`moderate` 或 `high`，不自动推断症状或生成困倦评分。
- `caffeine_last_time`：本人报告的 `HH:MM`，00:00–23:59；只统计有记录日数，不输出原始钟点、不推导时区影响或给出咖啡因截止时间。
- `user_selected_action`：仅允许既有安全观察行动 `observe_sleep_opportunity`，表示自愿观察睡眠机会，不接受干预命令。
- `performed`：可选布尔值，必须同时提供上述行动；`false` 是明确报告未完成，省略是未知，不能补为 `false`。
- `phase`：可选 `baseline` 或 `observation`，必须同时提供上述行动。若有一个行动记录标记阶段，全部行动记录都须标记；按日期排列后基线不能在观察阶段之后重启。没有行动的情境记录不自动分配阶段。不要求凑足阶段数或天数。

不接受 `null`、自由文本、症状正文、URL、嵌入路径、提示词、任意行动或其他字段。合成示例（日期仅用于说明；真实调用必须使用本次请求窗口内本人实际提供的日期，不能照抄为本人事实）：

```json
{
  "schema_version": 1,
  "records": [
    {"date": "2026-09-04", "sleep_opportunity_minutes": 480, "subjective_daytime_sleepiness": "moderate", "user_selected_action": "observe_sleep_opportunity", "performed": false, "phase": "baseline"},
    {"date": "2026-09-05", "sleep_opportunity_minutes": 490, "subjective_daytime_sleepiness": "low", "caffeine_last_time": "13:30", "user_selected_action": "observe_sleep_opportunity", "performed": true, "phase": "observation"},
    {"date": "2026-09-06", "user_selected_action": "observe_sleep_opportunity", "phase": "observation"}
  ]
}
```

新增 `user_context_review`（`schema=user-context-review.v1`）明确标记 `source=USER-REPORTED`，只输出可呈现的最小聚合白名单：窗口、所选行动、已记录/已完成/明确未完成/缺失日数、阶段首末日期和跨度、逐字段覆盖、睡眠机会中位数与主观困倦类别计数。行动缺失日数的分母是请求窗口（阶段内则为显式阶段首末日跨度），不是约定执行计划，不能解释为依从率或未完成次数；阶段首末之间未报告的日期仍是未知，阶段间空白不分配阶段。

- 只有两阶段确有对应字段时，才标为 `descriptive_side_by_side_only`；只有一个阶段或缺少字段时为 `insufficient_evidence`。不计算差值、显著性、相关、疗效或新评分；`effectiveness` 与 `objective_outcome_comparison` 固定 `not_evaluated`。小样本前后并列不能称为改善或有效，完成记录数不等于生理改善。
- 睡眠机会与同日设备时长只在两字段实际存在时并列汇总，使用已有内存行，不新增查询；冲突的设备时长日期排除，缺少配对为 `insufficient_evidence`。同日不保证测量定义相同，不能把差额称为睡眠效率或睡眠负债。本人情境不替代设备/算法时期证据，不解锁正式规律性、恢复比较或趋势。
- P1 睡眠问题链接该聚合证据；已提供字段按覆盖区分剩余缺口，其他观察和资格不变。可选行动仍使用 P1 全局至多两项清单，复盘所选行动不是新增建议。
- 不输出逐日原始情境、原始咖啡因钟点或文件路径；不保存输入副本、状态、历史、跟踪记录或日志，不建立服务。调用方自行管理选定文件，技能不创建或更新它。普通 JSON 输出不自动归档；任何后续保存或分享仍须原有独立授权。

## 5. 非核心或低覆盖模块

- 饮水与汗液：手工录入和设备估算可能混合，覆盖不足时只报告 `insufficient_coverage`，不推断脱水或给补液量。
- 逐活动明细、活动名称/描述、位置、轨迹及原始 FIT/GPX/TCX：继续要求用户明确请求并遵循活动文件授权边界。默认画像只读取不含位置和标识的汇总字段；训练负荷/效果只按 Garmin 厂商值聚合，不生成训练处方。
- Fitness Age、Training Readiness、Training Status：只可展示 Garmin 原始值及新鲜度，不反向重建厂商算法，也不与本画像合成分数。

## 6. 证据与来源

以下资料访问于 2026-08-24，仅用于解释设备字段、方法边界和公共卫生参照：

- [Garmin HRV Status](https://www.garmin.com/en-IE/garmin-technology/health-science/hrv-status/)：7 日平均、约 3 周个人基线及厂商状态语义。
- [Garmin Body Battery](https://www.garmin.com/en-US/garmin-technology/health-science/body-battery/)：HRV、压力、睡眠和活动的共同输入及充放电语义。
- [Garmin Sleep Tracking](https://support.garmin.com/en-IN/?faq=mBRMf4ks7XAQ03qtsbI8J6)：睡眠时长、起止、阶段、呼吸和 Pulse Ox 的设备能力差异。
- [Garmin Intensity Minutes](https://support.garmin.com/en-CA/?faq=pNU9nnDzzGAHmEavp9rpY8)：强度分钟受设备与计算设置影响，剧烈强度可双倍计入目标。
- [Garmin Heart Rate Monitoring](https://www.garmin.com/en-US/garmin-technology/health-science/heart-rate-monitoring/) 与 [VO₂max](https://www.garmin.com/en-GB/garmin-technology/running-science/physiological-measurements/vo2-max/)：腕式心率与心肺估计的来源、模态和个体化限制。
- [WHO 身体活动指南](https://www.who.int/publications/i/item/9789240015128)：18–64 岁成人每周活动建议；只有人口和意图门禁满足时才做参考比较。
- [睡眠规律性专家共识](https://pubmed.ncbi.nlm.nih.gov/37684151/)：睡眠起止规律是独立健康维度，但不提供适用于消费设备的统一阈值。
- [AASM 消费级睡眠技术立场](https://aasm.org/advocacy/position-statements/consumer-sleep-technology/)：消费设备不能替代睡眠疾病诊断或治疗验证。
