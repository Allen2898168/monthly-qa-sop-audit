#!/usr/bin/env python3
"""Offline QA SOP auditor for already-collected CSV/TSV rows.

This helper does not log in to Jira, fetch Jira issues, open Lark documents, or
collect linked Bugs. It only classifies evidence fields that already exist in
the input table.
"""
import argparse
import csv
from datetime import date, datetime, timedelta
import json
import re
from pathlib import Path


EXPECTED_COLUMNS = [
    "时间",
    "JIRA单",
    "状态",
    "业务模块",
    "Story Points",
    "测试人员",
    "流程类型",
    "测试周期",
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

SG_PUBLIC_HOLIDAYS = {
    # Maintain this list yearly. 2026-05-27 is Hari Raya Haji in the user's
    # current KPI calendar and must be excluded from workday calculations.
    "2026-01-01",
    "2026-02-17",
    "2026-02-18",
    "2026-03-20",
    "2026-04-03",
    "2026-05-01",
    "2026-05-27",
    "2026-08-10",
    "2026-11-08",
    "2026-11-09",
    "2026-12-25",
}


NEGATIVE_PATTERNS = [
    r"缺",
    r"无",
    r"未",
    r"没有",
    r"不通过",
    r"不规范",
    r"阻塞",
    r"逃逸",
    r"线上",
    r"Prod Bug",
    r"P0",
    r"P1",
    r"P2",
    r"P3",
]


POSITIVE_PATTERNS = [
    r"有",
    r"已",
    r"通过",
    r"完成",
    r"关闭",
    r"如期",
    r"无关联Bug",
    r"验收通过",
]


def norm(value):
    if value is None:
        return ""
    return str(value).strip()


def has_any(text, patterns):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def first_value(row, names):
    for name in names:
        value = norm(row.get(name))
        if value:
            return value
    return ""


def parse_number(value):
    if isinstance(value, dict):
        for key in ("value", "name", "displayName"):
            parsed = parse_number(value.get(key))
            if parsed is not None:
                return parsed
    t = norm(value)
    if not t:
        return None
    value_match = re.search(r"['\"]value['\"]\s*:\s*['\"]?(-?\d+(?:\.\d+)?)", t)
    if value_match:
        return float(value_match.group(1))
    match = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(match.group(0)) if match else None


def parse_date(value, default_year=None):
    t = norm(value)
    if not t:
        return None
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
    if not match:
        match = re.search(r"(\d{1,2})[-/.](\d{1,2})", t)
        if not match:
            return None
        if default_year is None:
            # Monthly audit rows without a year are not safe for deterministic
            # duration calculation.
            return None
        m, d = [int(x) for x in match.groups()]
        return date(int(default_year), m, d)
    y, m, d = [int(x) for x in match.groups()]
    return date(y, m, d)


def parse_date_set(value):
    dates = set()
    text = norm(value)
    if not text:
        return dates
    for y, m, d in re.findall(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text):
        dates.add(date(int(y), int(m), int(d)))
    return dates


def extra_work_dates_from_row(row):
    text = first_value(
        row,
        [
            "周末测试进度日期",
            "周末有效工作日",
            "额外有效工作日",
            "周末测试日期",
            "周末备注测试日期",
        ],
    )
    return parse_date_set(text)


def workdays_between(start, end, holidays=SG_PUBLIC_HOLIDAYS, extra_work_dates=None):
    if not start or not end:
        return None
    if end < start:
        start, end = end, start
    extra_work_dates = extra_work_dates or set()
    days = 0
    current = start
    while current <= end:
        is_regular_workday = current.weekday() < 5 and current.isoformat() not in holidays
        if is_regular_workday or current in extra_work_dates:
            days += 1
        current += timedelta(days=1)
    return days


SCHEDULE_ONLY_COMPLETION_RE = re.compile(
    r"测试完成时间\s*(顺延|更新|调整|改|不变|暂未确定)|整体测试完成时间不变|预计.*测试完成",
    re.I,
)


def effective_actual_completion_date(row, default_year=None):
    actual_text = first_value(row, ["实际测试完成", "实际完成", "测试实际完成", "测试完成备注"])
    if not actual_text or SCHEDULE_ONLY_COMPLETION_RE.search(actual_text):
        return None
    if not re.search(r"测试完成|测试通过|测试验证无问题|验证无问题|已测试|状态", actual_text):
        return None
    return parse_date(actual_text, default_year=default_year)


def get_test_duration_days(row):
    direct = first_value(row, ["测试周期", "测试工日", "测试天数", "测试周期天数"])
    direct_number = parse_number(direct)
    if direct_number is not None:
        return direct_number
    start = parse_date(first_value(row, ["预计测试开始", "预计测试开始时间", "测试开始", "测试开始时间", "时间"]))
    default_year = start.year if start else None
    planned_end = parse_date(
        first_value(row, ["预计测试完成", "预计测试完成时间", "测试完成", "测试完成时间"]),
        default_year=default_year,
    )
    # Workload bonus uses the planned testing window. Actual completion is only
    # a fallback when no planned end is available; it should not expand bonus days.
    end = planned_end or effective_actual_completion_date(row, default_year=default_year)
    return workdays_between(start, end, extra_work_dates=extra_work_dates_from_row(row))


def has_tester_owner(row):
    return bool(first_value(row, ["测试人员", "测试介入人", "测试负责人", "QA", "人员"]))


def infer_process_type(row):
    explicit = norm(row.get("流程类型"))
    if explicit and "待确认" not in explicit:
        return explicit

    jira = first_value(row, ["JIRA单", "标题", "需求名称", "summary", "Summary"])
    title = jira.lower()
    module = first_value(row, ["业务模块", "业务线", "模块"])
    tester = first_value(row, ["测试人员", "测试介入人", "测试负责人", "QA", "人员"]).lower()
    story_points = parse_number(first_value(row, ["Story Points", "Story points", "SP点数", "SP", "故事点"]))
    duration = get_test_duration_days(row)
    data_group_testers = {"lena107940", "maxz108336", "rain107774", "terence", "rain", "maxz", "lena"}
    data_risk_keywords = r"风控|数据服务|监控系统|标签后台|审核系统|资运|KYT|kyt|提币审核|充值|提现审核"

    if module == "数仓" and has_tester_owner(row):
        return "标准流程"
    if tester in data_group_testers and re.search(data_risk_keywords, jira, re.I):
        return "标准流程"
    if "okr" in title:
        return "标准流程"
    if story_points is not None and story_points > 3:
        return "标准流程"
    if duration is not None and duration > 2:
        return "标准流程"

    if "快速优化" in jira:
        return "简化流程"
    if story_points is not None and story_points <= 3:
        return "简化流程"
    if duration is not None and duration <= 1 and story_points is not None and story_points < 3:
        return "简化流程"
    return "待确认"


COMPLETION_ONLY_PATTERNS = [
    r"^测试完成$",
    r"^测试通过$",
    r"^验证通过$",
    r"^已测完$",
    r"^待发布$",
    r"^已发布$",
    r"^已上线$",
    r"测试完成[，,。\\s]*(待发布|已发布|已上线|产品验收中|验收中)?$",
    r"测试通过[，,。\\s]*(待发布|已发布|已上线|产品验收中|验收中)?$",
    r"验证通过[，,。\\s]*(待发布|已发布|已上线)?$",
]


SCHEDULE_ONLY_COMPLETION_RE = re.compile(
    r"(测试完成时间|测试时间|完成时间).*(顺延|延期|延后|调整|更新)|"
    r"(顺延|延期|延后|调整|更新).*(测试完成时间|测试时间|完成时间)",
    re.I,
)


SIMPLE_COMPLETION_HANDOFF_RE = re.compile(
    r"(测试完成|测试通过|验证通过|验证完成|已测完).*(请|麻烦|通知|同步)?.*验收|"
    r"(测试完成|测试通过|验证通过|验证完成|已测完).*(请|麻烦|辛苦)\s*(\[~[^\]]+\]|@[A-Za-z0-9_.@-]+)|"
    r"(测试完成|测试通过|验证通过|验证完成|已测完).*(可以|可)(发布|上线)",
    re.I,
)


def classify_test_report(text):
    t = norm(text)
    if t in {"有测试报告", "有测试结论", "仅测试完成备注", "缺测试报告/结论", "待确认：链接无法打开"}:
        return t
    if not t or re.fullmatch(r"(缺失|缺|无|未见|没有|N/A|NA)", t, re.I):
        return "缺测试报告/结论"
    if SCHEDULE_ONLY_COMPLETION_RE.search(t):
        return "缺测试报告/结论"
    if re.search(r"打不开|无法打开|无权限|权限不足|无法确认|链接失效|404|访问受限", t):
        return "待确认：链接无法打开"
    has_link = bool(re.search(r"https?://|wiki/|lark|Lark|飞书|文档|链接", t, re.I))
    if re.search(r"测试报告|测试完成报告|测试总结|报告链接", t):
        return "有测试报告"
    if has_link and re.search(r"测试报告|report|报告|测试总结", t, re.I):
        return "有测试报告"
    if SIMPLE_COMPLETION_HANDOFF_RE.search(t):
        return "有测试结论"
    if any(re.search(p, t, re.I) for p in COMPLETION_ONLY_PATTERNS):
        return "仅测试完成备注"
    has_scope = re.search(r"测试范围|覆盖范围|测试内容|验证范围|回归范围|功能点", t)
    has_result = re.search(r"测试结论|测试结果|验证结果|结论|通过|不通过|完成", t)
    has_risk = re.search(r"遗留|风险|阻塞|问题|线上验证|待观察|无需回归|无风险", t)
    if has_scope and has_result and (has_risk or len(t) >= 40):
        return "有测试结论"
    if re.search(r"测试结论|测试结果|验证结果", t) and len(t) >= 20:
        return "有测试结论"
    if re.search(r"测试完成|验证通过|已测完|待发布|已发布|已上线", t):
        return "仅测试完成备注"
    return "缺测试报告/结论"


NOT_SUBMITTED_STATUS_RE = re.compile(r"需求池|开发中|待开发|待提测|联调中|实现中")
TESTING_IN_PROGRESS_STATUS_RE = re.compile(r"测试中|已提测|待测试")


def row_status(row):
    return first_value(row, ["状态", "status", "Status"])


def is_not_submitted_to_qa(row):
    return bool(NOT_SUBMITTED_STATUS_RE.search(row_status(row)))


def is_testing_in_progress_without_completion(row, finish):
    if not TESTING_IN_PROGRESS_STATUS_RE.search(row_status(row)):
        return False
    return is_missing(finish) or bool(re.search(r"未见.*已测试|未见.*测试完成", finish))


SELF_TEST_EVIDENCE_RE = re.compile(r"自测报告|自测文档|自测结果|提测报告|提测文档", re.I)


def classify_self_test(text):
    t = norm(text)
    if t in {"有自测报告", "缺自测报告"}:
        return t
    if not t or re.fullmatch(r"(缺失|缺|无|未见|没有|N/A|NA|-)", t, re.I):
        return "缺自测报告"
    if re.search(r"链接未标注|未标注自测|未标注提测|仅链接|无标签", t, re.I):
        return "缺自测报告"
    if re.search(r"打不开|无法打开|无权限|权限不足|链接失效|404|访问受限", t) and SELF_TEST_EVIDENCE_RE.search(t):
        return "待确认：链接无法打开"
    if SELF_TEST_EVIDENCE_RE.search(t):
        return "有自测报告"
    return "缺自测报告"


def has_table_style_test_cases(text):
    t = norm(text)
    if not t:
        return False
    headers = ["用例ID", "场景", "前置条件", "操作", "预期结果"]
    header_hits = sum(1 for h in headers if h in t)
    case_ids = len(re.findall(r"TC[-_ ]?\d+|用例\s*\d+", t, re.I))
    return header_hits >= 3 and case_ids >= 1


def is_missing(text):
    t = norm(text)
    if not t:
        return True
    return has_any(t, [r"缺", r"无$", r"未", r"没有", r"待补", r"N/A", r"NA"])


def has_traceable_case_link(text):
    t = norm(text)
    if is_missing(t):
        return False
    if re.search(r"https?://|wiki/|jira|JIRA|lark|Lark|用例链接|测试用例|case|Case|链接|文档|表格", t):
        return True
    # Accept explicit dated case notes, but flag generic "有" elsewhere as weak.
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}.*(用例|测试点|评审)", t):
        return True
    return False


