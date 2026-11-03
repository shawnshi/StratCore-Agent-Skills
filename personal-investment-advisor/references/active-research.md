# Active research workflow

PIA treats faster return-seeking as an evidence and allocation research problem, not as an execution mandate. The active path is offline and fail-closed:

1. `alpha-validate` checks a point-in-time evidence package and promotion policy. It measures out-of-sample, cost-adjusted information ratio, stressed costs, drawdown, turnover, an approximate deflated-Sharpe probability, and a CSCV-style probability of backtest overfitting.
2. `alpha-scan` accepts only a package whose validation report is `eligible_for_active_research`. It applies confidence and evidence-age decay, uncertainty haircuts, and produces Rank/Yank research pools.
3. `portfolio-construct` computes an equal-risk-contribution benchmark from the full supplied covariance matrix, then a bounded robust-alpha candidate under transaction-cost, turnover, and per-name change constraints.
4. `rebalance-proposal` compares current and candidate allocations over an explicit review horizon and no-trade band.

The stable CLI emits a status envelope, not a downstream business report. Use the guarded four-stage example in [command-catalog.md](command-catalog.md) to check successful exits and `status == complete` before extracting `result` to each explicitly authorized output. An incomplete stage must not feed downstream work. Every active entrypoint binds each package, report, and policy digest to the same single-read parsed input consumed by its calculation; canonical JSON hashing is unchanged.

## Personal-investor free-data mode

The default acquisition layer uses free public sources: SEC EDGAR `companyfacts` and filings for US point-in-time fundamentals, exchange/issuer/CNInfo disclosures for A/H shares, Yahoo Finance or Akshare for best-effort market history, and a public broker fee schedule for costs. Paid terminals, licensed academic databases, and sell-side consensus feeds are never assumed.

A free-source package may honestly set `survivorship_bias_control=false` or `corporate_action_adjusted=false`. These booleans are valid inputs, so `alpha-validate` still computes the available experimental metrics; each false value is a failed promotion check and prevents `eligible_for_active_research`. It must not be changed to true merely to satisfy the gate.

SEC EDGAR solves filing availability for US fundamentals but does not itself supply historical index membership or delisting returns. Current constituents therefore remain survivorship-biased unless public historical membership and delisted total returns are independently bound. When promotion is blocked, risk-only `experimental_weight` analysis may still use the separate inverse-volatility workflow; it is not Rank/Yank or an active-alpha candidate.

## Non-negotiable boundary

- Every artifact declares its own `decision_scope` (`research_only` / `advisory` / `actionable`); the calculation pipeline stays read-only with respect to its inputs and never executes orders. Both `research_only` and `advisory` may provide buy/sell inclinations and research recommendations for the user's reference or manual execution, subject to applicable evidence and feasibility gates. It does not modify actual holdings or accounts, directly or indirectly. Separately authorized Dashboard, Thesis, independent risk-policy and skill maintenance follows [SKILL.md](../SKILL.md); holdings import/correction is a distinct explicitly authorized data-maintenance task, not an advisory side effect. Changed inputs require new calculations and bindings, not retrospective edits to archived passing evidence.
- Candidate weights and allocation gaps are permitted only after the P0 validation gate passes. They must be labelled `candidate_weight` or `allocation_gap`. `target_weight` is permitted in `advisory` or `actionable` proposals after the same P0 gate; it is a proposed state, never an actual-holdings writeback. Experimental weights remain experimental until their promotion gates pass.
- No active-research calculation command may place, schedule, route, or simulate an order; infer missing holdings; fetch mutable live data; or overwrite an input. Free-source acquisition occurs beforehand through a separate evidence command and its immutable output hash is then bound offline.
- A failed contract, stale component, unbound upstream hash, non-PSD covariance matrix, infeasible constraint set, or optimizer non-convergence fails closed.
- Expected alpha, covariance, costs, and horizons are assumptions. Passing a statistical gate does not establish future profitability.

## Input contracts

- Alpha package: `references/alpha_evidence_schema.json`
- Promotion policy: `references/alpha_promotion_policy_schema.json`
- Scan policy: `references/active_scan_policy_schema.json`
- Construction policy: `references/active_construction_policy_schema.json`
- Proposal policy: `references/rebalance_proposal_policy_schema.json`

All datetimes must be timezone-aware. Source evidence must use a non-test public, `sec://`, or user-controlled `dataset://` locator and a lowercase SHA-256. The package must explicitly report point-in-time evidence and boolean survivorship/corporate-action states. `false` means experimental evidence, not malformed input; both values must be `true` before promotion.

