# QA SOP/KPI Audit Rules

## Role Split

Business owner scores:

- 业务交付质量与效能：30 分
- 重点工作：25 分

Testing supervisor scores:

- 测试专业能力与规范执行：45 分

Final score is summarized by the testing supervisor. For business delivery and key work, the aggregated score must not be higher than the business owner score.

## KPI Scorecard

Final score must be calculated from the three top-level modules and their child indicators. Do not estimate the final score only as `100 - total deductions + bonus` unless the module scores below have also been reconciled.

### 业务交付质量与效能，30 分

| 指标项目 | 满分 | 评分规则 |
|---|---:|---|
| 保障项目交付节奏与跨团队协作效率 | 15 | 1. 提测前无法产出测试用例，单月每次扣 2 分，超过 3 个共计扣 5 分；2. 因测试原因影响项目节奏，1 次扣 3 分；3. 提测后主流程阻塞，影响测试推进，1 次扣 1 分；4. 响应不及时累计 3 次及以上扣 5 分；5. 单月时效测试工日 >=25 天加 1 分，>=29 天加 3-5 分。 |
| 提前暴露需求缺口、技术风险和交付验收风险 | 5 | 1. 未推动需求缺口、技术风险闭环，导致验收阶段风险暴露，1 次扣 1 分；2. 验收阶段发现测试逃逸问题，1 个扣 1 分，涉及主流程扣 5 分。 |
| 保障上线后业务运行稳定性 | 10 | 1. P2/P3 线上漏测 Bug 累计 2 个扣 3 分；2. P1 线上漏测 Bug 1 个扣 5 分；3. P0 线上漏测 Bug 1 个扣 10 分。 |

### 重点工作，25 分

| 指标项目 | 满分 | 评分规则 |
|---|---:|---|
| 重点需求1 | 15 | 1. Bug 未记录、Jira Bug 提单不符合规范，扣 1 分，超过 5 个共计扣 5 分；2. 测试场景遗漏导致验收未通过，扣 5-10 分。 |
| 重点需求2 | 10 | 1. Bug 未记录、Jira Bug 提单不符合规范，扣 1 分，超过 5 个共计扣 5 分；2. 测试场景遗漏导致验收未通过，扣 5-10 分。 |

### 测试专业能力与规范执行，45 分

| 指标项目 | 满分 | 评分规则 |
|---|---:|---|
| 完成需求分析、影响范围识别和测试设计沉淀 | 15 | 1. 用例文档中未记录产品需求理解或技术方案理解，扣 1 分；2. 用例文档全局影响面评估缺失，或需覆盖项未转化为用例，扣 1-3 分；3. 用例未编写，1-3 次每次扣 3 分，超过 3 次该项不得分。 |
| 完成测试用例设计、用例评审和执行记录 | 15 | 1. 用例评审不通过，单月 1-3 次每次扣 3 分，超过 3 次该项不得分；2. 测试进度、测试日报或测试结论未留痕，1 次扣 2 分。 |
| 严格执行质量门禁和缺陷闭环 | 15 | 1. 标准流程未输出测试报告，或简化流程未同步测试完成结论，1 次扣 3 分；2. 准入、冒烟、准出等关键门禁未检查或无留痕，1 次扣 5 分；3. 阻塞准出的关键缺陷未通报、未推动修复或未闭环，1 次扣 3 分。 |

## Out-of-Scope Bug Rule

If a bug is outside the current test scope, do not count it as testing responsibility when all conditions are met:

- PRD, technical plan, test plan, use case, report, Jira, or Lark clearly says the area is out of current scope.
- The limitation or residual risk was synchronized before acceptance/release.
- Product, development, project manager, or business side accepted the scope/risk.

Count it as testing responsibility when:

- The area was actually impacted by the current change but testing failed to identify it.
- Testing did not document or synchronize the scope limitation.
- The problem belongs to core flow, key interface/data, permissions, exception path, compatibility, or acceptance criteria that should have been covered.

## Business Delivery Quality and Efficiency

This top-level module is worth 30 points:

- 保障项目交付节奏与跨团队协作效率：15 points.
- 提前暴露需求缺口、技术风险和交付验收风险：5 points.
- 保障上线后业务运行稳定性：10 points.

## Workload Calendar Rules