def classify_case_review(text):
    t = norm(text)
    if not t or re.fullmatch(r"(缺失|缺|无|未见|没有|N/A|NA|-)", t, re.I):
        return "缺失评审"
    if re.search(r"缺(失)?(用例/)?评审|缺用例/评审|未见用例/评审|无评审|没有评审", t):
        return "缺失评审"
    if re.search(r"未见评审结论|未见用例评审结论|未见通过/不通过结论", t):
        return "未见用例评审结论"
    if re.search(r"不通过|打回|覆盖不足|质量问题", t):
        return "用例评审不通过"
    if re.search(r"用例评审通过|评审通过|评审已通过", t):
        return "用例评审通过"
    if re.search(r"(测试用例|用例|case).{0,20}(已评审|评审完成|已完成评审)", t, re.I):
        return "用例评审通过"
    if re.search(r"(已评审|评审完成|已完成评审).{0,20}(测试用例|用例|case)", t, re.I):
        return "用例评审通过"
    if t in {"已评审", "评审完成", "已完成评审"}:
        return "用例评审通过"
    if re.search(r"评审|review", t, re.I):
        return "未见用例评审结论"
    return "缺失评审"


def looks_positive(text):
    t = norm(text)
    return bool(t) and has_any(t, POSITIVE_PATTERNS) and not has_any(t, [r"缺", r"未", r"不通过", r"不规范"])


