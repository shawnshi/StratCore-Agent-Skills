# Weekly Audit Template

本模板用于周度复盘，可按材料和用户目标裁剪。默认只读获取本周日历和本地 Garmin 健康摘要；末日数据不新鲜时，可按主技能新鲜度门启动一次已授权同步任务并披露结果。不得自动读取历史对话或既往日志，并记录所有来源的实际覆盖窗口。七天窗口不足以支持需要至少 28 天的个人趋势时，只报告资格不足，不自动扩窗。

## 自动保存契约

- 明确生成个人日志周审计时，允许按 `personal-diary-writer` 用户授权与范围合同读取当前自然周的 canonical 个人日志日期块；不得扩展到其他周。
- 周审计通过内容门、周期拓扑门和受保护请求门后默认保存。只有精确 canonical 请求或 `AUDIT_AUTOSAVE` 结构化命令可触发；草稿、预览、只读、不保存及其他修饰请求保持只读。
- payload 的第一个非空行且唯一 H2 必须是 `## [YYYY-Www] Weekly Cognitive Audit｜起始日期 至 结束日期`；其余标题只能是 H3 或更深，不得携带日期 H1 或其他 H2。
- 先运行 `audit_gate.py --period-type weekly --period-id YYYY-Www --enforce-template-fields`，再用同一字节 payload、`periodic-audit-request-v1` artifact 和范围回执执行 `diary_ops.py scope/replace --action replace-weekly-audit --week YYYY-Www`。完整保留周期结束日既有日记及其他周期审计；日期块不存在时只创建日期标题与本周审计。写后要求日期标题与目标周审计标题各恰好出现一次。

## 建议内容

```markdown
## [YYYY-Www] Weekly Cognitive Audit｜[起始日期] 至 [结束日期]

### 时间范围与证据
- **周期:** [日期与时区]
- **材料:** [来源及覆盖范围]
- **数据缺口:** [未提供或无法核实的部分]

### 本周关键事实
- [重要事件、产出或约束及证据]

### 承诺对照
| 承诺 | 状态 | 证据 | 偏离原因或未知 |
|---|---|---|---|
| [承诺] | [完成/部分完成/未完成/无法判断] | [证据] | [说明] |

### 重复模式
- **观察:** [按证据量列出；没有可靠重复模式时说明不足]
- **证据强度:** [高/中/低及理由]
- **替代解释:** [外部约束、样本不足或其他可能]

### 时间背景
- **日程:** [默认只读日程能证明安排，不能单独证明出席或实际投入]
- **深度工作块（Deep Work Blocks）:** [记录本周 2–4 小时连续无中断深度思考/输出的时间块数量与完成产出]
- **碎片干扰税（Fragmentation Tax）:** [记录会议、临时杂务或碎片上下文切换造成的打断次数与精力耗损评估]

### 能量管理（描述性生理背景）
- **数据范围与来源:** [请求窗口、实际观测窗口、本地/实时来源]
- **组件覆盖与新鲜度:** [逐组件状态、最近观测日期和缺口]
- **采集审计:** `sync_eligible=<true|false>; sync_attempted=<started|waited_existing|direct|not_attempted>; task_status=<success|failed|timeout|invalid|start_failed|interrupted_or_terminated|not_checked>; local_reread=<accepted|rejected|not_run>; local_status=<complete|partial|no_data|read_error|not_run>; live_fallback=<used|not_used>; reason=<稳定原因码>`
- **睡眠观察:** [时长、阶段占比、躁动和各自观测日期]
- **HRV 与静息心率观察:** [值、原始状态和各自观测日期]
- **Body Battery 与压力观察:** [值和各自观测日期]
- **执行带宽:** `not_scored`；[说明不从健康指标生成认知、职业表现或日程承载评分；主观状态如有则另列来源]
- **睡眠负债:** [来源提供时写 sleep_debt_h、sleep_debt_status=provided_by_source、method、baseline_h 和 window_days；未提供时写 sleep_debt_h=null、sleep_debt_status=not_provided_by_source、method=none、baseline_h=null、window_days=null 及原因]
- **摩擦解构:** [分列本周已记录负荷、主观感受、生理观测、外部约束和未知项]
- **交叉归因:** [只描述时间共现、日期错位和替代解释，不写因果或能力推断]
- **干预指令:** [可选；写触发条件、最小动作和完成标准，由用户结合主观状态决定]
- **数据缺口与不可判断事项:** [包括趋势资格不足；不得扩窗]

### 风险与数据缺口
- [待核实事项]

### 下周行动
1. [触发条件、最小动作、完成标准]
```

周审计的 canonical 自动保存不等于交接授权。只有用户明确要求交接时，才根据 `references/handoff_contract.md` 另加 `Handoff Payload`。不要从缺失材料推断动机、人格或健康结论。