- Testing cycle and equivalent testing workdays exclude weekends and Singapore public holidays by default.
- If Jira/Lark has an explicit weekend testing progress note, count that weekend date as an effective testing workday.
- In exported sheets, weekend override dates can be provided in `周末测试进度日期`, `周末有效工作日`, `额外有效工作日`, `周末测试日期`, or `周末备注测试日期`.
- Bonus rule: single-month equivalent testing workdays >= 25 and < 29 suggests +1 point; >= 29 suggests +3-5 points, with the exact bonus confirmed by the supervisor.
- Bonus eligibility still requires no major delivery incident, no P0/P1 online missed bug, and no testing-side delay.
- Output field `当月工时统计/天`: the tester's monthly equivalent testing workdays after excluding weekends/Singapore public holidays and adding explicit weekend testing-progress dates.
- For Jira live scans, calculate workload from the planned testing window: `预计测试开始时间` through `预计测试完成时间`. Actual completion comments and `已测试` status transitions are delivery-timeliness evidence only and must not expand workload bonus days by default.
- If Jira/Lark explicitly updates the planned testing schedule with non-testing-side or project-accepted wording such as `测试时间顺延` or `测试完成时间更新`, use the updated `预计测试完成时间` as the planned end date.
- If actual completion is later than the planned end date, keep workload calculated through `预计测试完成时间`; use the extra days only when judging whether testing was overdue.
- Output field `加分项`: output `加 1 分`, `建议加 3-5 分`, or `-`.
- Output row-level field `月度工作量加分在汇总项统计` as `全部有效统计工作日 N 天`; keep the bonus score only in the monthly summary/deduction-bonus table.
- In the monthly bonus row, include the threshold text: `全部有效统计工作日 N 天，>=25 天` with `+1 分`, or `全部有效统计工作日 N 天，>=29 天` with `3-5 分，由主管根据本月表现判断`.

### 保障项目交付节奏与跨团队协作效率

Check each scoring standard separately. This indicator is worth 15 points.

1. 提测前无法产出测试用例
   - Evidence field: `提测前完成测试用例产出`.
   - Satisfied: before the planned test start (`预计测试开始时间`), Jira/Lark contains a test case link, smoke case link, or explicit test point link that can support testing. If planned test start is absent, use the first actual transition into testing as the fallback boundary.
   - Not satisfied: no test case/test point link is recorded before the planned test start or fallback test-entry boundary, or the record only says "有" without a traceable link/location.
   - Deduction: monthly each occurrence deducts 2 points; more than 3 demands caps this item at 5 points deducted.

2. 因测试侧原因影响项目节奏
   - Satisfied: test-side work does not delay agreed project schedule.
   - Not satisfied: test-side missed action, delayed execution, missing evidence, or unhandled blocker causes schedule impact.
   - Deduction: 3 points.

3. 提测后主流程阻塞，影响测试推进
   - Satisfied: main flow is testable after submission, or blocker is quickly synchronized and handled.
   - Not satisfied: main flow blocks testing progress after submission due to missing test-side gate or follow-up.
   - Deduction: 1 point.

4. 响应不及时累计 3 次及以上
   - Satisfied: response meets team expectation.
   - Not satisfied: delayed response reaches 3 confirmed instances in the month.
   - Deduction: 5 points.

5. 单月时效测试工日
   - Effective testing workdays >= 25 and < 29: add 1 point.
   - Effective testing workdays >= 29: add 3-5 points, with the exact bonus decided by the supervisor based on monthly performance.

### 提前暴露需求缺口、技术风险和交付验收风险

1. 未推动需求缺口、技术风险闭环，导致验收阶段风险暴露
   - Satisfied: known requirement gap or technical risk was synchronized and pushed to owner/time conclusion.
   - Not satisfied: known risk was not escalated or closed before acceptance.
   - Deduction: 1 point each.

2. 验收阶段发现测试逃逸问题
   - Satisfied: no acceptance issue that should have been covered by testing.
   - Not satisfied: acceptance finds a missed test issue.
   - Deduction: 1 point each; main-flow impact deducts 5 points.

### 保障上线后业务运行稳定性

- P2/P3 online missed bugs: cumulative 2 deduct 3 points.
- P1 online missed bug: 1 deducts 5 points.
- P0 online missed bug: 1 deducts 10 points.

## Key Work

This top-level module is worth 25 points:

- 重点需求1：15 points.
- 重点需求2：10 points.

Apply per key demand.