def has_gate_evidence(row):
    evidence = "\n".join(
        norm(row.get(name))
        for name in [
            "自测报告",
            "提测报告",
            "提测文档",
            "准入/冒烟/准出留痕",
            "准入记录",
            "冒烟记录",
            "准出记录",
            "测试报告",
            "风险同步/闭环记录",
            "验收/线上问题",
        ]
    )
    if not evidence:
        return False
    if re.search(r"缺|未见|没有|无留痕|N/A|NA", evidence, re.I) and not re.search(
        r"自测|提测|准入|冒烟|准出|测试报告|验收通过|测试完成|验证通过|已同步|闭环|风险",
        evidence,
        re.I,
    ):
        return False
    return bool(
        re.search(
            r"自测报告|自测文档|自测结果|提测报告|提测文档|准入|冒烟|准出|测试报告|测试完成|验证通过|验收通过|已同步|闭环|风险说明|风险同步",
            evidence,
            re.I,
        )
    )


def read_rows(path, fmt):
    delimiter = "\t" if fmt == "tsv" else ","
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader), reader.fieldnames or []


def audit_row(row):
    issues = []
    manual = []
    row_findings = []

    jira = norm(row.get("JIRA单"))
    flow_type = infer_process_type(row)
    story_points = parse_number(first_value(row, ["Story Points", "Story points", "SP点数", "SP", "故事点"]))
    case_review_required = story_points is None or story_points >= 3
    pre_submit_case = norm(row.get("提测前完成测试用例产出"))
    case_record = norm(row.get("用例/评审记录"))
    case_content = norm(first_value(row, ["测试用例是否编写", "测试用例内容是否有效"]))
    impact_assessment = norm(row.get("全局影响面评估分析是否完整"))
    self_test = classify_self_test(row.get("自测报告"))
    test_report = classify_test_report(row.get("测试报告"))
    acceptance = norm(row.get("验收/线上问题"))
    risk = norm(row.get("风险同步/闭环记录"))
    bug_record = norm(row.get("Bug记录是否规范"))
    finish = norm(row.get("实际测试完成"))
    standard_flow = ("标准" in flow_type) or flow_type == "待确认"
    not_submitted = is_not_submitted_to_qa(row)
    testing_in_progress = is_testing_in_progress_without_completion(row, finish)
    requires_case_artifacts = standard_flow and not not_submitted
    requires_completion_evidence = not not_submitted and not testing_in_progress

    pre_submit_case_missing = not has_traceable_case_link(pre_submit_case)
    case_review_status = classify_case_review(case_record)
    case_review_missing = case_review_status == "缺失评审"

    if requires_case_artifacts:
        if pre_submit_case_missing:
            issues.append("提测前缺测试用例链接")
            row_findings.append("提测前未见用例产出")
        elif re.search(r"只有|无链接|未评审|待补|后补", pre_submit_case):
            issues.append("提测前用例产出证据较弱")
            row_findings.append("提测前用例产出证据较弱")
            manual.append("确认提测前是否已有可追溯测试用例链接")

        if not case_review_required and case_review_missing:
            pass
        elif case_review_status == "未见用例评审结论":
            issues.append("用例评审结论不明确")
            row_findings.append("用例评审结论待确认")
            manual.append("未见用例评审结论")
        elif case_review_missing:
            if pre_submit_case_missing:
                issues.append("缺用例评审记录（已按缺用例处理）")
                row_findings.append("未见用例/评审记录")
                manual.append("已按用例未编写处理时，不重复按评审不通过扣分")
            else:
                issues.append("缺用例评审记录")
                row_findings.append("未见用例/评审记录")
                manual.append("确认是否按用例评审记录缺失计入")
        elif case_review_status == "用例评审不通过":
            issues.append("用例评审不通过")
            row_findings.append("用例评审不通过")

        if case_content:
            if has_table_style_test_cases(case_content):
                pass
            elif re.search(r"用例有效|有效|实际用例|测试点|可执行场景|非空", case_content):
                pass
            elif re.search(r"无效|仅有|空白|空表|占位|未见实际|缺失", case_content):
                issues.append("测试用例内容无效")
                row_findings.append("测试用例内容无效")
            elif re.search(r"待确认|读取不完整", case_content):
                issues.append("测试用例内容需确认")
                row_findings.append("测试用例内容待确认")
                manual.append("确认六. 测试用例是否有实际测试点/用例图/表格内容")

        if re.search(r"待确认|读取不完整|章节未展开", impact_assessment):
            if re.search(r"画板|board|节点不可读", impact_assessment, re.I):
                row_findings.append("待确认：画板节点不可读")
            else:
                row_findings.append("全局影响面评估待确认")
            manual.append("确认涉及且需覆盖的影响项是否已补充具体影响点并转用例")
        elif is_missing(impact_assessment):
            issues.append("缺全局影响面评估记录")
            row_findings.append("全局影响面评估缺失")
            manual.append("确认用例文档是否存在全局影响面评估")
        elif re.search(r"不完整|缺少|读取不完整", impact_assessment):
            issues.append("全局影响面评估不完整")
            row_findings.append("全局影响面评估不完整")
            manual.append("确认涉及且需覆盖的影响项是否已补充具体影响点并转用例")

    if standard_flow and not not_submitted and is_missing(self_test):
        issues.append("标准流程缺自测报告")
        row_findings.append("缺自测报告")
    if standard_flow and not not_submitted and not has_gate_evidence(row):
        issues.append("关键门禁无留痕")
        row_findings.append("未见准入/冒烟/准出留痕")

    if not requires_completion_evidence:
        pass
    elif standard_flow and test_report in {"缺测试报告/结论", "仅测试完成备注", "有测试结论"}:
        issues.append("标准流程缺测试报告")
        row_findings.append(test_report)
    elif standard_flow and test_report.startswith("待确认"):
        issues.append("标准流程测试报告需确认")
        row_findings.append(test_report)
    elif (not standard_flow) and test_report == "缺测试报告/结论":
        issues.append("简化流程缺完成结论")
        row_findings.append("缺测试结论备注")

    if requires_completion_evidence and (is_missing(finish) or re.search(r"延期|未完成|阻塞", finish)):
        issues.append("测试完成状态异常")
        row_findings.append("测试完成状态异常，待确认")
        manual.append("确认是否因测试侧原因影响项目节奏")

    if acceptance and not re.search(r"验收通过|无|无关联|非测试|优化项", acceptance):
        issues.append("验收/线上问题需确认")
        row_findings.append("验收/线上问题待确认")
        manual.append("确认是否测试逃逸、是否主流程、是否测试范围内")

    if not risk or re.search(r"缺|未见|没有|待补", risk):
        issues.append("缺风险同步/闭环记录")
        row_findings.append("未见风险同步/闭环记录")
        manual.append("确认是否存在已知风险未同步或未闭环")

    if bug_record and not re.search(r"无关联Bug|规范|无$", bug_record):
        if re.search(r"不规范|缺|未记录|无法复现|复现步骤", bug_record):
            issues.append("Bug记录不规范")
            row_findings.append("Bug记录不规范")
        elif re.search(r"P0|P1|P2|P3|Bug", bug_record, re.I):
            issues.append("存在关联 Bug")
            row_findings.append("存在关联 Bug，需确认是否测试逃逸")
            manual.append("确认 Bug 等级、是否线上漏测、是否测试侧责任")

    if not row_findings:
        row_findings.append("无")

    return {
        "row": row,
        "jira": jira,
        "flow_type": flow_type,
        "test_report": test_report,
        "not_submitted_to_qa": not_submitted,
        "testing_in_progress": testing_in_progress,
        "issues": issues,
        "row_findings": row_findings,
        "deductions": row_findings,
        "manual_confirmations": manual,
    }


