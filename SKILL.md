---
name: monthly-qa-sop-audit
description: Monthly QA KPI/SOP audit workflow for scanning testers' Jira/Lark demand records and exported CSV/TSV sheets. Use when Codex is asked to audit a tester's monthly Jira tickets, check whether test cases, reviews, progress notes, test reports, gates, bug records, risk closure, acceptance issues, or online bugs comply with QA SOP, and produce KPI deduction suggestions or a monthly scoring evidence table.
---

# QA 月度 SOP 审计与 KPI 扣分建议工具

Use this skill for monthly QA SOP/KPI audits. It produces evidence, deduction/bonus suggestions, and a row-level audit table for manual supervisor review. It is not a fully automatic final scoring authority.

## Source Of Truth

- KPI/SOP scoring rules live in `references/sop-rules.md`.
- Jira/Lark sourcing and evidence collection rules live in `references/jira-sourcing.md`.
- Acceptance issue-list classification rules live in `references/acceptance-issue-list.md`.
- `scripts/collect_month.py` is the preferred live collector for Jira REST + Lark app-token evidence gathering.
- `scripts/audit_monthly_sop.py`, `scripts/check_bug_record_quality.py`, and related helpers apply deterministic audit rules on collected data.
- `scripts/lark_doc_fetch.py` reads Lark docs live via a Lark app token (see `references/jira-sourcing.md` → Lark Document Fetch).

When a rule appears to conflict, prefer `references/sop-rules.md` for scoring and `references/jira-sourcing.md` for data collection.

## Capability Boundary

There are two supported modes:

1. Live Jira/Lark audit
   - Use when the user provides a tester/person/group plus a month, such as `rain 5月份绩效考核`.
   - Default to Jira/Lark live scan following `references/jira-sourcing.md`.
   - Do not first search local files or ask for CSV/TSV when tester/group + month is already provided.
   - The assistant must actually inspect Jira/Lark evidence available in the session before claiming it was checked.
   - Accepted live sources, in order: scripted Jira REST + Lark app-token pipeline, browser-control session, authenticated Chrome/CDP session. Anonymous Jira API access is never acceptable.
   - Do not start or attach to browser/CDP only to verify Jira access before the scripted Jira REST + Lark app-token path has been attempted.
   - If none of these authenticated paths works, stop and report the access blocker. Do not silently fall back to local files, old TSVs, anonymous Jira API results, or offline scripts.

2. Offline file audit
   - Use only when the user explicitly provides or requests CSV/TSV/JSON/local-file mode.
   - `scripts/audit_monthly_sop.py` audits already-collected CSV/TSV rows.
   - `scripts/check_bug_record_quality.py` checks already-exported Jira Bug JSON.
   - Missing source fields cannot be invented. Mark missing evidence as `待确认`, `缺...`, or `-` according to the output rules.

## Formal Output Contract

For any formal KPI audit request, output directly in chat using exactly these sections:

```text
一、月度结论摘要

二、扣分/加分建议

三、关键确认项

四、逐单检查表
```

Do not output only local file paths or generated artifacts. Do not create `*_audit.tsv`, `*_summary.md`, `.xlsx`, or other report files by default. Create/export files only when the user explicitly asks `导出文件`, `生成Excel`, `保存到本地`, `输出文件`, or equivalent.

### 一、月度结论摘要

This section must be clear enough for a supervisor to see the current score immediately. Use this structure:

```text
本次审计范围为 <tester> 在 <YYYY-MM> 的 Jira/Lark 记录，共 <N> 个需求。

当前明确测算得分为 <score>/100，其中：
```

Then output a Markdown table with exactly these columns:

```text
模块 | 得分 | 主要依据
```

The table must include exactly these four rows, in this order:

```text
业务交付质量与效能 | <score>/30 | <deduction/bonus basis>
重点工作 | <score>/25 | <deduction basis or 暂未确认重点需求范围，Bug 规范问题暂不计入扣分>
测试专业能力与规范执行 | <score>/45 | <deduction basis>
合计 | <score>/100 | 明确扣 <N> 分，加 <N> 分
```

After the table, include one sentence only for score-changing pending items. Generate it from the current audit evidence; do not reuse any example Jira keys or wording that does not apply to the current tester/month.

```text
该分数暂未计入待确认项：<线上/验收问题 Jira key> 的责任归属、<超期 Jira key> 的超期是否测试侧原因、以及 <Bug 规范问题 Jira key> 的重点需求 Bug 规范扣分适用范围。
```

Do not mix tool limitations or broad caveats into the score sentence. If a non-score evidence limitation must be mentioned, add a separate sentence after the pending-item sentence and clearly label it as evidence completeness, not current scoring.

### 二、扣分/加分建议

This section must be a table with exactly these columns:

```text
结论 | 项目 | 问题 | 建议
```

Every deduction/bonus row must include exact counts and affected Jira keys when Jira-key-level evidence exists. Keep monthly threshold conclusions here, not inside row-level `扣分项`.

### 三、关键确认项

Only include confirmation items that can change the final score, such as:

- responsibility attribution for online/acceptance issues;
- whether Bug规范 applies to key-work scoring;
- whether workload bonus eligibility is blocked by major incident, P0/P1 online missed bug, or testing-side delay.

Do not put tool limitations, broad caveats, or implementation notes here, such as `画板无法读取`, `自动检查疑似`, `多数 Jira 单 Story Points 为空`, or `人工复核后确认`.

