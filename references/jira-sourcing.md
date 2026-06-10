# Jira/Lark Monthly Demand Sourcing

Use this reference only for monthly demand sourcing and evidence collection. Do not maintain KPI scoring rules here; use `references/sop-rules.md` for all pass/fail, deduction, bonus, and wording decisions.

## Default Scope

Primary monthly scope:

```text
测试介入时间 >= target month start
AND 测试介入时间 < next month start
AND 测试介入人 = target tester
```

Use `测试介入时间` as the default monthly filter, not Jira issue created time, resolved time, release time, or current status update time.

When the user provides a tester/person/group plus a target month, default to Jira/Lark live scan. Do not first search local files or ask for a CSV/TSV.

Use offline file/table mode only when the user explicitly says one of:

```text
使用本地文件
导出表
CSV
TSV
粘贴数据
种子列表
```

## Live Access Gate

For tester/month KPI audits, use this fixed access order and do not branch into local files unless the user explicitly requested offline mode:

1. Use the available browser-control tool to operate the user's logged-in browser session.
2. If browser-control is unavailable, try an authenticated Chrome/CDP session only when it is already accessible from the current runtime.
3. Verify login before any audit work:
   - open a known Jira issue such as `https://jira.weex.tech/browse/WWLD-12494`, or run an authenticated Jira search;
   - confirm the response can see WWLD project data and is not `anonymous`;
   - confirm Jira comments/links are visible enough to collect SOP evidence.
4. If login/session verification fails, stop the live audit and report:

```text
无法实时扫描 Jira/Lark：当前会话未取得已登录 Jira 权限。
需要用户在可被 Codex 控制的浏览器中打开并登录 Jira，或明确提供 Jira/Lark 导出表后改走离线审计。
```

Do not continue with anonymous Jira API data. Do not use old local TSV/CSV files as a replacement for live scan.

## Default Jira Query

Use Jira `cf[]` field ids by default. Do not use Chinese custom-field names as the first attempt, because field display names, locale, and punctuation can drift.

Confirmed Jira field mapping:

| Business field | REST field | JQL field |
|---|---|---|
| 测试人员（多选） | `customfield_11622` | `cf[11622]` |
| 预计测试开始时间 | `customfield_12304` | `cf[12304]` |
| 预计测试完成时间 | `customfield_11617` | `cf[11617]` |

Default monthly KPI live-scan JQL:

```jql
project = WWLD
AND cf[11622] in ("<tester>")
AND cf[12304] >= "<month_start>"
AND cf[12304] < "<next_month_start>"
ORDER BY cf[12304] ASC, key ASC
```

Use `maxResults=1` and a strict field whitelist for the first probe:

```text
key,summary,status,customfield_11622,customfield_12304,customfield_11617
```

If the default JQL returns results and `customfield_11622` contains the target tester, use the same JQL for the full paged scan.

If the default JQL returns 0 results, probe only the tester-value syntax in this order. Keep the project and date conditions unchanged:

```jql
project = WWLD AND cf[11622] = "<tester>" AND cf[12304] >= "<month_start>" AND cf[12304] < "<next_month_start>" ORDER BY cf[12304] ASC, key ASC
project = WWLD AND cf[11622] in ("<display_name>") AND cf[12304] >= "<month_start>" AND cf[12304] < "<next_month_start>" ORDER BY cf[12304] ASC, key ASC
project = WWLD AND cf[11622] = "<display_name>" AND cf[12304] >= "<month_start>" AND cf[12304] < "<next_month_start>" ORDER BY cf[12304] ASC, key ASC
```

Only if all `cf[]` probes fail due to JQL syntax or field-value errors, try the Chinese-name fallback:

```jql
project = WWLD
AND "测试人员（多选）" in ("<tester>")
AND "预计测试开始时间" >= "<month_start>"
AND "预计测试开始时间" < "<next_month_start>"
ORDER BY "预计测试开始时间" ASC, key ASC
```

Do not use `created`, `resolved`, status transition date, Jira assignee, reporter, or creator as the monthly scope filter unless the user explicitly changes the audit口径.

If the tester field is unreliable after these probes, use the QA schedule/Lark monthly demand list or a user-provided `测试介入时间 + JIRA单` seed list as the scope source, then enrich each Jira issue individually.

## Default KPI Tester Roster

Exclude Jonathan accounts by default unless explicitly requested:

```text
jonathan107404
jonathan107838
```

Default KPI tester roster:

| Jira username | Display name |
|---|---|
| `alice` | Alice |
| `lena107940` | Lena |
| `maxz108336` | MaxZ |
| `ming107435` | Ming |
| `gabriel@weexdev.com` | Gabriel |
| `kayce107735` | Kayce |
| `rain107774` | Rain |
| `sheep` | Sheep |
| `terence` | Terence |
| `tim108179` | TimWu |
| `wesley107941` | Wesley |

## Default KPI Tester Groups

### 活动组

```text
alice
ming107435
gabriel@weexdev.com
tim108179
wesley107941
```

### 数仓组

```text
lena107940
maxz108336
rain107774
terence
```

### 开放服务组

```text
kayce107735
sheep
```

## Tester Source Priority

Use tester ownership in this order:

1. QA schedule, weekly report, monthly Lark table, or manually provided `测试介入时间 + JIRA单` list.
2. Jira custom tester field, only when clearly the team's tester-owner field, such as `测试负责人`, `QA负责人`, `测试介入人`, or equivalent.
3. Jira assignee/reporter only when the user explicitly confirms that the team uses assignee/reporter as tester owner.

