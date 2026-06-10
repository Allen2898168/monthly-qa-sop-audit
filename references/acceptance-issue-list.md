# Acceptance Issue List Scan

Use this reference when Jira comments or descriptions link to a Lark/wiki/base table for product acceptance issues.

## Trigger

Run this scan when Jira comments/descriptions contain both:

1. Acceptance wording:

```text
验收问题
验收问题清单
产品验收问题
验收反馈
问题跟踪表
需求问题跟踪表
```

2. A Lark/wiki/base URL, for example:

```text
https://bsgwewe588io.sg.larksuite.com/wiki/...
```

## Goal

Open the linked issue table and classify all visible/accessible records by the field `问题类型`.

The result is used to fill the audit field `验收/线上问题`.

## Required Fields

Expected table fields include:

```text
阶段
问题描述
反馈人
问题类型
严重程度
```

Only `问题类型` is required for classification. `严重程度` is used for priority distribution when available.

## Classification Rule

Classify records by exact or normalized `问题类型` value.

Common values:

```text
bug
Bug
产品问题
需求问题
优化
体验问题
配置问题
非问题
```

Normalize `bug`, `Bug`, `BUG` to `bug`.

If the field is empty, count as `未分类`.

## Bug Count Rule

The acceptance Bug count is:

```text
count(records where normalized 问题类型 == "bug")
```

If `严重程度` exists, also count:

```text
P0
P1
P2
P3
其他/空
```

## Output To `验收/线上问题`

Use concise wording:

```text
验收问题清单：共 N 条；bug X 条（P0:a、P1:b、P2:c、P3:d）；产品问题 Y 条；优化 Z 条
```

If all records are bugs:

```text
验收问题清单：共 N 条，均为 bug（P0:a、P1:b、P2:c、P3:d）
```

If there are no bug records:

```text
验收问题清单：共 N 条，未发现 bug；按问题类型统计：产品问题 Y 条、优化 Z 条
```

## Evidence To Keep

For audit traceability, keep at least:

```text
source_url
table_title
total_records
type_counts
bug_priority_counts
sample_bug_rows
scan_time
```

Sample bug rows should include:

```text
问题描述
反馈人
问题类型
严重程度
```

## Browser Reading Notes

Lark Base tables may use virtual rendering. If DOM text only shows toolbar/header:

1. Confirm permission by checking the table title and visible fields.
2. Try scrolling the table area horizontally/vertically.
3. Inspect loaded resources or page state for Base/table metadata.
4. Use visible rows when only visible rows are accessible, and state the limitation.

Do not invent records. If the table cannot be fully read, mark the result as partial or `待人工确认`.

## Example

For a table with two visible rows:

| 问题描述 | 反馈人 | 问题类型 | 严重程度 |
|---|---|---|---|
| 首次充值定义未填写，能保存 | PR-PMU-Lindsay | bug | P1 |
| 小丑牌邀请任务配置时，判断邀请人和被邀请人的奖品id需一致 | PR-PMU-Lindsay | bug | P1 |

Write:

```text
验收问题清单：共 2 条，均为 bug（P1:2）
```