def summarize(results):
    issue_counts = {}
    row_finding_counts = {}
    manual_count = 0
    for result in results:
        for issue in result["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for finding in result["row_findings"]:
            if finding == "无":
                continue
            row_finding_counts[finding] = row_finding_counts.get(finding, 0) + 1
        manual_count += len(result["manual_confirmations"])
    monthly_suggestions = []
    missing_cases = issue_counts.get("提测前缺测试用例链接", 0)
    if missing_cases:
        if missing_cases > 3:
            monthly_suggestions.append(f"提测前未见用例产出共 {missing_cases} 个需求，超过 3 个，按规则本项扣 5 分。")
            monthly_suggestions.append("用例未编写超过 3 次，“完成需求分析、影响范围识别和测试设计沉淀”项建议不得分。")
        else:
            monthly_suggestions.append(f"提测前未见用例产出共 {missing_cases} 个需求，按规则逐项评估扣分。")
    missing_gate_evidence = row_finding_counts.get("未见准入/冒烟/准出留痕", 0)
    missing_self_test = row_finding_counts.get("缺自测报告", 0)
    if missing_gate_evidence:
        monthly_suggestions.append(f"标准流程准入/冒烟/准出等关键门禁无留痕共 {missing_gate_evidence} 个需求，按每次扣 5 分。")
    if missing_self_test:
        monthly_suggestions.append(f"标准流程未见自测报告共 {missing_self_test} 个需求，按门禁规则每次扣 5 分，单项月度封顶 15 分。")
    missing_reports = row_finding_counts.get("缺测试报告/结论", 0)
    missing_simple_conclusions = row_finding_counts.get("缺测试结论备注", 0)
    completion_only = row_finding_counts.get("仅测试完成备注", 0)
    conclusion_only = row_finding_counts.get("有测试结论", 0)
    standard_report_misses = issue_counts.get("标准流程缺测试报告", 0)
    simple_conclusion_misses = issue_counts.get("简化流程缺完成结论", 0)
    report_pending = sum(count for finding, count in row_finding_counts.items() if finding.startswith("待确认：链接无法打开"))
    if missing_reports:
        monthly_suggestions.append(f"缺测试报告/结论共 {missing_reports} 个需求，标准流程按缺测试报告评估。")
    if missing_simple_conclusions:
        monthly_suggestions.append(f"简化流程缺测试结论备注共 {missing_simple_conclusions} 个需求，按每次扣 3 分。")
    if completion_only:
        monthly_suggestions.append(f"仅测试完成备注共 {completion_only} 个需求，标准流程不等同于完整测试报告。")
    if conclusion_only:
        monthly_suggestions.append(f"仅测试结论共 {conclusion_only} 个需求，标准流程不等同于完整测试报告。")
    if report_pending:
        monthly_suggestions.append(f"测试报告链接无法确认共 {report_pending} 个需求，需确认链接权限和内容。")
    concise_kpi_rows = []
    if missing_cases:
        concise_kpi_rows.append(
            {
                "项目": "业务交付质量与效能",
                "问题": f"提测前未见用例产出 {missing_cases} 个" + ("，超过 3 个" if missing_cases > 3 else ""),
                "建议扣分": "扣 5 分" if missing_cases > 3 else "按次数评估",
            }
        )
        if missing_cases > 3:
            concise_kpi_rows.append(
                {
                    "项目": "测试专业能力与规范执行",
                    "问题": "用例未编写/提测前无用例超过 3 个，“需求分析、影响范围识别和测试设计沉淀”项不得分",
                    "建议扣分": "扣 15 分",
                }
            )
    gate_quality_parts = []
    gate_quality_deduction = 0
    if missing_gate_evidence:
        gate_quality_parts.append(f"标准流程准入/冒烟/准出等关键门禁无留痕 {missing_gate_evidence} 个")
        gate_quality_deduction += missing_gate_evidence * 5
    if missing_self_test:
        gate_quality_parts.append(f"标准流程未见自测报告 {missing_self_test} 个")
        gate_quality_deduction += missing_self_test * 5
    if standard_report_misses:
        report_details = []
        if missing_reports:
            report_details.append(f"缺测试报告/结论 {missing_reports} 个")
        if completion_only:
            report_details.append(f"仅测试完成备注 {completion_only} 个")
        if conclusion_only:
            report_details.append(f"仅测试结论 {conclusion_only} 个")
        detail_text = f"（{'，'.join(report_details)}）" if report_details else ""
        gate_quality_parts.append(f"标准流程缺测试报告 {standard_report_misses} 个{detail_text}")
        gate_quality_deduction += standard_report_misses * 3
    if simple_conclusion_misses:
        gate_quality_parts.append(f"简化流程缺测试结论备注 {simple_conclusion_misses} 个")
        gate_quality_deduction += simple_conclusion_misses * 3
    if gate_quality_parts:
        gate_quality_capped = min(gate_quality_deduction, 15)
        if gate_quality_deduction > gate_quality_capped:
            gate_quality_parts.append("严格执行质量门禁和缺陷闭环子项按 15 分上限计")
        concise_kpi_rows.append(
            {
                "项目": "严格执行质量门禁和缺陷闭环",
                "问题": "；".join(gate_quality_parts),
                "建议扣分": f"扣 {gate_quality_capped} 分",
            }
        )
    if report_pending:
        concise_kpi_rows.append(
            {
                "项目": "测试专业能力与规范执行",
                "问题": f"测试报告链接无法确认 {report_pending} 个",
                "建议扣分": "需人工确认",
            }
        )
    return {
        "issue_counts": issue_counts,
        "row_finding_counts": row_finding_counts,
        "deduction_counts": row_finding_counts,
        "monthly_deduction_suggestions": monthly_suggestions,
        "concise_kpi_rows": concise_kpi_rows,
        "manual_confirmation_count": manual_count,
    }


def summarize_workload_overload(rows):
    summaries = summarize_workload_bonus(rows)
    return [
        {"测试人员": row["测试人员"], "月份": row["月份"], "等效测试工日": row["当月工时统计/天"], "负载判断": "过载"}
        for row in summaries
        if parse_number(str(row["当月工时统计/天"])) is not None and parse_number(str(row["当月工时统计/天"])) >= 29
    ]


def workload_bonus_label(days):
    if days is None:
        return "-"
    if days >= 29:
        return "建议加 3-5 分"
    if days >= 25:
        return "加 1 分"
    return "-"


def workload_bonus_suggestion(days):
    if days is None:
        return "-"
    if days >= 29:
        return "3-5 分，由主管根据本月表现判断"
    if days >= 25:
        return "+1 分"
    return "-"


def workload_threshold_text(days):
    if days is None:
        return "-"
    if days >= 29:
        return f"全部有效统计工作日 {days:g} 天，>=29 天"
    if days >= 25:
        return f"全部有效统计工作日 {days:g} 天，>=25 天"
    return f"全部有效统计工作日 {days:g} 天"


def workload_row_text(days):
    if days is None:
        return "-"
    return f"全部有效统计工作日 {days:g} 天"


def format_points(value):
    if value is None:
        return "-"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return str(int(value))
    return f"{value:g}"


def parse_score_range(text, keyword):
    t = norm(str(text))
    if keyword and keyword not in t:
        return None
    if re.search(r"需人工|待确认|确认后|按次数|封顶|最多", t):
        return None
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-~至]\s*(\d+(?:\.\d+)?)\s*分", t)
    if range_match:
        return (float(range_match.group(1)), float(range_match.group(2)))
    match = re.search(r"(\d+(?:\.\d+)?)\s*分", t)
    if match:
        value = float(match.group(1))
        return (value, value)
    return None


