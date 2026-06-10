#!/usr/bin/env python3
import argparse
import csv
import re
import sys


OUTPUT_COLUMNS = [
    "时间",
    "JIRA单",
    "Jira地址",
    "状态",
    "经办人",
    "研发人员",
    "流程类型",
    "预计测试完成",
    "实际测试完成",
    "提测前完成测试用例产出",
    "用例/评审记录",
    "测试用例是否编写",
    "全局影响面评估分析是否完整",
    "自测报告",
    "测试报告",
    "验收/线上问题",
    "风险同步/闭环记录",
    "Bug记录是否规范",
    "扣分项",
]


ISSUE_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def clean(value):
    return (value or "").strip()


def extract_issue_and_title(text):
    text = clean(text)
    match = ISSUE_RE.search(text)
    if not match:
        return "", text
    key = match.group(1)
    title = (text[: match.start()] + text[match.end() :]).strip()
    title = re.sub(r"^[\s:：,，-]+", "", title)
    return key, f"{key}{title}" if title else key


def detect_columns(fieldnames):
    names = fieldnames or []
    time_col = next((c for c in names if c in ("时间", "测试介入时间", "介入时间", "日期")), None)
    jira_col = next((c for c in names if c in ("JIRA单", "Jira单", "jira", "JIRA", "需求", "需求单")), None)
    return time_col, jira_col


def read_rows(path, fmt):
    delimiter = "\t" if fmt == "tsv" else ","
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        if not sample.strip():
            return []
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames and any(reader.fieldnames):
            time_col, jira_col = detect_columns(reader.fieldnames)
            if time_col and jira_col:
                return [
                    {
                        "time": clean(row.get(time_col)),
                        "jira_text": clean(row.get(jira_col)),
                    }
                    for row in reader
                ]

        f.seek(0)
        simple_reader = csv.reader(f, delimiter=delimiter)
        rows = []
        for row in simple_reader:
            if not row or not any(clean(c) for c in row):
                continue
            if len(row) == 1:
                rows.append({"time": "", "jira_text": clean(row[0])})
            else:
                rows.append({"time": clean(row[0]), "jira_text": clean(" ".join(row[1:]))})
        return rows


def normalize(rows):
    output = []
    for row in rows:
        key, jira_title = extract_issue_and_title(row["jira_text"])
        if not key and not jira_title:
            continue
        normalized = {col: "" for col in OUTPUT_COLUMNS}
        normalized["时间"] = row["time"]
        normalized["JIRA单"] = jira_title or key
        normalized["Jira地址"] = f"https://jira.weex.tech/browse/{key}" if key else ""
        normalized["流程类型"] = "待确认"
        output.append(normalized)
    return output


def main():
    parser = argparse.ArgumentParser(description="Normalize tester monthly Jira seed list into QA SOP audit TSV.")
    parser.add_argument("input", help="Input CSV/TSV seed list. Use columns 时间/测试介入时间 and JIRA单 when available.")
    parser.add_argument("--format", choices=["csv", "tsv"], default=None)
    args = parser.parse_args()

    fmt = args.format
    if fmt is None:
        fmt = "tsv" if args.input.lower().endswith(".tsv") else "csv"

    rows = normalize(read_rows(args.input, fmt))
    writer = csv.DictWriter(sys.stdout, fieldnames=OUTPUT_COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()
