#!/usr/bin/env python3
"""Offline summarizer for exported acceptance issue tables."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


TYPE_COLUMNS = ["问题类型", "类型", "issue_type", "Issue Type"]
PRIORITY_COLUMNS = ["严重程度", "优先级", "priority", "Priority"]
DESC_COLUMNS = ["问题描述", "描述", "summary", "Summary"]
REPORTER_COLUMNS = ["反馈人", "报告人", "reporter", "Reporter"]


def norm(value):
    value = (value or "").strip()
    if value.lower() == "bug":
        return "bug"
    return value or "未分类"


def pick_column(fieldnames, candidates):
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    return None


def read_rows(path, fmt):
    delimiter = "\t" if fmt == "tsv" else ","
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader), reader.fieldnames or []


def summarize(rows, fieldnames):
    type_col = pick_column(fieldnames, TYPE_COLUMNS)
    priority_col = pick_column(fieldnames, PRIORITY_COLUMNS)
    desc_col = pick_column(fieldnames, DESC_COLUMNS)
    reporter_col = pick_column(fieldnames, REPORTER_COLUMNS)

    type_counts = Counter()
    bug_priority_counts = Counter()
    sample_bug_rows = []

    for row in rows:
        issue_type = norm(row.get(type_col)) if type_col else "未分类"
        type_counts[issue_type] += 1
        if issue_type == "bug":
            priority = norm(row.get(priority_col)) if priority_col else "未分类"
            bug_priority_counts[priority] += 1
            if len(sample_bug_rows) < 10:
                sample_bug_rows.append({
                    "问题描述": row.get(desc_col, "") if desc_col else "",
                    "反馈人": row.get(reporter_col, "") if reporter_col else "",
                    "问题类型": row.get(type_col, "") if type_col else "",
                    "严重程度": row.get(priority_col, "") if priority_col else "",
                })

    return {
        "total_records": len(rows),
        "type_field": type_col,
        "priority_field": priority_col,
        "type_counts": dict(type_counts),
        "bug_count": type_counts.get("bug", 0),
        "bug_priority_counts": dict(bug_priority_counts),
        "sample_bug_rows": sample_bug_rows,
    }


def format_summary(payload):
    total = payload["total_records"]
    bug_count = payload["bug_count"]
    type_counts = payload["type_counts"]
    priority_counts = payload["bug_priority_counts"]

    priority_part = "、".join(f"{k}:{v}" for k, v in priority_counts.items()) if priority_counts else ""
    other_types = [(k, v) for k, v in type_counts.items() if k != "bug"]
    other_part = "、".join(f"{k} {v} 条" for k, v in other_types)

    if bug_count and bug_count == total:
        return f"验收问题清单：共 {total} 条，均为 bug" + (f"（{priority_part}）" if priority_part else "")
    if bug_count:
        return f"验收问题清单：共 {total} 条；bug {bug_count} 条" + (f"（{priority_part}）" if priority_part else "") + (f"；{other_part}" if other_part else "")
    return f"验收问题清单：共 {total} 条，未发现 bug" + (f"；按问题类型统计：{other_part}" if other_part else "")


def main():
    parser = argparse.ArgumentParser(description="Summarize acceptance issue list by 问题类型 and 严重程度.")
    parser.add_argument("input", help="Input CSV/TSV exported from acceptance issue table")
    parser.add_argument("--format", choices=["csv", "tsv"], default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.input)
    fmt = args.format or ("tsv" if path.suffix.lower() == ".tsv" else "csv")
    rows, fieldnames = read_rows(path, fmt)
    payload = summarize(rows, fieldnames)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_summary(payload))


if __name__ == "__main__":
    main()