def add_ranges(ranges):
    lows = [r[0] for r in ranges if r]
    highs = [r[1] for r in ranges if r]
    if not lows:
        return None
    return (sum(lows), sum(highs))


def score_summary(summary):
    explicit_deduction = summary.get("预计总扣分") or summary.get("预计扣分") or summary.get("总扣分")
    explicit_bonus = summary.get("预计加分") or summary.get("加分")
    explicit_final = summary.get("预计最终得分") or summary.get("预计得分") or summary.get("最终得分")
    if explicit_deduction is not None and explicit_bonus is not None and explicit_final is not None:
        return f"预计总扣分 {explicit_deduction}，预计加分 {explicit_bonus}，预计最终得分 {explicit_final}。"

    deduction_ranges = [
        parse_score_range(row.get("建议扣分", ""), "扣")
        for row in summary.get("concise_kpi_rows", [])
    ]
    deduction = parse_score_range(str(explicit_deduction), "") if explicit_deduction is not None else add_ranges(deduction_ranges)

    bonus_ranges = []
    if explicit_bonus is not None:
        bonus_ranges.append(parse_score_range(str(explicit_bonus), ""))
    else:
        for row in summary.get("workload_bonus", []):
            days = parse_number(str(row.get("当月工时统计/天")))
            suggestion = workload_bonus_suggestion(days)
            if suggestion == "+1 分":
                bonus_ranges.append((1, 1))
            elif suggestion.startswith("3-5"):
                bonus_ranges.append((3, 5))
    bonus = add_ranges(bonus_ranges)

    if not deduction and not bonus:
        return "预计总扣分 0 分，预计加分 0 分，预计最终得分 100 分。"
    deduction = deduction or (0, 0)
    bonus = bonus or (0, 0)
    final_low = 100 - deduction[1] + bonus[0]
    final_high = 100 - deduction[0] + bonus[1]
    deduction_text = format_points(deduction[0]) if deduction[0] == deduction[1] else f"{format_points(deduction[0])}-{format_points(deduction[1])}"
    bonus_text = format_points(bonus[0]) if bonus[0] == bonus[1] else f"{format_points(bonus[0])}-{format_points(bonus[1])}"
    final_text = format_points(final_low) if final_low == final_high else f"{format_points(final_low)}-{format_points(final_high)}"
    qualifier = "约 " if summary.get("manual_confirmation_count", 0) else ""
    return f"预计总扣分 {qualifier}{deduction_text} 分，预计加分 +{bonus_text} 分，预计最终得分 {qualifier}{final_text} 分。"


