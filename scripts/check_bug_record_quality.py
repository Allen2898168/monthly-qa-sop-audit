#!/usr/bin/env python3
"""Offline checker for already-exported Jira Bug JSON.

This helper does not fetch Jira issues. It only checks Bug records that were
already exported/provided to the script.
"""
import argparse
import json
import re
import sys
from collections import Counter


STEP_PATTERNS = [
    r"复现步骤",
    r"操作步骤",
    r"步骤",
    r"step",
    r"steps",
    r"点击",
    r"进入",
    r"选择",
    r"输入",
    r"配置",
    r"提交",
    r"处理",
]

ACTUAL_PATTERNS = [
    r"实际结果",
    r"实际",
    r"现象",
    r"问题",
    r"报错",
    r"失败",
    r"无法",
    r"没有",
    r"未",
    r"错误",
]

EXPECTED_PATTERNS = [
    r"预期结果",
    r"预期",
    r"应该",
    r"应为",
    r"需",
    r"需要",
    r"期望",
]

URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.I)


def norm(value):
    return (value or "").strip()


def has_any(text, patterns):
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def issue_fields(issue):
    fields = issue.get("fields", issue)
    return {
        "key": issue.get("key") or fields.get("key", ""),
        "summary": norm(fields.get("summary")),
        "description": norm(fields.get("description")),
        "priority": (fields.get("priority") or {}).get("name") if isinstance(fields.get("priority"), dict) else norm(fields.get("priority")),
        "status": (fields.get("status") or {}).get("name") if isinstance(fields.get("status"), dict) else norm(fields.get("status")),
        "assignee": ((fields.get("assignee") or {}).get("displayName") or (fields.get("assignee") or {}).get("name")) if isinstance(fields.get("assignee"), dict) else norm(fields.get("assignee")),
    }


def classify(issue):
    f = issue_fields(issue)
    description = f["description"]
    missing = []

    if not description:
        missing.append("描述为空")
    elif URL_ONLY_RE.match(description):
        missing.append("仅贴外部链接")

    has_steps = bool(description) and has_any(description, STEP_PATTERNS)
    has_actual = bool(description) and has_any(description, ACTUAL_PATTERNS)
    has_expected = bool(description) and has_any(description, EXPECTED_PATTERNS)

    if not has_steps:
        missing.append("缺复现步骤")
    if not has_actual:
        missing.append("缺实际结果")
    if not has_expected:
        missing.append("缺预期结果")

    if not f["priority"]:
        missing.append("缺优先级")
    if not f["status"]:
        missing.append("缺状态")
    if not f["assignee"]:
        missing.append("缺经办人/修复人")

    return {
        **f,
        "has_reproduction_steps": has_steps,
        "has_actual_result": has_actual,
        "has_expected_result": has_expected,
        "is_standard": not missing,
        "missing_items": missing,
    }


def load_issues(path):
    data = json.load(open(path, encoding="utf-8")) if path != "-" else json.load(sys.stdin)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "issues" in data and isinstance(data["issues"], list):
            return data["issues"]
        if "value" in data:
            value = data["value"]
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                    if isinstance(parsed, dict) and "issues" in parsed:
                        return parsed["issues"]
                except json.JSONDecodeError:
                    pass
        return [data]
    return []


def summarize(results):
    total = len(results)
    standard = sum(1 for r in results if r["is_standard"])
    not_standard = total - standard
    missing_counter = Counter()
    for result in results:
        if not result["is_standard"]:
            missing_counter.update(result["missing_items"])
    main_issues = "、".join(k for k, _ in missing_counter.most_common())
    if total == 0:
        return "无关联Bug"
    if not_standard == 0:
        return f"关联 Bug {total} 个；规范 {standard} 个，不规范 0 个"
    return f"关联 Bug {total} 个；规范 {standard} 个，不规范 {not_standard} 个；主要问题：{main_issues}"


def main():
    parser = argparse.ArgumentParser(
        description="Offline check of already-exported Jira Bug records by reproduction/actual/expected fields."
    )
    parser.add_argument("input", help="JSON file containing Jira issues, or '-' for stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [classify(issue) for issue in load_issues(args.input)]
    payload = {
        "summary_text": summarize(results),
        "total": len(results),
        "standard": sum(1 for r in results if r["is_standard"]),
        "not_standard": sum(1 for r in results if not r["is_standard"]),
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["summary_text"])


if __name__ == "__main__":
    main()
