#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("audit_monthly_sop", SCRIPT_DIR / "audit_monthly_sop.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

COLLECT_SPEC = importlib.util.spec_from_file_location("collect_month", SCRIPT_DIR / "collect_month.py")
collect = importlib.util.module_from_spec(COLLECT_SPEC)
COLLECT_SPEC.loader.exec_module(collect)

LARK_SPEC = importlib.util.spec_from_file_location("lark_doc_fetch", SCRIPT_DIR / "lark_doc_fetch.py")
lark = importlib.util.module_from_spec(LARK_SPEC)
LARK_SPEC.loader.exec_module(lark)


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".env").write_text(
            "JIRA_URL=https://jira.example\n"
            "JIRA_USERNAME=user\n"
            "JIRA_TOKEN=token\n"
            "APP_ID=app\n"
            "APP_SECRET=secret\n",
            encoding="utf-8",
        )
        (root / ".env.local").write_text(
            "JIRA_URL=https://local.example\n"
            "JIRA_USERNAME=local\n"
            "JIRA_TOKEN=local-token\n"
            "APP_ID=local-app\n"
            "APP_SECRET=local-secret\n",
            encoding="utf-8",
        )
        old_cwd = Path.cwd()
        try:
            import os
            os.chdir(root)
            assert_equal(
                collect.resolve_env_path(
                    ".env",
                    collect.DEFAULT_JIRA_ENV_CANDIDATES,
                    ["JIRA_URL", "JIRA_USERNAME", "JIRA_TOKEN"],
                ),
                ".env",
                "默认优先使用工作区 .env",
            )
            (root / ".env").unlink()
            assert_equal(
                collect.resolve_env_path(
                    ".env",
                    collect.DEFAULT_JIRA_ENV_CANDIDATES,
                    ["JIRA_URL", "JIRA_USERNAME", "JIRA_TOKEN"],
                ),
                ".env.local",
                "工作区 .env 不可用时回退 .env.local",
            )
            assert_equal(
                lark.resolve_env_path(".env"),
                ".env.local",
                "Lark 默认凭据同样回退 .env.local",
            )
        finally:
            os.chdir(old_cwd)
    assert_equal(
        collect.format_jira_cell("WWLD-12494", "【风控审核】新增-提币审核-提币自动审核新增规则"),
        "WWLD-12494 【风控审核】新增-提币审核-提币自动审核新增规则",
        "逐单表 JIRA单 输出单号+标题",
    )
    presubmit_label, presubmit_review = collect.classify_presubmit_and_review(
        [
            {
                "category": "测试用例",
                "created": "2026-05-11",
                "ctx": "测试用例：https://case.example",
                "body": "测试用例：https://case.example\n用例评审通过",
            }
        ],
        "2026-05-12",
        "2026-05-13",
    )
    assert_equal(presubmit_review, "用例评审通过", "测试开始前用例评审")
    assert_equal(
        presubmit_label,
        "测试用例链接（2026-05-11 评审通过，测试开始 2026-05-12 前已产出）",
        "提测前用例产出按预计测试开始时间判断",
    )
    assert_equal(
        collect.format_actual_test_completion("2026-05-15", "2026-05-15"),
        "如期：状态 2026-05-15 已测试（预计 2026-05-15）",
        "已测试状态流转在预计测试完成时间当天视为如期",
    )
    assert_equal(
        collect.format_actual_test_completion("2026-05-15", "2026-05-18"),
        "超期：状态 2026-05-18 已测试（预计 2026-05-15）",
        "已测试状态流转晚于预计测试完成时间视为超期",
    )
    assert_equal(
        collect.format_actual_test_completion("2026-05-15", ""),
        "未见状态流转已测试（预计 2026-05-15）",
        "未见已测试状态流转需明确输出",
    )
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
    gate_row = next((row for row in gate_rows if row["项目"] == "严格执行质量门禁和缺陷闭环"), None)
    if not gate_row:
        raise AssertionError("标准流程缺少准入/冒烟/准出等关键门禁留痕必须进入门禁汇总扣分")
    if "准入/冒烟/准出" not in gate_row["问题"] or "自测报告" not in gate_row["问题"] or "测试报告" not in gate_row["问题"]:
        raise AssertionError("门禁汇总必须同时列出准入/冒烟/准出、自测报告和测试报告缺失")
    assert_equal(gate_row["建议扣分"], "扣 13 分", "门禁/自测/测试报告缺失按同一 15 分子项合并测算")

    gate_cap_summary = audit.summarize(
        [
            audit.audit_row(
                {
                    "JIRA单": f"WWLD-REPORT-{idx} 标准流程",
                    "流程类型": "标准流程",
                    "Story Points": "5",
                    "提测前完成测试用例产出": "有：https://case.example",
                    "用例/评审记录": "用例评审通过",
                    "测试用例是否编写": "有效",
                    "全局影响面评估分析是否完整": "完整",
                    "自测报告": "缺失" if idx < 2 else "有自测报告",
                    "测试报告": "缺失",
                    "实际测试完成": "如期完成测试",
                    "风险同步/闭环记录": "有风险同步",
                    "Bug记录是否规范": "无关联Bug",
                }
            )
            for idx in range(7)
        ]
    )
    gate_cap_rows = gate_cap_summary["concise_kpi_rows"]
    gate_cap_row = next((row for row in gate_cap_rows if row["项目"] == "严格执行质量门禁和缺陷闭环"), None)
    if not gate_cap_row:
        raise AssertionError("标准流程缺测试报告必须进入门禁汇总扣分")
    if "标准流程缺测试报告 7 个" not in gate_cap_row["问题"] or "标准流程未见自测报告 2 个" not in gate_cap_row["问题"]:
        raise AssertionError("门禁汇总必须列出测试报告和自测报告缺失数量")
    assert_equal(gate_cap_row["建议扣分"], "扣 15 分", "门禁/自测/测试报告扣分按 15 分子项封顶")
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
    required_header = "时间 | JIRA单 | 状态 | 流程类型 | 实际测试完成 | 提测前完成测试用例产出 | 用例/评审记录 | 测试用例是否编写 | 全局影响面评估分析是否完整 | 自测报告 | 测试报告 | 验收/线上问题 | 风险同步/闭环记录 | Bug记录是否规范 | 月度工作量加分在汇总项统计 | 扣分项"
    if required_header not in report:
        raise AssertionError("Markdown report missing required row-level columns")
    if "全部有效统计工作日 25 天" not in report:
        raise AssertionError("Row-level workload column must include concrete monthly workdays")
    if "| 加分 | 工作量加分 | Rain 全部有效统计工作日 25 天，>=25 天 | +1 分 |" not in report:
        raise AssertionError("Workload bonus row must include threshold text and bonus suggestion")
    for phrase in ["当前明确测算得分为", "| 业务交付质量与效能 |", "| 重点工作 |", "| 测试专业能力与规范执行 |", "| 合计 |"]:
        if phrase not in report:
            raise AssertionError(f"Monthly conclusion must include {phrase}")
    module_report = audit.markdown_report(
        [
            {
                "时间": "2026/5/1",
                "JIRA单": "WWLD-1 测试需求",
                "测试人员": "rain107774",
                "月份": "2026-05",
            }
        ],
        [
            audit.audit_row(
                {
                    "时间": "2026/5/1",
                    "JIRA单": "WWLD-1 测试需求",
                    "测试人员": "rain107774",
                    "Bug记录是否规范": "无关联Bug",
                }
            )
        ],
        {
            "manual_confirmation_count": 1,
            "concise_kpi_rows": [
                {"项目": "业务交付质量与效能", "问题": "提测前未见用例产出 10 个，超过 3 个", "建议扣分": "扣 5 分"},
                {"项目": "测试专业能力与规范执行", "问题": "用例沉淀缺失", "建议扣分": "扣 15 分"},
                {"项目": "严格执行质量门禁和缺陷闭环", "问题": "门禁/自测/测试报告证据不足", "建议扣分": "扣 15 分"},
            ],
            "workload_bonus": [{"测试人员": "rain107774", "月份": "2026-05", "当月工时统计/天": 25, "加分项": "加 1 分"}],
        },
    )
    for expected in [
        "当前明确测算得分为 66/100",
        "| 业务交付质量与效能 | 26/30 |",
        "| 重点工作 | 25/25 |",
        "| 测试专业能力与规范执行 | 15/45 |",
        "| 合计 | 66/100 | 明确扣 35 分，加 1 分 |",
    ]:
        if expected not in module_report:
            raise AssertionError(f"Monthly conclusion must include module score row: {expected}")
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