MODULES = [
    ("业务交付质量与效能", 30),
    ("重点工作", 25),
    ("测试专业能力与规范执行", 45),
]


def add_range(a, b):
    if not a:
        return b
    if not b:
        return a
    return (a[0] + b[0], a[1] + b[1])


def clamp_range(value, low, high):
    return (max(low, min(high, value[0])), max(low, min(high, value[1])))


def format_range(value):
    if not value:
        return "0"
    if value[0] == value[1]:
        return format_points(value[0])
    return f"{format_points(value[0])}-{format_points(value[1])}"


def module_for_kpi_item(item):
    text = norm(item)
    if "业务交付质量与效能" in text:
        return "业务交付质量与效能"
    if "重点" in text:
        return "重点工作"
    return "测试专业能力与规范执行"


def deduction_basis(row):
    issue = str(row.get("问题") or "").strip()
    suggestion = str(row.get("建议扣分") or "").strip()
    if suggestion.startswith("扣"):
        return f"{issue}，{suggestion}"
    return issue


def workload_bonus_ranges(summary):
    bonus = None
    basis = []
    for row in summary.get("workload_bonus", []):
        days = parse_number(str(row.get("当月工时统计/天")))
        suggestion = workload_bonus_suggestion(days)
        if suggestion == "+1 分":
            bonus = add_range(bonus, (1, 1))
            basis.append(f"{workload_threshold_text(days)}，加 1 分")
        elif suggestion.startswith("3-5"):
            bonus = add_range(bonus, (3, 5))
            basis.append(f"{workload_threshold_text(days)}，建议加 3-5 分")
    return bonus or (0, 0), basis


def extract_jira_key(text):
    match = re.search(r"\b[A-Z]+-\d+\b", str(text or ""))
    return match.group(0) if match else str(text or "").strip()


def keys_text(keys):
    keys = [key for key in keys if key]
    if not keys:
        return ""
    if len(keys) <= 6:
        return "、".join(keys)
    return "、".join(keys[:6]) + f" 等 {len(keys)} 个需求"


def module_score_summary(summary, results):
    deductions = {name: (0, 0) for name, _ in MODULES}
    basis = {name: [] for name, _ in MODULES}
    for row in summary.get("concise_kpi_rows", []):
        deduction = parse_score_range(row.get("建议扣分", ""), "扣")
        if not deduction:
            continue
        module = module_for_kpi_item(row.get("项目", ""))
        deductions[module] = add_range(deductions[module], deduction)
        basis[module].append(deduction_basis(row))

    bonus, bonus_basis = workload_bonus_ranges(summary)
    basis["业务交付质量与效能"].extend(bonus_basis)

    bug_keys = []
    for result in results:
        bug_text = str(result.get("row", {}).get("Bug记录是否规范", ""))
        match = re.search(r"不规范\s*(\d+)\s*个", bug_text)
        if match and int(match.group(1)) > 0:
            bug_keys.append(extract_jira_key(result.get("jira")))
    if bug_keys and not basis["重点工作"]:
        basis["重点工作"].append("暂未确认重点需求范围，Bug 规范问题暂不计入扣分")

    rows = []
    score_total = (0, 0)
    deduction_total = (0, 0)
    for name, max_score in MODULES:
        module_bonus = bonus if name == "业务交付质量与效能" else (0, 0)
        module_score = (
            max_score - deductions[name][1] + module_bonus[0],
            max_score - deductions[name][0] + module_bonus[1],
        )
        module_score = clamp_range(module_score, 0, max_score)
        score_total = add_range(score_total, module_score)
        deduction_total = add_range(deduction_total, deductions[name])
        rows.append(
            {
                "模块": name,
                "满分": max_score,
                "得分": module_score,
                "主要依据": "；".join(basis[name]) if basis[name] else "无已确认扣分项",
            }
        )
    return rows, score_total, deduction_total, bonus


