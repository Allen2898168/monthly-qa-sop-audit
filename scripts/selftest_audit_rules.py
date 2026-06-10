#!/usr/bin/env python3
import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("audit_monthly_sop", SCRIPT_DIR / "audit_monthly_sop.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main():
    assert_equal(
        audit.infer_process_type(
            {
                "JIRA单": "WWLD-15000【数据服务】修改-合约影子币对接口",
                "业务模块": "数仓",
                "测试人员": "Sheep",
                "测试周期": "1",
            }
        ),
        "标准流程",
        "业务模块=数仓且有测试人员",
    )
    assert_equal(
        audit.infer_process_type(
            {
                "JIRA单": "WWLD-12494【风控审核】新增-提币审核-提币自动审核新增规则",
                "测试人员": "rain107774",
                "测试周期": "1",
            }
        ),
        "标准流程",
        "数仓组风控/数据类标题按标准流程",
    )
    assert_equal(
        audit.infer_process_type({"JIRA单": "WWLD-13435「OKR」大富翁世界杯活动", "Story Points": "2", "测试周期": "1"}),
        "标准流程",
        "标题包含 OKR",
    )
    assert_equal(
        audit.infer_process_type({"JIRA单": "WWLD-X 快速优化", "Story Points": "2", "测试周期": "1"}),
        "简化流程",
        "快速优化小单",
    )
    assert_equal(
        audit.infer_process_type({"JIRA单": "WWLD-Y 普通需求", "Story Points": "5", "测试周期": "1"}),
        "标准流程",
        "Story Points > 3",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-26",
                "预计测试完成时间": "2026-05-27",
            }
        ),
        1,
        "2026-05-27 新加坡假期排除",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-26",
                "预计测试完成时间": "2026-05-29",
            }
        ),
        3,
        "测试周期排除周末和新加坡假期",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-29",
                "预计测试完成时间": "2026-05-31",
            }
        ),
        1,
        "默认排除周末",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-29",
                "预计测试完成时间": "2026-05-31",
                "周末测试进度日期": "2026-05-30",
            }
        ),
        2,
        "周末有测试进度备注则计入有效工作日",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-15",
                "预计测试完成时间": "2026-05-18",
                "实际测试完成": "超期：05-20 09:35 备注测试完成（预计 05-18）",
            }
        ),
        2,
        "实际测试完成晚于预计时仍按计划测试窗口计算工日",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-15",
                "预计测试完成时间": "2026-05-18",
                "实际测试完成": "如期：05-15 11:53 备注测试完成",
            }
        ),
        2,
        "实际测试完成早于预计时仍按计划测试窗口计算工日",
    )
    assert_equal(
        audit.get_test_duration_days(
            {
                "预计测试开始时间": "2026-05-19",
                "预计测试完成时间": "2026-05-20",
                "实际测试完成": "5.19 下午 stg Doris 挂掉，测试完成时间顺延一天",
            }
        ),
        2,
        "测试完成时间顺延类排期备注不能当成完成备注",
    )
    assert_equal(audit.classify_test_report("https://x.example/report 测试报告"), "有测试报告", "测试报告链接")
    assert_equal(
        audit.classify_test_report("测试范围：后管、web；测试结果：通过；遗留风险：无"),
        "有测试结论",
        "完整测试结论",
    )
    assert_equal(audit.classify_test_report("测试完成"), "仅测试完成备注", "仅完成备注")
    assert_equal(audit.classify_test_report(""), "缺测试报告/结论", "缺报告结论")
    assert_equal(audit.classify_test_report("测试报告链接无法打开"), "待确认：链接无法打开", "链接无法打开")
    assert_equal(audit.classify_self_test("https://x.example/wiki/abc"), "缺自测报告", "未标注自测/提测报告的链接不算自测报告")
    assert_equal(audit.classify_self_test("https://x.example/wiki/abc 自测报告"), "有自测报告", "显式自测报告链接")
    assert_equal(audit.classify_self_test("待确认：链接未标注自测报告"), "缺自测报告", "链接未标注自测报告不能输出待确认")
    table_cases = """
    六、测试用例
    用例ID 场景 前置条件 操作 预期结果
    TC-01 用户满足现货活跃条件 近14天有现货订单 执行任务 加入现货活跃用户组
    TC-02 用户不满足任何交易条件 近14天无订单 执行任务 不在任何用户组中
    """
    if not audit.has_table_style_test_cases(table_cases):
        raise AssertionError("表格形式测试用例应判定为已编写")
    standard_with_conclusion = audit.audit_row(
        {
            "JIRA单": "WWLD-STD 标准流程",
            "流程类型": "标准流程",
            "Story Points": "5",
            "提测前完成测试用例产出": "有：https://case.example",
            "用例/评审记录": "用例评审通过",
            "测试用例是否编写": "有效",
            "全局影响面评估分析是否完整": "完整",
            "自测报告": "有自测报告",
            "测试报告": "有测试结论",
            "实际测试完成": "如期完成测试",
            "风险同步/闭环记录": "无",
            "Bug记录是否规范": "无关联Bug",
        }
    )
    if "标准流程缺测试报告" not in standard_with_conclusion["issues"]:
        raise AssertionError("标准流程只有测试结论时必须判定为缺测试报告")
    late_case_link = audit.audit_row(
        {
            "JIRA单": "WWLD-LATE-CASE 标准流程",
            "流程类型": "标准流程",
            "Story Points": "5",
            "提测前完成测试用例产出": "否，2026-05-20 才有用例链接 https://case.example",
            "用例/评审记录": "用例评审通过",
            "测试用例是否编写": "有效",
            "全局影响面评估分析是否完整": "完整",
            "自测报告": "有自测报告",
            "测试报告": "有测试报告",
            "实际测试完成": "如期完成测试",
            "风险同步/闭环记录": "有风险同步",
            "Bug记录是否规范": "无关联Bug",
        }
    )
    if "提测前缺测试用例链接" not in late_case_link["issues"]:
        raise AssertionError("用例链接晚于提测时，不能因为有链接就判定提测前用例合格")
    reviewed_case = audit.audit_row(
        {
            "JIRA单": "WWLD-REVIEW 标准流程",
            "流程类型": "标准流程",
            "Story Points": "5",
            "提测前完成测试用例产出": "有：https://case.example",
            "用例/评审记录": "测试用例（已评审）：https://case.example",
            "测试用例是否编写": "有效",
            "全局影响面评估分析是否完整": "完整",
            "自测报告": "有自测报告",
            "测试报告": "有测试报告",
            "实际测试完成": "如期完成测试",
            "风险同步/闭环记录": "有风险同步",
            "Bug记录是否规范": "无关联Bug",
        }
    )
    if any(finding in reviewed_case["row_findings"] for finding in ["用例评审结论待确认", "未见用例/评审记录"]):
        raise AssertionError("测试用例（已评审）应判定为用例评审通过，不能标记为缺评审或未见评审结论")
    assert_equal(
        audit.report_row_value(reviewed_case, "用例/评审记录"),
        "用例评审通过",
        "测试用例（已评审）最终表格归一为用例评审通过",
    )
    missing_gate_summary = audit.summarize(
        [
            audit.audit_row(
                {
                    "JIRA单": "WWLD-GATE 标准流程",
                    "流程类型": "标准流程",
                    "Story Points": "5",
                    "提测前完成测试用例产出": "有：https://case.example",
                    "用例/评审记录": "用例评审通过",
                    "测试用例是否编写": "有效",
                    "全局影响面评估分析是否完整": "完整",
                    "自测报告": "缺失",
                    "测试报告": "缺失",
                    "实际测试完成": "如期完成测试",
                    "风险同步/闭环记录": "无",
                    "Bug记录是否规范": "无关联Bug",
                }
            )
        ]
    )
    gate_rows = missing_gate_summary["concise_kpi_rows"]
    if not any(row["项目"] == "严格执行质量门禁和缺陷闭环" and row["建议扣分"] == "扣 5 分" for row in gate_rows):
        raise AssertionError("标准流程缺少准入/冒烟/准出等关键门禁留痕必须扣 5 分")
    gate_with_other_evidence = audit.summarize(
        [
            audit.audit_row(
                {
                    "JIRA单": "WWLD-GATE-EVIDENCE 标准流程",
                    "流程类型": "标准流程",
                    "Story Points": "5",
                    "提测前完成测试用例产出": "有：https://case.example",
                    "用例/评审记录": "用例评审通过",
                    "测试用例是否编写": "有效",
                    "全局影响面评估分析是否完整": "完整",
                    "自测报告": "缺失",
                    "测试报告": "有测试报告",
                    "实际测试完成": "如期完成测试",
                    "风险同步/闭环记录": "有风险同步",
                    "Bug记录是否规范": "无关联Bug",
                }
            )
        ]
    )
    if not any(
        row["项目"] == "严格执行质量门禁和缺陷闭环" and "自测报告" in row["问题"] and row["建议扣分"] == "扣 5 分"
        for row in gate_with_other_evidence["concise_kpi_rows"]
    ):
        raise AssertionError("标准流程缺自测报告时，即使存在其他测试/风险留痕，也必须按门禁项扣 5 分")
    overload = audit.summarize_workload_overload(
        [
            {"时间": "2026/5/1", "测试人员": "Rain", "等效测试工日": "28"},
            {"时间": "2026/5/1", "测试人员": "Sheep", "等效测试工日": "29"},
        ]
    )
    assert_equal(len(overload), 1, "只标记 >=29 工日过载")
    assert_equal(overload[0]["测试人员"], "Sheep", "过载人员")
    workload_bonus = audit.summarize_workload_bonus(
        [
            {"月份": "2026-05", "测试人员": "Rain", "等效测试工日": "24"},
            {"月份": "2026-05", "测试人员": "Sheep", "等效测试工日": "25"},
            {"月份": "2026-05", "测试人员": "Kayce", "等效测试工日": "29"},
        ]
    )
    bonus_by_person = {row["测试人员"]: row["加分项"] for row in workload_bonus}
    assert_equal(bonus_by_person["Rain"], "-", "24 工日不加分")
    assert_equal(bonus_by_person["Sheep"], "加 1 分", "25 工日加 1 分")
    assert_equal(bonus_by_person["Kayce"], "建议加 3-5 分", "29 工日建议加 3-5 分")
    rain_may_bonus = audit.summarize_workload_bonus(
        [
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-04", "预计测试完成时间": "2026-05-05", "实际测试完成": "如期：05-05 20:02 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-05", "预计测试完成时间": "2026-05-06", "实际测试完成": "如期：05-06 18:06 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-06", "预计测试完成时间": "2026-05-07", "实际测试完成": "如期：05-07 13:33 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-08", "预计测试完成时间": "2026-05-08", "实际测试完成": "如期：05-08 13:35 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-11", "预计测试完成时间": "2026-05-15", "实际测试完成": "如期：05-15 15:57 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-13", "预计测试完成时间": "2026-05-14", "实际测试完成": "如期：05-14 11:38 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-14", "预计测试完成时间": "2026-05-14", "实际测试完成": "如期：05-14 17:54 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-15", "预计测试完成时间": "2026-05-15", "实际测试完成": "未见测试完成备注；状态 05-18 09:12 已测试（超期）"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-15", "预计测试完成时间": "2026-05-18", "实际测试完成": "超期：05-20 09:35 备注测试完成（预计 05-18）"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-19", "预计测试完成时间": "2026-05-20", "实际测试完成": "如期：05-20 20:05 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-20", "预计测试完成时间": "2026-05-20", "实际测试完成": "如期：05-20 19:50 备注测试通过"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-26", "预计测试完成时间": "2026-05-28", "实际测试完成": "如期：05-28 09:10 备注测试完成"},
            {"月份": "2026-05", "测试人员": "Rain", "预计测试开始时间": "2026-05-26", "预计测试完成时间": "2026-05-28", "实际测试完成": "未见测试完成备注；状态 05-28 19:29 已测试（如期）"},
        ]
    )
    assert_equal(rain_may_bonus[0]["当月工时统计/天"], 25, "Rain 2026-05 planned workload")
    assert_equal(rain_may_bonus[0]["加分项"], "加 1 分", "Rain 25 工日加 1 分")
    report = audit.markdown_report(
        [
            {
                "时间": "2026/5/1",
                "JIRA单": "WWLD-1 测试需求",
                "测试人员": "Rain",
                "等效测试工日": "25",
            }
        ],
        [
            audit.audit_row(
                {
                    "时间": "2026/5/1",
                    "JIRA单": "WWLD-1 测试需求",
                    "测试人员": "Rain",
                    "等效测试工日": "25",
                    "Bug记录是否规范": "无关联Bug",
                }
            )
        ],
        {"manual_confirmation_count": 0, "concise_kpi_rows": [], "workload_bonus": [{"测试人员": "Rain", "月份": "2026-05", "当月工时统计/天": 25, "加分项": "加 1 分"}]},
    )
    for section in ["一、月度结论摘要", "二、扣分/加分建议", "三、关键确认项", "四、逐单检查表"]:
        if section not in report:
            raise AssertionError(f"Markdown report missing required section: {section}")
    required_header = "时间\tJIRA单\t状态\t流程类型\t实际测试完成\t提测前完成测试用例产出\t用例/评审记录\t测试用例是否编写\t全局影响面评估分析是否完整\t自测报告\t测试报告\t验收/线上问题\t风险同步/闭环记录\tBug记录是否规范\t月度工作量加分在汇总项统计\t扣分项"
    if required_header not in report:
        raise AssertionError("Report missing required TSV row-level columns")
    if "全部有效统计工作日 25 天" not in report:
        raise AssertionError("Row-level workload column must include concrete monthly workdays")
    if "加分\t工作量加分\tRain 全部有效统计工作日 25 天，>=25 天\t+1 分" not in report:
        raise AssertionError("Workload bonus row must include threshold text and bonus suggestion")
    if "| 结论 | 项目 | 问题 | 建议 |" in report or "| " + " | ".join(audit.REPORT_COLUMNS) + " |" in report:
        raise AssertionError("Formal report must use TSV/Lark-paste format, not Markdown pipe tables")
    for phrase in ["预计总扣分", "预计加分", "预计最终得分"]:
        if phrase not in report:
            raise AssertionError(f"Monthly conclusion must include {phrase}")
    weak_output = audit.markdown_report(
        [
            {
                "时间": "2026/5/1",
                "JIRA单": "WWLD-2 测试需求",
                "测试人员": "Rain",
                "测试用例是否编写": "待确认：画板未读",
                "全局影响面评估分析是否完整": "缺失",
                "自测报告": "缺失",
                "Bug记录是否规范": "1个Bug，1个疑似不规范",
            }
        ],
        [
            audit.audit_row(
                {
                    "时间": "2026/5/1",
                    "JIRA单": "WWLD-2 测试需求",
                    "测试人员": "Rain",
                    "测试用例是否编写": "待确认：画板未读",
                    "全局影响面评估分析是否完整": "缺失",
                    "自测报告": "缺失",
                    "Bug记录是否规范": "1个Bug，1个疑似不规范",
                }
            )
        ],
        {"manual_confirmation_count": 0, "concise_kpi_rows": [], "workload_bonus": []},
    )
    for forbidden in ["画板未读", "疑似不规范"]:
        if forbidden in weak_output:
            raise AssertionError(f"Markdown report contains forbidden wording: {forbidden}")
    if "待确认：Bug详情未打开" not in weak_output:
        raise AssertionError("疑似不规范 must be converted to Bug详情待确认, not a final non-compliant count")
    print("selftest passed")


if __name__ == "__main__":
    main()