1. Bug 未记录、Jira Bug 提单不符合规范
   - Satisfied: bug has clear title, repro steps, actual/expected result, severity/priority, owner/status.
   - Not satisfied: missing bug record, empty description, external-link-only description, one-line phenomenon only, unclear repro, missing actual/expected result, or development cannot reproduce based on description.
   - Deduction: 1 point per non-compliant Bug record, capped at 5 points when more than 5 non-compliant Bug records are found. For KPI scoring, check every associated Bug under the demand, not a sample.

2. 测试场景遗漏导致验收未通过
   - Satisfied: no acceptance failure caused by missed test scenario.
   - Not satisfied: missed test scenario causes acceptance failure, major rework, or release blocking.
   - Deduction: 5-10 points, based on the severity confirmed by the business owner/supervisor.

## Testing Professional Capability and SOP Execution

### 1. 完成需求分析、影响范围识别和测试设计沉淀，15 分

1. 用例文档中未记录产品需求理解或技术方案理解
   - Satisfied: use-case document records product or technical understanding with actual analysis content, and review has no obvious deviation.
   - Not satisfied: no understanding record, only section headings, only Jira/PRD/TRD links without analysis content, or product/development points out obvious misunderstanding.
   - Deduction: 1 point.

2. 用例文档全局影响面评估缺失，或需覆盖项未转化为用例
   - Evidence field: `全局影响面评估分析是否完整`.
   - Satisfied: impact assessment exists, and every row marked `本次需求是否涉及=是` and `是否需要用例覆盖=是` has a concrete impact-point description in `具体影响点/验证要求/待确认人`, and those covered items are reflected in cases/test points. Verification requirement and owner are helpful but not mandatory.
   - Not satisfied: impact assessment missing/incomplete, any covered row lacks a concrete impact-point description, or covered item not converted.
   - Deduction: 1-3 points.

3. 测试用例内容为空或无效
   - Evidence field: `测试用例是否编写`.
   - Satisfied: `六. 测试用例` contains actual test points, executable scenarios, a non-empty case table, or a visible mindmap/whiteboard/image with case nodes.
   - Not satisfied: only the section title, template warning text, empty table, placeholder, or unreadable/blank case link is present.
   - Deduction: treat as use-case design missing/invalid for this demand. Add row-level fact `测试用例内容无效`.

4. 用例未编写
   - Evidence field: `测试用例是否编写`; use `提测前完成测试用例产出` only to decide the separate delivery-efficiency item `提测前无法产出测试用例`.
   - Satisfied: a traceable test case, smoke case, executable test point, or valid test-report execution record exists by the end of the demand, even if it was recorded after test completion.
   - Not satisfied: no traceable test case, smoke case, executable test point, or valid test-report execution record exists by the end of the demand.
   - Important boundary: `用例晚于测试完成` or `提测前未见用例产出` must not be counted as `用例未编写` when a final valid case/test-point/test-execution record exists. Count it only under `提测前无法产出测试用例`.
   - Deduction: 1-3 occurrences deduct 3 points each; more than 3 occurrences means this item gets 0 points.

Deduplication:

- If "用例未编写" is deducted for a demand, do not repeatedly deduct requirement understanding, impact assessment, or coverage conversion for that same demand.

#### Product/Technical Understanding Validity Rule

Do not judge the understanding sections as valid only because the document has headings.

For `产品需求理解与确认`, the section is valid only when it contains actual content under the PRD/Jira/product information, such as:

- Tester's understanding analysis.
- Feature/module split.
- Scope confirmation.
- Key business rules.
- Confirmation points or pending questions.

Examples:

```text
Jira单：https://jira.weex.tech/browse/WWLD-14454
PRD（产品需求文档）: KYT新厂商接入【PRD】
产品：RAD-CRU-Melon
理解分析描述：KYT接入新的厂商(elliptic)，同时可支持在后台灵活配置。可分为两个功能模块：
一：后台配置页面
二：KYT新厂商风险判定流程及lark告警是否正确
```

This is valid because it has actual understanding analysis after the PRD information.

If the section only contains:

```text
Jira单：...
PRD（产品需求文档）: ...
产品：...
```

then mark:

```text
有 PRD 链接，但产品需求理解与确认内容不足
```

For `技术方案理解与确认`, the section is valid only when it contains actual technical understanding or confirmation content under the TRD/developer information, such as:

- Technical implementation summary.
- Interface/data/rule changes.
- Important constraints.
- Self-test or TRD conclusions relevant to testing.
- Technical risk or verification focus.

If it only contains TRD link and developer name, mark:

```text
有 TRD 链接，但技术方案理解与确认内容不足
```

Use these result labels:

- `产品需求理解与确认：有，且有实际理解分析内容`
- `产品需求理解与确认：内容不足`
- `产品需求理解与确认：缺失`
- `技术方案理解与确认：有，且有实际理解分析内容`
- `技术方案理解与确认：内容不足`
- `技术方案理解与确认：缺失`

#### Global Impact Assessment Validity Rule

For `四. 全局影响面评估`, do not pass only because the table exists.

Check each impact row. When both conditions are true:

```text
本次需求是否涉及 = 是
是否需要用例覆盖 = 是
```

then `具体影响点/验证要求/待确认人` must contain a concrete impact-point description, such as:

- Specific affected function or link.
- Verification requirement, risk/limitation, owner, or confirmation person can be included, but they are not mandatory when a concrete impact point is already present.

If a row is marked involved and needs case coverage, but the concrete impact-point description is empty or only has placeholders, mark:

```text
全局影响面评估不完整：涉及且需覆盖的影响项缺少具体影响点
```

If all involved + covered rows have concrete descriptions, mark:

```text
完整：涉及且需覆盖的影响项均有具体影响点
```

If no impact assessment section/table is found, mark:

```text
缺失：未见全局影响面评估
```

If the document cannot be fully read, mark:

```text
待确认：用例文档可打开，但全局影响面评估表读取不完整
```

#### Test Case Content Validity Rule

For `六. 测试用例`, do not judge the test case as effective only because the heading exists or the template warning text exists.

Valid case content includes:

- Actual test points or executable scenarios.
- A non-empty case table.
- Table-style test cases with concrete rows and columns such as `用例ID`, `场景`, `前置条件`, `操作`, and `预期结果`.
- A mindmap, whiteboard, or embedded image with visible case nodes/branches.
- Flow/rule/data/exception verification points that can guide execution.

Invalid case content includes:

- Only `六. 测试用例` title.
- Only template text such as `测试用例不是简单罗列操作步骤...`.
- Empty table, placeholder, or blank embedded object.
- A table that only has headers such as `用例ID/场景/前置条件/操作/预期结果` but no concrete case rows.
- Link can open but contains no real test design content.

Use these result labels:

- `有效`
- `无效：画板为空`
- `缺失用例`
- `待确认：章节未展开`

### 2. 完成测试用例设计、用例评审和执行记录，15 分

1. 用例评审不通过
   - Satisfied: review passes, or review issues are revised and confirmed closed.
   - Exception: when `Story Points <= 3` or the demand is classified as `简化流程`, use-case review is not required. The simplified evidence requirement is a test completion conclusion and acceptance note.
   - Not satisfied: rejected due to testing-side use-case quality, such as missing core flow, interface data, boundary condition, exception path, permission, or acceptance scenario.
   - Evidence wording: `用例/评审记录` must explicitly say `用例评审通过` or `用例评审不通过` when the review conclusion is visible. If only a review trace exists but the result is unclear, write `未见用例评审结论`.
   - Deduction: monthly 1-3 occurrences deduct 3 points each; more than 3 occurrences means this item gets 0 points.

2. 测试进度、测试日报或测试结论未留痕
   - Satisfied: Jira/Lark/report/use-case execution record shows current progress, risks, and conclusion.
   - Not satisfied: no traceable progress, daily report, or conclusion.
   - Deduction: 2 points each; within same demand, only deduct once for trace issue.

### 3. 严格执行质量门禁和缺陷闭环，15 分

1. 标准流程未输出测试报告，或简化流程未同步测试完成结论
   - Satisfied: standard flow has test report; simplified flow has Jira/Lark completion conclusion. For simplified-flow demands whose testing starts before `2026-07-01`, concise completion handoff notes such as `测试进度100%`, `stg测试完成`, `stg验证通过`, `测试完成，请产品验收`, `测试完成 产品已同步验收`, `测试完成 麻烦[~xxx]` / `测试完成 请@xxx`, or `验证完成，可以发布` count as valid completion conclusions.
   - Not satisfied: missing required report/conclusion.
   - Deduction: 3 points.