def infer_scope_text(rows, summary):
    testers = sorted({first_value(row, ["测试人员", "测试介入人", "人员", "QA"]) for row in rows} - {""})
    if not testers:
        testers = sorted({str(row.get("测试人员") or "") for row in summary.get("workload_bonus", [])} - {""})
    months = sorted({str(row.get("月份") or "") for row in summary.get("workload_bonus", [])} - {""})
    if not months:
        for row in rows:
            dt = parse_date(first_value(row, ["时间", "预计测试开始时间", "测试介入时间"]))
            if dt:
                months.append(dt.strftime("%Y-%m"))
                break
    tester_text = "、".join(testers) if testers else "目标人员"
    month_text = "、".join(months) if months else "目标月份"
    return f"本次审计范围为 {tester_text} 在 {month_text} 的 Jira/Lark 记录，共 {len(rows)} 个需求。"


def pending_summary_sentence(results):
    online = []
    overdue = []
    bug_norm = []
    for result in results:
        row = result.get("row", {})
        key = extract_jira_key(result.get("jira"))
        if first_value(row, ["验收/线上问题"]) not in ("", "-", "无"):
            online.append(key)
        if str(first_value(row, ["实际测试完成"])).startswith("超期"):
            overdue.append(key)
        bug_text = str(row.get("Bug记录是否规范", ""))
        match = re.search(r"不规范\s*(\d+)\s*个", bug_text)
        if match and int(match.group(1)) > 0:
            bug_norm.append(key)
    parts = []
    if online:
        parts.append(f"{keys_text(online)} 的验收/线上问题责任归属")
    if overdue:
        parts.append(f"{keys_text(overdue)} 的超期是否测试侧原因")
    if bug_norm:
        parts.append(f"{keys_text(bug_norm)} 的重点需求 Bug 规范扣分适用范围")
    if not parts:
        manual_keys = [extract_jira_key(result.get("jira")) for result in results if result.get("manual_confirmations")]
        if manual_keys:
            parts.append(f"{keys_text(manual_keys)} 的待确认项")
    if not parts:
        return ""
    return "该分数暂未计入待确认项：" + "、".join(parts) + "。"


def summarize_workload_bonus(rows):
    by_person_month = {}
    for row in rows:
        person = first_value(row, ["测试人员", "测试介入人", "人员", "QA"])
        if not person:
            continue
        month = first_value(row, ["月份", "时间周期"])
        if not month:
            start = parse_date(first_value(row, ["预计测试开始", "预计测试开始时间", "测试开始", "测试开始时间", "时间"]))
            month = start.strftime("%Y-%m") if start else ""
        if not month:
            continue
        workdays = parse_number(first_value(row, ["等效测试工日", "测试工日", "工作日"]))
        if workdays is None:
            workdays = get_test_duration_days(row)
        if workdays is None:
            continue
        by_person_month[(person, month)] = by_person_month.get((person, month), 0) + workdays
    return [
        {
            "测试人员": person,
            "月份": month,
            "当月工时统计/天": int(days) if float(days).is_integer() else round(days, 2),
            "加分项": workload_bonus_label(days),
        }
        for (person, month), days in sorted(by_person_month.items())
    ]


REPORT_COLUMNS = [
    "时间",
    "JIRA单",
    "状态",
    "流程类型",
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
    "月度工作量加分在汇总项统计",
    "扣分项",
]


def markdown_cell(value):
    text = str(value or "-").strip() or "-"
    return text.replace("\n", " ").replace("|", "\\|")


def report_row_value(result, column):
    row = result.get("row", {})
    not_submitted = result.get("not_submitted_to_qa") or is_not_submitted_to_qa(row)
    flow_type = result.get("flow_type") or first_value(row, ["流程类型"])
    simplified_flow = "简化" in flow_type
    if not_submitted:
        not_due_values = {
            "实际测试完成": "未到产出节点：测试完成暂不要求",
            "提测前完成测试用例产出": "未到产出节点：测试用例暂不要求",
            "用例/评审记录": "未到产出节点：用例评审暂不要求",
            "测试用例是否编写": "未到产出节点：测试用例暂不要求",
            "全局影响面评估分析是否完整": "未到产出节点：影响面评估暂不要求",
            "自测报告": "未到产出节点：自测报告暂不要求",
            "测试报告": "未到产出节点：测试报告暂不要求",
        }
        if column in not_due_values:
            return not_due_values[column]
    if simplified_flow:
        simplified_values = {
            "提测前完成测试用例产出": "简化流程暂不要求测试用例",
            "用例/评审记录": "简化流程暂不要求用例评审",
            "测试用例是否编写": "简化流程暂不要求测试用例",
            "全局影响面评估分析是否完整": "简化流程暂不要求影响面评估",
            "自测报告": "简化流程暂不要求自测报告",
        }
        if column in simplified_values:
            return simplified_values[column]
    if column == "流程类型":
        return flow_type or "-"
    if column == "测试报告":
        test_report = result.get("test_report") or "-"
        if simplified_flow and test_report == "缺测试报告/结论":
            return "缺测试结论备注"
        return test_report
    if column == "用例/评审记录":
        return classify_case_review(first_value(row, [column]))
    if column == "测试用例是否编写":
        value = first_value(row, ["测试用例是否编写", "测试用例内容是否有效"]) or "-"
        return value.replace("画板未读", "内容无法读取")
    if column == "全局影响面评估分析是否完整":
        value = first_value(row, [column]) or "-"
        if value == "缺失":
            return "缺影响面评估"
        return value.replace("画板未读", "内容无法读取")
    if column == "自测报告":
        return classify_self_test(row.get(column))
    if column == "Bug记录是否规范":
        value = first_value(row, [column]) or "-"
        if "疑似不规范" in value:
            match = re.search(r"(\d+)\s*个\s*Bug", value, re.I)
            count = match.group(1) if match else "N"
            return f"关联 Bug {count} 个；待确认：Bug详情未打开"
        return value
    if column == "月度工作量加分在汇总项统计":
        return first_value(row, ["月度工作量加分在汇总项统计", "加分项"]) or "-"
    if column == "扣分项":
        findings = [item for item in result.get("row_findings", []) if item and item != "无"]
        return "；".join(findings) if findings else "无"
    return first_value(row, [column]) or "-"


