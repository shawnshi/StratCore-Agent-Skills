# Daily Audit Template

本模板用于单日认知复盘，仅在当前会话中只读交付，可按材料和用户目标裁剪。本模板不具备落盘至 canonical 季度日志（`YYYY-QN.md`）的自动保存路径；若需生成并自动落盘单日事实日志，必须通过 `personal-diary-writer` 八章规范（`# YYYY-MM-DD`）。默认只读获取当日日历和本地 Garmin 健康摘要；末日数据不新鲜时，可按主技能新鲜度门执行一次受控两阶段同步并披露结果。其他联网和来源只使用当前任务明确授权的数据。没有证据的部分写明数据缺口或直接省略。能量管理使用精确单日窗口，不扩窗生成趋势。

## 建议内容

```markdown
# [日期] Daily Audit

## 时间范围与证据
- **时间范围:** [日期与时区]
- **材料:** [用户日志、默认只读日程、默认只读 Garmin 摘要或工作产出]
- **数据缺口:** [没有则删除]

## 关键事实
- [事实及证据位置]

## 承诺对照
| 承诺 | 状态 | 证据 | 外部约束或未知 |
|---|---|---|---|
| [承诺] | [完成/部分完成/未完成/无法判断] | [证据] | [说明] |

## 重复模式与替代解释
- **观察:** [按证据量列出；没有可靠重复模式时说明不足]
- **证据强度:** [高/中/低及理由]
- **替代解释:** [不能排除的因素]

## 日程与时间分配
- **日程背景:** [日程只能证明安排；描述实际窗口、覆盖和缺口]
- **整块深度思考时间:** [记录今日是否有连续 2–4 小时无中断深度思考/架构/写作块，核心产出为何]
- **碎片干扰与精力损耗:** [记录打断源及碎片干扰税评估]

## 能量管理（描述性生理背景）
- **数据范围与来源:** [请求窗口、实际观测窗口、本地/实时来源]
- **组件覆盖与新鲜度:** [逐组件状态、最近观测日期和缺口]
- **采集审计:** `sync_eligible=<true|false>; sync_attempted=<started|waited_existing|direct|not_attempted>; task_status=<success|failed|timeout|invalid|start_failed|interrupted_or_terminated|not_checked>; local_reread=<accepted|rejected|not_run>; local_status=<complete|partial|no_data|read_error|not_run>; live_fallback=<used|not_used>; reason=<稳定原因码>`
- **睡眠观察:** [时长、阶段占比、躁动和观测日期]
- **HRV 与静息心率观察:** [各自值、原始状态和观测日期]
- **Body Battery 与压力观察:** [各自值和观测日期]
- **执行带宽:** `not_scored`；[说明不从健康指标生成认知、职业表现或日程承载评分；主观状态如有则另列来源]
- **睡眠负债:** [来源提供时写 sleep_debt_h、sleep_debt_status=provided_by_source、method、baseline_h 和 window_days；未提供时写 sleep_debt_h=null、sleep_debt_status=not_provided_by_source、method=none、baseline_h=null、window_days=null 及原因]
- **摩擦解构:** [分列今日已记录负荷、主观感受、生理观测、外部约束和未知项]
- **交叉归因:** [只描述时间共现、日期错位和替代解释，不写因果或能力推断]
- **干预指令:** [可选；写触发条件、最小动作和完成标准，由用户结合主观状态决定]
- **数据缺口与不可判断事项:** [日期错位、来源限制或无有效观测]

## 下一步
1. [触发条件、最小动作、完成标准]
```

只有用户明确要求保存或交接时，才根据 `references/handoff_contract.md` 另加 `Handoff Payload`。生成载荷不代表已经写入任何长期存储。