2. 准入、冒烟、准出等关键门禁未检查或无留痕
   - Satisfied: admission, smoke, and release gate are checked and traceable.
   - Not satisfied: any key gate is not checked or has no trace.
   - Deduction: 5 points.
   - For standard-flow demands, missing developer self-test evidence (`自测报告`, `自测文档`, `自测结果`, `提测报告`, or equivalent submission self-test evidence) counts as a gate-trace miss and should be deducted under this KPI item.
   - Other gate evidence such as `准入检查`, `冒烟通过`, `准出检查`, or explicit Jira/Lark gate comments may prove additional gate execution, but does not offset a missing required self-test/submission evidence item when the team KPI requires it.

3. 阻塞准出的关键缺陷未通报、未推动修复或未闭环
   - Satisfied: blocking issue is synchronized, assigned, tracked, fixed/risk-accepted, and closed with regression or status evidence.
   - Not satisfied: missing notification, no push, or no closure.
   - Deduction: 3 points.

## Monthly Aggregation

- Use single month as the scoring period.
- Count by demand.
- Multiple demands count separately.
- Same issue in same demand deducts once.
- Cap each 15-point item at 15 points deducted.
- Keep a "manual confirmation" list for unclear responsibility, missing evidence, out-of-scope claims, and duplicate events.
- Workload overload protection: calculate one tester's monthly equivalent testing workdays from planned testing windows, excluding weekends and Singapore public holidays. Mark workload as overloaded only when monthly equivalent testing workdays are > 28.
- Workload bonus: monthly equivalent testing workdays >= 25 and < 29 suggests +1 point; monthly equivalent testing workdays >= 29 suggests +3-5 points, with the exact bonus confirmed by the supervisor. Bonus eligibility still requires no major delivery incident, no P0/P1 online missed bug, and no testing-side delay.

## Process Type Rule

When `流程类型` is absent or unclear, infer process type by the team rule below.

Standard flow (`标准流程`) if any condition is met:

- Issue title contains `okr` or `OKR`.
- Jira `Story Points` > 3.
- Testing cycle > 2 working days.
- `业务模块 = 数仓` and the demand has a tester owner/tester intervention record.
- The tester is in the default `数仓组` roster and the title/module clearly belongs to 数仓与风控, such as `风控`, `数据服务`, `监控系统`, `标签后台`, `审核系统`, `资运`, `KYT`, `提币审核`, `充值`, or `提现审核`.

Simplified flow (`简化流程`) if no standard-flow condition is met and any condition is met:

- Issue title contains `快速优化`.
- Jira `Story Points` <= 3.
- Testing cycle <= 1 working day and `Story Points` < 3.

Otherwise mark `待确认`.

## Test Report / Test Conclusion Rule

For `测试报告`, use only these labels:

- `有测试报告`: a full test report body or clear test report link exists.
- `有测试结论`: test scope/result/risk or residual conclusion is clear, but no full report link is visible. For simplified-flow demands before `2026-07-01`, `测试完成` / `测试通过` plus `测试记录` / `测试内容`, `测试进度100%`, or concise environment / handoff conclusions such as `stg测试完成`, `stg验证通过`, `测试完成，请产品验收`, `测试完成 产品已同步验收`, `测试完成 麻烦[~xxx]` / `测试完成 请@xxx`, or `验证完成，可以发布` also count as a test conclusion.
- `仅测试完成备注`: only short completion text is visible, such as `测试完成`, `验证通过`, `待发布`, `已发布`, or `已上线`.
- `缺测试报告/结论`: neither a report nor a clear conclusion is visible.
- `待确认：链接无法打开`: a candidate link exists but cannot be opened or verified.

For standard flow, only `有测试报告` satisfies the test-report requirement. `有测试结论` and `仅测试完成备注` are insufficient for standard flow unless an approved exception is explicitly recorded. For simplified flow, `有测试结论` satisfies the completion-evidence requirement. A comment with only isolated `测试完成` remains `仅测试完成备注`; before `2026-07-01`, completion comments with environment,验收/发布交接, or explicit next-handler mention are normalized to `有测试结论`.

## Board/Whiteboard Evidence Boundary

If a Lark test-case document is a board/whiteboard and the app can only confirm the board object exists but cannot read node text, mark `待确认：画板节点不可读`. This is an evidence-completeness limitation, not an automatic deduction for missing test cases, missing product/technical understanding, or incomplete impact assessment. Deduct only after manually opening the board and confirming the content is actually missing or insufficient.

## Self-Test / Submission Evidence Rule

For `自测报告`, use only these labels:

- `有自测报告`: Jira/Lark comments, attachments, or adjacent link text explicitly contains `自测报告`, `自测文档`, `自测结果`, `提测报告`, or `提测文档`.
- `缺自测报告`: no explicit self-test/submission-report label is present. A bare URL, PRD/TRD link, product self-test note, or unlabeled document link must be treated as missing, not `待确认`.
- `待确认：链接无法打开`: a link explicitly labeled as self-test/submission-report exists but cannot be opened or verified.

For standard-flow demands, missing self-test/submission evidence counts as a gate-trace miss under `严格执行质量门禁和缺陷闭环`.

## Formal Output Contract

Formal monthly KPI audit output must use these sections:

```text
一、月度结论摘要

二、扣分/加分建议

三、关键确认项

四、逐单检查表
```

The `二、扣分/加分建议` table columns are:

```text
结论 | 项目 | 问题 | 建议
```

The `一、月度结论摘要` section must include a module score table before detailed deductions:

```text
本次审计范围为 <tester> 在 <YYYY-MM> 的 Jira/Lark 记录，共 <N> 个需求。

当前明确测算得分为 <score>/100，其中：

| 模块 | 得分 | 主要依据 |
|---|---:|---|
| 业务交付质量与效能 | <score>/30 | <deduction/bonus basis> |
| 重点工作 | <score>/25 | <deduction basis or 暂未确认重点需求范围，Bug 规范问题暂不计入扣分> |
| 测试专业能力与规范执行 | <score>/45 | <deduction basis> |
| 合计 | <score>/100 | 明确扣 <N> 分，加 <N> 分 |
```

After the table, include only score-changing pending items in one sentence. Generate pending Jira keys from the current audit evidence only; do not reuse example keys from prior audits. Do not mix evidence/tool limitations into the score sentence.

The `四、逐单检查表` columns are:

```tsv
时间	JIRA单	状态	流程类型	实际测试完成	提测前完成测试用例产出	用例/评审记录	测试用例是否编写	全局影响面评估分析是否完整	自测报告	测试报告	验收/线上问题	风险同步/闭环记录	Bug记录是否规范	月度工作量加分在汇总项统计	扣分项
```

Row-level `月度工作量加分在汇总项统计` must contain the monthly total only, such as `全部有效统计工作日 25 天`; the bonus score appears only in `二、扣分/加分建议`.

Formal output must not use weak wording:

- Do not use `疑似不规范`. Use `不规范` only after checking Bug details; otherwise use `关联 Bug N 个；待确认：Bug详情未打开`.
- Do not use `画板未读`. Use `待确认：内容无法读取`.
- Do not use generic row-cell `缺失` when a specific label exists.
- Do not use `有用例评审记录`; use `用例评审通过`, `用例评审不通过`, or `未见用例评审结论`.

## Output Wording Rule

Keep row-level and monthly-level wording separate.

Monthly summary rows must use exact issue counts and concrete evidence. Do not write vague quantities such as `多单`, `多个`, `部分需求`, or `若干需求`. For test-report and gate-evidence issues, write the exact count, affected Jira keys, and missing deliverables in the same row, for example:

```text
标准流程测试报告/门禁证据不足 2 单：WWLD-13340、WWLD-10242；缺失产出物：自测报告/提测自测证据、完整测试报告，仅见测试完成备注
```

Row-level `扣分项` should only record the factual miss for the demand:

- `提测前未见用例产出`
- `未见用例/评审记录`
- `全局影响面评估不完整`
- `未见自测报告`
- `缺测试报告/结论`
- `仅测试完成备注`
- `待确认：链接无法打开`
- `验收/线上问题待确认`
- `Bug记录不规范`
- `无`

For `Bug记录是否规范`, use row-level wording like:

- `无关联Bug`
- `关联 Bug N 个；规范 X 个，不规范 Y 个；主要问题：缺复现步骤、缺实际结果、缺预期结果`
- `关联 Bug N 个；规范 X 个，不规范 Y 个；主要问题：描述为空、仅贴外部链接`

Do not write monthly threshold conclusions into a row, for example:

- Do not write `提测前未产出用例，累计超过 3 个需求，扣 5 分` in each row.
- Do not write `用例未编写超过 3 次，该项不得分` in each row.

Monthly threshold conclusions belong only in the monthly summary, for example:

- `提测前未见用例产出共 X 个需求，超过 3 个，按规则本项扣 5 分。`
- `最终未见有效用例沉淀共 X 个需求，超过 3 次，“完成需求分析、影响范围识别和测试设计沉淀”项建议不得分。`