def markdown_report(rows, results, summary):
    lines = []
    lines.append("一、月度结论摘要")
    lines.append("")
    lines.append(infer_scope_text(rows, summary))
    lines.append("")
    module_rows, total_score, total_deduction, total_bonus = module_score_summary(summary, results)
    lines.append(f"当前明确测算得分为 {format_range(total_score)}/100，其中：")
    lines.append("")
    lines.append("| 模块 | 得分 | 主要依据 |")
    lines.append("|---|---:|---|")
    for row in module_rows:
        lines.append(
            "| {module} | {score}/{max_score} | {basis} |".format(
                module=markdown_cell(row["模块"]),
                score=markdown_cell(format_range(row["得分"])),
                max_score=markdown_cell(row["满分"]),
                basis=markdown_cell(row["主要依据"]),
            )
        )
    lines.append(
        "| 合计 | {score}/100 | 明确扣 {deduction} 分，加 {bonus} 分 |".format(
            score=markdown_cell(format_range(total_score)),
            deduction=markdown_cell(format_range(total_deduction)),
            bonus=markdown_cell(format_range(total_bonus)),
        )
    )
    pending_sentence = pending_summary_sentence(results)
    if pending_sentence:
        lines.append("")
        lines.append(pending_sentence)
    lines.append("")

    lines.append("二、扣分/加分建议")
    lines.append("")
    lines.append("| 结论 | 项目 | 问题 | 建议 |")
    lines.append("|---|---|---|---|")
    concise_rows = summary.get("concise_kpi_rows", [])
    if concise_rows:
        for row in concise_rows:
            lines.append(
                "| 明确扣分 | {项目} | {问题} | {建议扣分} |".format(
                    项目=markdown_cell(row.get("项目")),
                    问题=markdown_cell(row.get("问题")),
                    建议扣分=markdown_cell(row.get("建议扣分")),
                )
            )
    else:
        lines.append("| 暂不扣 | SOP留痕 | 未发现明显 SOP 缺失 | 暂不扣 |")
    workload_bonus = summary.get("workload_bonus", [])
    if workload_bonus:
        for row in workload_bonus:
            lines.append(
                "| 加分 | 工作量加分 | {person} {problem} | {suggestion} |".format(
                    person=markdown_cell(row.get("测试人员")),
                    problem=markdown_cell(workload_threshold_text(parse_number(str(row.get("当月工时统计/天"))))),
                    suggestion=markdown_cell(workload_bonus_suggestion(parse_number(str(row.get("当月工时统计/天"))))),
                )
            )
    lines.append("| 暂不扣 | 交付节奏 | 未发现明确测试侧延期时适用 | 暂不扣 |")
    lines.append("")

    lines.append("三、关键确认项")
    lines.append("")
    if summary["manual_confirmation_count"]:
        lines.append("| 确认项 | 涉及单子 | 影响 |")
        lines.append("|---|---|---|")
        manual_jiras = [result["jira"] for result in results if result["manual_confirmations"]]
        lines.append(
            "| 待确认项 | {} | 仅影响责任归因或是否纳入扣分 |".format(
                markdown_cell("、".join(manual_jiras) if manual_jiras else "-")
            )
        )
    else:
        lines.append("关键确认项：无")
    lines.append("")

    lines.append("四、逐单检查表")
    lines.append("")
    lines.append("| " + " | ".join(REPORT_COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(REPORT_COLUMNS)) + "|")
    workload_bonus = summary.get("workload_bonus", [])
    workload_by_person = {}
    fallback_workload = ""
    for row in workload_bonus:
        text = workload_row_text(parse_number(str(row.get("当月工时统计/天"))))
        workload_by_person[str(row.get("测试人员") or "").strip()] = text
        if not fallback_workload:
            fallback_workload = text
    for result in results:
        if not first_value(result.get("row", {}), ["月度工作量加分在汇总项统计", "加分项"]):
            person = first_value(result.get("row", {}), ["测试人员", "测试介入人", "人员", "QA"])
            workload_text = workload_by_person.get(person) or (fallback_workload if len(workload_bonus) == 1 else "")
            if workload_text:
                result = {**result, "row": {**result.get("row", {}), "月度工作量加分在汇总项统计": workload_text}}
        values = [markdown_cell(report_row_value(result, column)) for column in REPORT_COLUMNS]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Offline audit of already-collected monthly QA SOP evidence from CSV/TSV."
    )
    parser.add_argument("input", help="Input CSV/TSV file")
    parser.add_argument("--format", choices=["csv", "tsv"], default=None, help="Input format")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()

    path = Path(args.input)
    fmt = args.format
    if fmt is None:
        fmt = "tsv" if path.suffix.lower() == ".tsv" else "csv"

    rows, columns = read_rows(path, fmt)
    results = [audit_row(row) for row in rows]
    summary = summarize(results)
    workload_bonus = summarize_workload_bonus(rows)
    workload_overload = [
        {"测试人员": row["测试人员"], "月份": row["月份"], "等效测试工日": row["当月工时统计/天"], "负载判断": "过载"}
        for row in workload_bonus
        if parse_number(str(row["当月工时统计/天"])) is not None and parse_number(str(row["当月工时统计/天"])) >= 29
    ]
    summary["workload_bonus"] = workload_bonus
    payload = {
        "columns": columns,
        "missing_expected_columns": [c for c in EXPECTED_COLUMNS if c not in columns],
        "summary": summary,
        "workload_bonus": workload_bonus,
        "workload_overload": workload_overload,
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(rows, results, summary))


if __name__ == "__main__":
    main()