## Numerical contracts and migration

- The selected trial must match `gross_return - benchmark_return - turnover * total_cost_bps / 10000` at every observation, including in-sample rows. The absolute tolerance is `1e-12` in fractional returns, with zero relative tolerance. A mismatch is invalid input and blocks promotion. After reconciliation, DSR and PBO consume the exact recomputed selected sequence. Existing packages must be reconciled against their actual cost evidence, not made eligible by changing the promotion policy.
- New construction policies require `covariance.annualized: true`. The matrix must already be annualized covariance of fractional returns, not percentage returns or daily/monthly covariance. The constructor performs no implicit frequency conversion. The caller must verify frequency, return scale, and the annualization method in the hash-bound source dataset before setting the flag. For example, multiplying daily covariance by a verified annual observation factor is appropriate only when the adopted aggregation assumptions justify that scaling; the flag alone is not evidence of those assumptions.
- Archived policies remain untouched. To reuse one for new construction, create an explicitly authorized input with verified annualized units and the required flag; a missing, false, numeric, or string flag fails closed. The v1 schema identifier is retained, but this required field tightens the new-input contract.
- After turnover scaling, final active weights are checked for finiteness, sum of one, minimum/maximum bounds, per-name change cap, and one-way turnover (absolute numerical tolerance `1e-10`, independent of optimizer tolerance). Conflicts return no candidate rather than relaxing policy. This conservative post-check is not a joint turnover-constrained optimizer: it may reject a scaled result even when a different feasible allocation exists. Bounded ERC remains a risk benchmark, not the final turnover-constrained active allocation.

## Personal-use resource capacities

Limits are inclusive: each active JSON input is at most 32 MiB (33,554,432 UTF-8 bytes); construction accepts at most 250 assets and a 250 × 250 dense covariance matrix. Alpha validation retains the 1,000-trial ceiling and adds 10,000 observations per series and 1,000,000 total trial-return cells. The observation allowance covers about 40 daily trading years; the combined cell budget prevents multiplying both axis ceilings. The existing 100,000 optimizer-iteration ceiling and 4–12 even PBO blocks remain unchanged. These are capacity ceilings, not latency guarantees.

Readers consume at most the byte limit plus one before decoding, so file growth cannot bypass the cap. Dimension checks run before numeric-series copies or dense matrix allocation/eigendecomposition. Over-limit inputs produce explicit `size_limit` errors, never truncation or `no_data`. The schemas retain their v1 identifiers; within-cap formats and canonical hashes are unchanged. Oversized archives remain untouched and require a separately authorized preparation step before reuse; there is no automatic splitting, migration, or archiving.

Bounded simplex bisection stops when the clipped sum differs from one by at most `1e-14`, or the floating-point midpoint stagnates; its 200-iteration guard and residual correction remain. Monotonic clipping bounds each coordinate's projection error by the mass residual (apart from floating-point rounding). This internal accuracy is stricter than the unchanged `1e-10` final constraint checks; output weights remain rounded to 12 decimal places. Risk-budget, turnover, and convergence policies are not relaxed.

## Interpretation

`alpha-validate` now exposes `validation_scope=submitted_package_consistency_only`, `control_evidence_status=declared_not_independently_reconstructed` and `capital_deployment_approved=false`. Fewer than 60 out-of-sample observations produces an additional fragility warning; 60 is a diagnostic threshold, **not** a sufficient sample size or a new promotion rule. Before any real-capital decision, independently reconstruct historical constituents and delisted returns, corporate actions, filing availability, trial ledger completeness, embargoed out-of-sample splits and buy/sell-side cost assumptions. If those cannot be verified, retain experimental interpretation even if the supplied package passes its numerical policy. This review does not grant a skill permission to trade.

`eligible_for_active_research` means that the submitted experiment cleared the supplied promotion thresholds. It does not mean approved for capital deployment. Rank/Yank is an attention-allocation device; the Yank pool is a review list, not a sell list. The native final proposal remains non-executable research output. An `advisory` report may separately provide concrete manual-execution parameters after the applicable quote, rule, resource and cost checks, with validity, triggers, invalidation and downside stated. Incomplete checks permit only explicitly conditional/pending parameters, not an immediately executable claim. Parameter inclusion alone does not change the report to `actionable`; action-level readiness and actual execution remain subject to separate human governance outside this skill. Neither scope writes actual holdings or executes orders.