### 四、逐单检查表

This section is mandatory unless the user explicitly says `不用输出逐单表`, `只要摘要`, or equivalent. Use exactly these columns and one demand per row:

```tsv
时间	JIRA单	状态	流程类型	实际测试完成	提测前完成测试用例产出	用例/评审记录	测试用例是否编写	全局影响面评估分析是否完整	自测报告	测试报告	验收/线上问题	风险同步/闭环记录	Bug记录是否规范	月度工作量加分在汇总项统计	扣分项
```

Do not replace this table with an abbreviated table such as `JIRA单/主要问题`, `逐单风险概览`, `问题标签`, or `扣分事实`.

For TSV/Excel-copyable output, keep one demand per line and replace line breaks inside cells with spaces.

## Required Wording Boundaries

Formal KPI audit output must not use these weak/unstable terms:

- `疑似不规范`: use `不规范` only after checking Bug details; otherwise write `关联 Bug N 个；待确认：Bug详情未打开`.
- `画板未读`: use `待确认：内容无法读取` only when a qualifying test-case document was opened but cannot be read.
- generic row-cell `缺失`: prefer specific labels such as `缺用例`, `缺影响面评估`, `缺自测报告`, `缺测试报告/结论`, `缺失评审`, or `无`.
- `有用例评审记录`: use `用例评审通过`, `用例评审不通过`, or `未见用例评审结论`.

## Workflow

1. Determine scope:
   - tester/person/group;
   - target month;
   - source mode: live Jira/Lark or explicit offline file mode.

2. For live Jira/Lark audit, pass the access gate before collecting evidence:
   - First run the scripted collector using authenticated Jira REST + Lark app-token credentials per `references/jira-sourcing.md` Live Access Gate.
   - Credential discovery order is workspace `.env`, then workspace `.env.local`, then the documented user-level Jira/Lark `.env` paths.
   - Verify the REST session can see a known WWLD issue or the target Jira filter; `GET /rest/api/2/myself` must return a non-anonymous account.
   - Do not launch or attach to browser/CDP just to check whether Jira is logged in until both workspace `.env` and `.env.local` have been checked and the scripted REST path has been attempted when credentials are present.
   - If the scripted path cannot authenticate or cannot collect required evidence, fall back to browser-control or authenticated Chrome/CDP to complete the live scan.
   - If neither the scripted path nor browser/CDP works, treat live scan as blocked and ask the user to open/login Jira in the accessible browser, provide API credentials, or provide an explicit export.

3. Source demand rows:
   - For live scan, follow `references/jira-sourcing.md`.
   - For all-testers/group requests, expand the roster/group in `references/jira-sourcing.md`.
   - For seed lists with `测试介入时间 + JIRA单`, treat the seed list as scope and enrich each issue from Jira/Lark if live access is available.

4. Collect evidence per demand. **Prefer the scripted pipeline first; only use browser/CDP as a fallback when the scripts cannot authenticate or cannot read the required evidence.** Do not re-derive SOP labels by hand or spawn one agent per demand. The deterministic rules live in scripts; the model only adjudicates genuinely ambiguous rows (see step 7).

   ```bash
   # one command: live Jira REST + Lark app-token collection → evidence TSV
   python3 scripts/collect_month.py rain107774 2026-05 \
       --out audit_input.tsv --json evidence.json
   # second command: deterministic rule evaluation → four-section report
   python3 scripts/audit_monthly_sop.py audit_input.tsv --format tsv
   ```

   `collect_month.py` pulls demands by `测试人员（多选）=tester` + `预计测试开始时间 ∈ month`, opens each Lark 用例/测试报告/自测报告 doc, and classifies every evidence column (流程类型 via the engine's own rule, 提测前用例时序, 用例评审, 自测/测试报告标签, 全局影响面评估表逐行, Bug 描述规范). `audit_monthly_sop.py` applies thresholds/caps and emits 四段式. Use `references/sop-rules.md` only to interpret edge cases.

5. Produce the formal output in chat (the report from step 4, lightly edited for the manual-confirmation items).

6. Other offline helpers (when given exports instead of live access):

```bash
python3 scripts/normalize_jira_seed.py seed.tsv --format tsv > audit_input.tsv
python3 scripts/check_bug_record_quality.py bugs.json
python3 scripts/summarize_acceptance_issues.py acceptance.tsv --format tsv
```

7. Model/human intervention is limited to rows the scripts flag, e.g.: `待确认：画板节点不可读` (board test cases — needs `board:whiteboard:node:read` scope to auto-read), `流程类型=待确认`, online/acceptance responsibility attribution, 重点需求 designation for Key-Work Bug scoring, and borderline Bug records. Everything else is script-determined and reproducible.

Treat helper output as deterministic evidence support, not as a substitute for live Jira/Lark inspection. Do NOT use a multi-agent workflow to process demands one by one.

## Packaging Checklist

Before packaging or finalizing this skill, verify:

- `references/sop-rules.md` is the only scoring-rule source.
- `references/jira-sourcing.md` contains sourcing/evidence-collection rules only.
- `SKILL.md` contains output contract and workflow only, not duplicated scoring details.
- Formal output contains the four required sections.
- `四、逐单检查表` uses the exact required columns.
- No generated audit artifacts are included in the skill directory or zip.
- `scripts/selftest_audit_rules.py` passes.
