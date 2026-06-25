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

1. First use the scripted live-collection path: authenticated Jira REST API session (Basic auth `username:token`) plus Lark app-token access when credentials are already available in the runtime.
   - default Jira credential source order: workspace `.env`, then workspace `.env.local`, then `/Users/gabriel/Downloads/jira/.env` (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_TOKEN`), or equivalent environment variables / a user-indicated `.env`;
   - default Lark credential source order: workspace `.env`, then workspace `.env.local`, then `/Users/gabriel/Downloads/weexpr/eff/.env` (`app_id`, `app_secret`), or equivalent environment variables / a user-indicated `.env`;
   - never print the token value into chat or reports.
   - do not start browser-control or Chrome/CDP only to verify Jira access before workspace `.env` and `.env.local` have both been checked and this REST path has been attempted when credentials are present.
2. Verify login before any audit work:
   - for REST API: `GET /rest/api/2/myself` must return a real account (not `anonymous`), then fetch a known issue such as `WWLD-12494`;
   - confirm the response can see WWLD project data and is not `anonymous`;
   - confirm Jira comments/links are visible enough to collect SOP evidence.
3. If the scripted path cannot authenticate, cannot see the required Jira/Lark evidence, or hits an evidence boundary that blocks the audit, use the available browser-control tool to operate the user's logged-in browser session.
4. If browser-control is unavailable, try an authenticated Chrome/CDP session only when it is already accessible from the current runtime.
5. For browser/CDP fallback, open a known Jira issue such as `https://jira.weex.tech/browse/WWLD-12494`, or run an authenticated Jira search.
6. If login/session verification fails on all paths, stop the live audit and report:

```text
无法实时扫描 Jira/Lark：当前会话未取得已登录 Jira 权限。
需要用户在可被控制的浏览器中打开并登录 Jira、提供 Jira API 账号 Token（如 jira 项目 .env），或明确提供 Jira/Lark 导出表后改走离线审计。
```

Do not continue with anonymous Jira API data. Do not use old local TSV/CSV files as a replacement for live scan. Do not skip the scripted path just because browser/CDP is available. Do not use browser/CDP for a login/access sanity check when workspace `.env` / `.env.local` credentials are present or have not yet been attempted.

### REST API Mode Evidence Boundary

Authenticated REST API mode is a full live-scan source for Jira data (fields, comments, changelog, issue links, linked bugs). The Jira token alone cannot open Lark docs, but the Lark app token can — see `Lark Document Fetch (App Token Mode)` below. Use both together for a complete live scan:

- Jira REST (Jira `.env`) for issue data; Lark app token (`eff` `.env`) for docx/wiki document content.
- Readable docx/table/text content is assessed normally per `references/sop-rules.md`. The only residual gap is whiteboard (画板) node text, which needs a `board:whiteboard:node:read` scope the current app lacks — mark those `待确认：画板节点不可读`.
- State the board-scope limitation once in the monthly summary, not in `三、关键确认项`.

## Default Jira Query

Default Jira live-scan JQL pattern:

```jql
project = WWLD
AND 测试人员（多选） = "<tester>"
AND 预计测试开始时间 >= <month_start>
AND 预计测试开始时间 < <next_month_start>
ORDER BY 预计测试开始时间 ASC, key ASC
```

If the tester field is unreliable, use the QA schedule/Lark monthly demand list or a user-provided `测试介入时间 + JIRA单` seed list as the scope source, then enrich each Jira issue individually.

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

1. Fetch Jira field metadata once with `/rest/api/2/field`, map required custom fields, and cache the mapping for the current run. Known mapping for `jira.weex.tech` (re-verify against `/rest/api/2/field` if a fetch fails):

   | 字段 | Field ID |
   |---|---|
   | 测试人员（多选） | `customfield_11622` |
   | 测试人员（单选） | `customfield_11606` |
   | 预计测试开始时间 | `customfield_12304` |
   | 预计测试完成时间 | `customfield_11617` |
   | 预计提测时间 | `customfield_11616` |
   | 预计验收完成时间 | `customfield_11618` |
   | 预计发布时间 | `customfield_11619` |
   | 发布完成时间 | `customfield_12600` |
   | 研发人员 | `customfield_11615` |
   | 业务模块 | `customfield_12401` |
   | Story Points | `customfield_10106`（备用 `customfield_12503`） |
   | 测试进度 | `customfield_12201` |

   In JQL prefer the `cf[11622]` form over Chinese field names, e.g. `project = WWLD AND cf[11622] = "rain107774" AND cf[12304] >= "2026-05-01" AND cf[12304] < "2026-06-01"`. Note: `issuetype = "故障"` is not a valid JQL value on this instance; find associated bugs through issue links or `summary ~` search instead.
2. Fetch monthly demand rows with a strict field whitelist:
   - `summary`, `status`, `assignee`, `reporter`, `priority`, `issuetype`, `description`, `comment`, `issuelinks`, `labels`, `components`, `created`, `updated`;
   - tester owner, development owner, business module, Story Points, planned test start/end, submission date, acceptance/release dates, test progress.
3. Page Jira search results with `startAt`/`maxResults`; prefer `maxResults <= 50`.
4. For group/all-tester audits, scan one tester-month at a time.
5. Fetch heavy data only when needed:
   - changelog for completion/status transition evidence;
   - linked Bugs for Bug quality evidence;
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

Open test-report evidence when adjacent wording includes:

```text
测试报告
测试完成报告
测试总结
测试结论
```

When there is no labeled test-report link, also scan Jira comments for simplified-flow completion evidence. A comment counts as `有测试结论` when it contains completion/result wording such as `测试完成`, `测试通过`, or `验证通过`, and also contains record wording such as `测试记录`, `测试内容`, `验证记录`, `验证内容`, or `执行记录`. For demands whose testing starts before `2026-07-01`, Jira comments such as `测试进度100%`, `stg测试完成`, `stg环境测试通过`, `stg验证通过`, `测试完成，请产品验收`, `测试完成 产品已同步验收`, `测试完成 麻烦[~xxx]` / `测试完成 请@xxx`, or `验证完成，可以发布` also count as valid simplified-flow completion evidence. A short comment with only isolated `测试完成` / `测试通过` remains `仅测试完成备注`.

When Jira comments contain `验收问题`, `验收问题清单`, `问题跟踪表`, or similar wording plus a Lark/wiki/base URL, open the issue list and classify rows using `references/acceptance-issue-list.md`.

## Lark Document Fetch (App Token Mode)

Preferred way to open Lark docs without a browser/CDP. Lark documents on `*.larksuite.com` (international) can be read with a Lark app `tenant_access_token`, no browser needed.

Credentials: `app_id` / `app_secret` from workspace `.env`, workspace `.env.local`, or `/Users/gabriel/Downloads/weexpr/eff/.env` (the `eff` backend's Lark app), in that order. Never print the secret. Open-API base is region-specific:

- `*.sg.larksuite.com` / international → `https://open.larksuite.com`
- `*.feishu.cn` (China) → `https://open.feishu.cn`

Helpers:

- `scripts/collect_month.py <tester> <YYYY-MM>` — end-to-end live collector: Jira REST + Lark app token → evidence TSV for `audit_monthly_sop.py`. This is the primary live path; it classifies every SOP column deterministically and only leaves truly-ambiguous fields as `待确认`.
- `scripts/lark_doc_fetch.py <url>` — resolve a single Lark URL and return text + structural flags (used internally by the collector; also handy for spot checks).

```bash
python3 scripts/lark_doc_fetch.py "https://bsgwewe588io.sg.larksuite.com/wiki/<token>"
```

Fetch protocol:

1. `POST /open-apis/auth/v3/tenant_access_token/internal` with `{app_id, app_secret}` → `tenant_access_token` (cache ~2h).
2. For a `/wiki/<node_token>` URL, resolve first: `GET /open-apis/wiki/v2/spaces/get_node?token=<node_token>` → `obj_type` + `obj_token`.
3. For a docx (`/docx/<id>` or wiki obj_type=`docx`): `GET /open-apis/docx/v1/documents/<id>/raw_content` → plain text; `GET /open-apis/docx/v1/documents/<id>/blocks` → block list (detect structure).
4. Block-type signals: `43` = board/画板(whiteboard), `31` = table, `27` = image, `1` = page.

### Board (画板) Scope Limitation — Important

The `eff` Lark app has docx/wiki read scopes but **not** `board:whiteboard:node:read`. So:

- A test-case doc that is just a title + a board block (`raw_content` length is only the title, blocks show `has_board=true`) means the cases live in a whiteboard whose node text the app cannot read.
- Do not classify such a doc as `缺失用例` (a board exists) and do not assert `有效` (cannot see nodes). Use the row-level label `用例为画板形式（board 对象存在，应用无 board 节点读取权限）` and mark case-content validity `待确认：画板节点不可读`. This is an evidence-completeness limitation, not an automatic deduction for missing cases, missing product/technical understanding, or incomplete impact assessment.
- When a test-case doc has a real text/table body (e.g. a full 全局影响面评估 table), assess those readable sections normally per `references/sop-rules.md`; only the in-board case nodes stay `待确认`.

### Self-Test / Report Reclassification After Reading

When the Jira comment only had a bare URL but the opened document is itself a structured developer self-test report (`自测范围` / `自测结果` / `结论：可提测`), treat it as `有自测报告`. Reading the doc beats the bare-link heuristic. Likewise, when a labeled `测试报告` link returns `131005 not found` (or otherwise cannot resolve), use `待确认：测试报告链接无法访问`, not `有测试报告`.

State the board-scope limitation once in the monthly summary, never in `三、关键确认项`.

## Associated Bug Collection

Collect associated bugs from:

- Jira issue links on the demand.
- Jira comments that explicitly identify an issue as this demand's bug/defect/online escape, using wording such as `关联Bug`, `关联缺陷`, `本需求Bug`, `验收问题`, `线上问题`, `线上漏测`, `Prod Bug`, or `缺陷单`.
- JQL by linked issue when supported:

```jql
issuetype = BUG AND issue in linkedIssues(<DEMAND_KEY>)
```

Do not count every issue key mentioned in comments as an associated Bug. If the comment context says the issue is an `插入项`, `并行需求`, `优先处理`, `延期风险`, `阻塞项`, or another interrupted/parallel demand, record it under risk synchronization instead.

## Live Scan Versus Offline Scripts

Live scan means Codex actually inspects Jira/Lark evidence available in the current session.

Offline scripts do not fetch Jira/Lark:

- `scripts/audit_monthly_sop.py` reads already-collected CSV/TSV rows.
- `scripts/check_bug_record_quality.py` reads already-exported Jira Bug JSON.
- `scripts/summarize_acceptance_issues.py` reads exported acceptance issue CSV/TSV rows.

If a field was not collected, the script can only classify the missing field; it cannot prove the evidence does not exist in Jira/Lark.