Do not infer tester ownership from Jira `经办人`, `报告人`, `创建人`, or current assignee by default.

## Stable Jira Fetch Protocol

Avoid large all-field responses. Do not request `fields=*all` for monthly audits.

Use this sequence:

1. Fetch Jira field metadata once with `/rest/api/2/field`, map required custom fields, and cache the mapping for the current run.
2. Fetch monthly demand rows with a strict field whitelist:
   - `summary`, `status`, `assignee`, `reporter`, `priority`, `issuetype`, `description`, `comment`, `issuelinks`, `labels`, `components`, `created`, `updated`;
   - tester owner, development owner, business module, Story Points, planned test start/end, submission date, acceptance/release dates, test progress.
3. Page Jira search results with `startAt`/`maxResults`; prefer `maxResults <= 50`.
4. For group/all-tester audits, scan one tester-month at a time.
5. Fetch heavy data only when needed:
   - changelog for completion/status transition evidence;
   - sampled linked Bugs for Bug quality evidence, following the sampling rule below;
   - Lark/Google docs only when links match the evidence-link rules below.
6. If a response is truncated, retry with fewer fields or smaller page size. Never continue from a truncated JSON response.

Temporary working data is allowed internally, but do not mention local temporary files in the user-facing report unless the user asks for exported files.

## Evidence To Collect Per Demand

Collect enough evidence to fill the formal row-level table:

```text
时间
JIRA单
状态
流程类型
实际测试完成
提测前完成测试用例产出
用例/评审记录
测试用例是否编写
全局影响面评估分析是否完整
自测报告
测试报告
验收/线上问题
风险同步/闭环记录
Bug记录是否规范
月度工作量加分在汇总项统计
扣分项
```

Also collect supporting fields used for decisions:

```text
Jira地址
经办人
研发人员
业务模块
Story Points
测试人员
测试周期
预计测试开始
预计测试完成
关联 Bug keys
linked evidence URLs
```

Apply `references/sop-rules.md` after evidence is collected.

## Evidence Link Rules

Open a document link as a test-case document only when the URL is explicitly adjacent to wording such as:

```text
测试用例
用例
测试点
case
测试脑图
```

Do not open ordinary PRD/需求/技术方案 links as test-case evidence.

Open self-test/submission evidence only when adjacent wording includes:

```text
自测报告
自测文档
自测结果
提测报告
提测文档
```

For self-test/submission evidence, do not open the linked document by default. If Jira/Lark visible text has one of the adjacent keywords above and a URL/attachment/card link is present, mark `有自测报告`. Open the link only when the label is ambiguous and the result can change a deduction.

For test-report evidence, do not open the linked document by default. If Jira/Lark visible text has one of the adjacent keywords below and a URL/attachment/card link is present, mark `有测试报告`:

```text
测试报告
测试完成报告
测试总结
测试结论
```

If there is only a plain Jira comment such as `测试完成`, `验证通过`, or `待发布` without a report/conclusion link, classify it by `references/sop-rules.md` as `仅测试完成备注` or `有测试结论`; do not open unrelated links to prove a report.

When Jira comments contain `验收问题`, `验收问题清单`, `问题跟踪表`, or similar wording plus a Lark/wiki/base URL, open the issue list and classify rows using `references/acceptance-issue-list.md`.

## Associated Bug Collection

Collect associated bugs from:

- Jira issue links on the demand.
- Jira comments that explicitly identify an issue as this demand's bug/defect/online escape, using wording such as `关联Bug`, `关联缺陷`, `本需求Bug`, `验收问题`, `线上问题`, `线上漏测`, `Prod Bug`, or `缺陷单`.
- JQL by linked issue when supported:

```jql
issuetype = BUG AND issue in linkedIssues(<DEMAND_KEY>)
```

Do not count every issue key mentioned in comments as an associated Bug. If the comment context says the issue is an `插入项`, `并行需求`, `优先处理`, `延期风险`, `阻塞项`, or another interrupted/parallel demand, record it under risk synchronization instead.

## Associated Bug Quality Sampling

For Bug record quality, do not open every associated Bug by default. Use this fixed sampling rule:

```text
total Bugs = N
if N = 0: no Bug quality detail check
if 1 <= N <= 3: open all Bugs
if N > 3: open max(3, ceil(N * 30%)) Bugs
```

Sampling priority:

1. Bugs explicitly marked `Prod Bug`, `线上问题`, `线上漏测`, P0, or P1.
2. Bugs with higher priority/severity.
3. Bugs most clearly linked from the demand's Jira issue links.
4. Newest created Bugs when priority/link evidence is otherwise equal.

Only sampled Bugs may be judged `规范` or `不规范`. Unopened Bugs must not be called non-compliant.

Use row-level wording such as:

```text
无关联Bug
关联 Bug N 个；已抽查 M 个；规范 X 个，不规范 Y 个；主要问题：缺复现步骤、缺实际结果、缺预期结果
关联 Bug N 个；已抽查 M 个；规范 X 个，不规范 0 个
关联 Bug N 个；待确认：Bug详情未打开
```

## Live Scan Versus Offline Scripts

Live scan means Codex actually inspects Jira/Lark evidence available in the current session.

Offline scripts do not fetch Jira/Lark:

- `scripts/audit_monthly_sop.py` reads already-collected CSV/TSV rows.
- `scripts/check_bug_record_quality.py` reads already-exported Jira Bug JSON.
- `scripts/summarize_acceptance_issues.py` reads exported acceptance issue CSV/TSV rows.

If a field was not collected, the script can only classify the missing field; it cannot prove the evidence does not exist in Jira/Lark.
