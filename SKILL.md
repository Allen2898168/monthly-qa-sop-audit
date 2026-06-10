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
- Scripts under `scripts/` are offline helpers. They do not log in to Jira, open Lark documents, or fetch linked Bugs by themselves.

When a rule appears to conflict, prefer `references/sop-rules.md` for scoring and `references/jira-sourcing.md` for data collection.

## Capability Boundary

There are two supported modes:

1. Live Jira/Lark audit
   - Use when the user provides a tester/person/group plus a month, such as `rain 5月份绩效考核`.
   - Default to Jira/Lark live scan following `references/jira-sourcing.md`.
   - Do not first search local files or ask for CSV/TSV when tester/group + month is already provided.
   - The assistant must actually inspect Jira/Lark evidence available in the session before claiming it was checked.
   - If Jira/Lark cannot be accessed with an authenticated browser/session, stop and report the access blocker. Do not silently fall back to local files, old TSVs, anonymous Jira API results, or offline scripts.

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

### 二、扣分/加分建议

This section must be a TSV/Lark-pasteable table with exactly these columns. Do not use Markdown pipe-table formatting:

```text
结论	项目	问题	建议
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

Do not replace this table with an abbreviated table such as `JIRA单/主要问题`, `逐单风险概览`, `问题标签`, or `扣分事实`. Do not output Markdown pipe tables for the row-level table.

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
   - Use the available browser-control capability or an authenticated Chrome/CDP session to open Jira.
   - Verify the session can see a known WWLD issue or the target Jira filter.
   - If only anonymous Jira API access is available, treat live scan as blocked and ask the user to open/login Jira in the accessible browser or provide an explicit export.
   - Prefer `scripts/jira_cdp_live_scan.mjs` for Jira data collection: it executes Jira REST `fetch` inside the authenticated Chrome/CDP session, batches demand rows, samples linked Bugs, and only opens necessary Lark test-case links.

3. Source demand rows:
   - For live scan, follow `references/jira-sourcing.md`.
   - For all-testers/group requests, expand the roster/group in `references/jira-sourcing.md`.
   - For seed lists with `测试介入时间 + JIRA单`, treat the seed list as scope and enrich each issue from Jira/Lark if live access is available.

4. Collect evidence per demand:
   - Jira status, assignee, development owner, planned test dates, actual completion evidence.
   - Test case, review, impact assessment, self-test/submission report, test report/conclusion.
   - Acceptance issues, risk/closure notes, linked Bugs and Bug record quality.
   - Use `references/sop-rules.md` for all pass/fail/deduction decisions.

5. Produce the formal output in chat.

6. If using offline helpers:

```bash
NODE_PATH=/path/to/node_modules node scripts/jira_cdp_live_scan.mjs --tester rain107774 --display-name Rain --month 2026-05 --audit
python3 ~/.codex/skills/monthly-qa-sop-audit/scripts/normalize_jira_seed.py seed.tsv --format tsv > audit_input.tsv
python3 ~/.codex/skills/monthly-qa-sop-audit/scripts/audit_monthly_sop.py audit_input.tsv --format tsv
python3 ~/.codex/skills/monthly-qa-sop-audit/scripts/check_bug_record_quality.py bugs.json
python3 ~/.codex/skills/monthly-qa-sop-audit/scripts/summarize_acceptance_issues.py acceptance.tsv --format tsv
```

`jira_cdp_live_scan.mjs --audit` is the preferred live-scan path when Chrome/CDP is authenticated. The Python helpers remain deterministic offline evidence support and are not a substitute for live Jira/Lark inspection.

## Packaging Checklist

Before packaging or finalizing this skill, verify:

- `references/sop-rules.md` is the only scoring-rule source.
- `references/jira-sourcing.md` contains sourcing/evidence-collection rules only.
- `SKILL.md` contains output contract and workflow only, not duplicated scoring details.
- Formal output contains the four required sections.
- `四、逐单检查表` uses the exact required columns.
- No generated audit artifacts are included in the skill directory or zip.
- `scripts/selftest_audit_rules.py` passes.
