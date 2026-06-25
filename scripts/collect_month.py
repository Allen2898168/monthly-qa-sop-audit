#!/usr/bin/env python3
"""Live collector for the monthly QA SOP audit.

Turns a tester + month into the evidence TSV that ``audit_monthly_sop.py``
consumes — no browser, no CDP. It logs in to Jira via REST (Basic auth) and
opens Lark docs via a Lark app tenant_access_token, then deterministically
classifies each SOP evidence column. Only genuinely ambiguous fields
(prose understanding sections, board-node content, responsibility attribution)
are left as ``待确认`` for human/model review.

Usage:
    python3 collect_month.py rain107774 2026-05 \
        --out audit_input.tsv --json evidence.json

Then:
    python3 audit_monthly_sop.py audit_input.tsv --format tsv

Credentials are read from .env files; the Lark token is never printed.
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime

# Reuse the existing offline helpers so rules live in one place.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lark_doc_fetch as LARK  # noqa: E402
import audit_monthly_sop as AUDIT  # noqa: E402
from check_bug_record_quality import classify as classify_bug, summarize as summarize_bugs  # noqa: E402

JIRA_FIELDS = {
    "tester_multi": "customfield_11622",
    "tester_single": "customfield_11606",
    "test_start": "customfield_12304",
    "test_end": "customfield_11617",
    "submit_plan": "customfield_11616",
    "release_plan": "customfield_11619",
    "release_done": "customfield_12600",
    "dev": "customfield_11615",
    "module": "customfield_12401",
    "sp1": "customfield_10106",
    "sp2": "customfield_12503",
    "progress": "customfield_12201",
}

FIELD_WHITELIST = ",".join([
    "summary", "status", "assignee", "reporter", "priority", "issuetype",
    "description", "comment", "issuelinks", "labels", "components", "created", "updated",
] + list(JIRA_FIELDS.values()))

DEFAULT_JIRA_ENV_CANDIDATES = [
    ".env.local",
    "~/Downloads/jira/.env",
]

DEFAULT_LARK_ENV_CANDIDATES = [
    ".env.local",
    "~/Downloads/weexpr/eff/.env",
]


# ---------------------------------------------------------------------------
# Jira REST access
# ---------------------------------------------------------------------------
def load_env(path):
    creds = {}
    with open(os.path.expanduser(path)) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip().strip('"').strip("'")
    return creds


def has_required_keys(path, required_keys):
    if not os.path.exists(path):
        return False
    creds = load_env(path)
    for key_group in required_keys:
        if isinstance(key_group, str):
            key_group = [key_group]
        if not any(creds.get(key) for key in key_group):
            return False
    return True


def resolve_env_path(path, candidates, required_keys):
    expanded = os.path.expanduser(path)
    if has_required_keys(expanded, required_keys):
        return expanded
    if path not in (".env", ".env.local"):
        return expanded
    for candidate in candidates:
        expanded_candidate = os.path.expanduser(candidate)
        if has_required_keys(expanded_candidate, required_keys):
            return expanded_candidate
    return expanded


class Jira:
    def __init__(self, env):
        self.url = env["JIRA_URL"].rstrip("/")
        self.auth = base64.b64encode(
            f"{env['JIRA_USERNAME']}:{env['JIRA_TOKEN']}".encode()
        ).decode()

    def get(self, path, params=None):
        qs = ("?" + urllib.parse.urlencode(params)) if params else ""
        req = urllib.request.Request(
            self.url + path + qs, headers={"Authorization": "Basic " + self.auth}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def verify(self):
        me = self.get("/rest/api/2/myself")
        name = me.get("name", "")
        if not name or name == "anonymous":
            raise SystemExit("Jira auth failed: anonymous session")
        return name

    def search(self, jql, fields, expand=None):
        issues, start = [], 0
        while True:
            params = {"jql": jql, "fields": fields, "startAt": start, "maxResults": 50}
            if expand:
                params["expand"] = expand
            d = self.get("/rest/api/2/search", params)
            issues.extend(d["issues"])
            if start + 50 >= d["total"]:
                break
            start += 50
        return issues

    def issue(self, key, fields, expand=None):
        params = {"fields": fields}
        if expand:
            params["expand"] = expand
        return self.get(f"/rest/api/2/issue/{key}", params)


# ---------------------------------------------------------------------------
# Evidence extraction helpers
# ---------------------------------------------------------------------------
def first_day(month):
    y, m = [int(x) for x in month.split("-")]
    return date(y, m, 1)


def next_month(month):
    y, m = [int(x) for x in month.split("-")]
    return f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"


def fld(f, key):
    return f.get(JIRA_FIELDS[key])


def date10(s):
    return (s or "")[:10]


def format_jira_cell(key, summary):
    key = (key or "").strip()
    summary = (summary or "").strip()
    return f"{key} {summary}".strip()


def format_actual_test_completion(planned_end, tested_transition_date):
    planned = date10(planned_end)
    tested = date10(tested_transition_date)
    if not tested:
        return f"未见状态流转已测试（预计 {planned or '-'}）"
    if not planned:
        return f"状态 {tested} 已测试（预计 -）"
    status = "如期" if tested <= planned else "超期"
    return f"{status}：状态 {tested} 已测试（预计 {planned}）"


def user_names(value):
    if isinstance(value, list):
        return ",".join(u.get("name", "") for u in value if isinstance(u, dict))
    if isinstance(value, dict):
        return value.get("name", "")
    return value or ""


def option_value(value):
    if isinstance(value, dict):
        return value.get("value") or value.get("name") or value.get("displayName") or ""
    return value or ""


def status_transitions(issue):
    out = []
    for h in issue.get("changelog", {}).get("histories", []):
        for it in h["items"]:
            if it["field"] == "status":
                out.append((h["created"][:16], h["author"].get("name", ""), it.get("toString", "")))
    return out


def first_transition_to(issue, target):
    for ts, _who, to in status_transitions(issue):
        if to == target:
            return ts[:10]
    return ""


def last_transition_to(issue, target):
    found = ""
    for ts, _who, to in status_transitions(issue):
        if to == target:
            found = ts[:10]
    return found


# Lark URL with its adjacent label context, pulled from a comment/description body.
URL_RE = re.compile(r"https?://[\w.-]*larksuite\.com/\S+")


def clean_url(u):
    return u.rstrip(".,，。)）]】 \n\t")


def categorize_link(ctx):
    c = ctx or ""
    if "测试用例" in c or "用例" in c:
        return "测试用例"
    if "测试报告" in c or "测试总结" in c or "测试结论" in c:
        return "测试报告"
    if "自测报告" in c or "自测文档" in c or "自测结果" in c or "提测报告" in c or "提测文档" in c:
        return "自测报告"
    if "技术" in c:
        return "技术文档"
    return "其他"


def collect_links(issue):
    """Return [{url, category, ctx, author, created}] for all Lark links."""
    f = issue["fields"]
    out = []
    for u in URL_RE.findall(f.get("description") or ""):
        out.append({"url": clean_url(u), "category": categorize_link("description"), "ctx": "description",
                    "author": "", "created": ""})
    for c in f.get("comment", {}).get("comments", []):
        body = c.get("body") or ""
        for u in URL_RE.findall(body):
            line = next((ln.strip() for ln in body.split("\n") if u[:40] in ln), body[:80])
            out.append({"url": clean_url(u), "category": categorize_link(line), "ctx": line[:120],
                        "body": body[:400], "author": c["author"].get("name", ""), "created": c["created"][:10]})
    return out


# ---------------------------------------------------------------------------
# Column classifiers (deterministic; mark 待确认 only when truly unreadable)
# ---------------------------------------------------------------------------
IMPACT_INVOLVED_RE = re.compile(r"全局影响面评估")
TEMPLATE_CASE_RE = re.compile(r"测试用例不是简单罗列操作步骤")


def classify_case_doc(doc):
    """doc = fetched lark result for the 测试用例 link (or None)."""
    if doc is None:
        return "缺用例", "无 Rain 测试用例文档"
    if not doc.get("ok"):
        return "待确认：链接无法访问", doc.get("note", "")
    blocks = doc.get("blocks", {})
    text = doc.get("text", "") or ""
    has_board = blocks.get("has_board")
    has_table = blocks.get("has_table")
    body_wo_title = text.split("\n", 1)[1] if "\n" in text else ""
    concrete = re.sub(r"\s", "", body_wo_title)
    concrete = TEMPLATE_CASE_RE.sub("", concrete)
    if has_board and len(concrete) < 40:
        return "画板形式（board存在，节点不可读）", "待确认：画板节点不可读"
    if has_table and len(concrete) >= 40:
        return "有效", "用例文档含表格/正文内容"
    if len(concrete) >= 60:
        return "有效", "用例文档含正文内容"
    return "待确认：内容无法读取", "用例文档正文过短"


def classify_impact(case_doc):
    if case_doc is None:
        return "缺失：未见全局影响面评估"
    if not case_doc.get("ok"):
        return "待确认：用例文档无法打开"
    text = case_doc.get("text", "") or ""
    if not IMPACT_INVOLVED_RE.search(text):
        if case_doc.get("blocks", {}).get("has_board"):
            return "待确认：画板节点不可读"
        return "缺失：未见全局影响面评估"
    # Section present in readable text. Heuristic completeness: the section must
    # carry concrete impact-point descriptors (mentions/feature text), not just
    # the involved/covered yes-no grid.
    section = text[text.find("全局影响面评估"):]
    section = section[: text.find("测试用例") - text.find("全局影响面评估")] if "测试用例" in section else section
    concrete_hits = len(re.findall(r"@|验证|回归|新增|需|配置|检测|限制|页面|接口|流程", section))
    if concrete_hits >= 4:
        return "完整（脚本判定，建议人工抽查）"
    return "不完整：涉及且需覆盖的影响项缺少具体影响点"


SELFTEST_DOC_RE = re.compile(r"自测范围|自测结果|自测报告|可提测|提测报告")


def classify_self_test(links, docs):
    """有自测报告 if a labeled self-test link OR a fetched doc that is itself a
    structured dev self-test report (reads beat the bare-link heuristic)."""
    for lk in links:
        if lk["category"] == "自测报告":
            return "有自测报告"
    # bare-URL doc that is structurally a self-test report
    for lk in links:
        if lk["category"] in ("其他", "技术文档"):
            d = docs.get(lk["url"])
            if d and d.get("ok") and SELFTEST_DOC_RE.search(d.get("text", "") or ""):
                return "有自测报告"
    return "缺自测报告"


REPORT_FULL_RE = re.compile(r"测试结论|测试评估|测试计划|执行情况|是否通过|准出|测试场景|预期结果")


def classify_test_report(links, docs, issue=None):
    cand = [lk for lk in links if lk["category"] == "测试报告"]
    if not cand:
        if issue:
            best_label = None
            label_rank = {"有测试报告": 3, "有测试结论": 2, "仅测试完成备注": 1}
            for comment in issue.get("fields", {}).get("comment", {}).get("comments", []):
                body = comment.get("body") or ""
                if AUDIT.SCHEDULE_ONLY_COMPLETION_RE.search(body):
                    continue
                label = AUDIT.classify_test_report(body)
                if label in label_rank and (best_label is None or label_rank[label] > label_rank[best_label]):
                    best_label = label
                    if best_label == "有测试报告":
                        break
            if best_label:
                return best_label
        return "缺测试报告/结论"
    for lk in cand:
        d = docs.get(lk["url"])
        if d is None:
            continue
        if not d.get("ok"):
            return "待确认：链接无法打开"
        if REPORT_FULL_RE.search(d.get("text", "") or "") and len((d.get("text") or "")) >= 300:
            return "有测试报告"
    # link labeled 测试报告 but content thin
    return "有测试结论"


PRODUCT_RE = re.compile(r"产品需求理解与确认")
TECH_RE = re.compile(r"技术方案理解与确认")


def section_body(text, head_re, next_heads):
    m = head_re.search(text)
    if not m:
        return None
    start = m.end()
    ends = [text.find(h, start) for h in next_heads if text.find(h, start) > 0]
    end = min(ends) if ends else len(text)
    return text[start:end]


def classify_understanding(case_doc, which):
    if case_doc is None or not case_doc.get("ok"):
        return "待确认(画板/无用例文档)"
    text = case_doc.get("text", "") or ""
    head = PRODUCT_RE if which == "product" else TECH_RE
    body = section_body(text, head, ["二. ", "三. ", "四. ", "五. ", "六. ", "技术方案理解", "全局影响面评估", "术语解释"])
    if body is None:
        if case_doc.get("blocks", {}).get("has_board"):
            return "待确认(画板/无用例文档)"
        return "缺失"
    # strip the boilerplate scaffolding (Jira/PRD/TRD links, owner mentions)
    stripped = re.sub(r"(Jira单|PRD（产品需求文档）|TRD（技术需求文档）|产品|开发|理解分析描述)[:：].*", "", body)
    stripped = re.sub(r"https?://\S+|@\S+|\s", "", stripped)
    return "有，且有实际理解分析内容" if len(stripped) >= 25 else "内容不足"


PRESUBMIT_REVIEW_RE = re.compile(r"评审通过|已评审|用例评审")


def classify_presubmit_and_review(links, test_start, test_in):
    case_links = [lk for lk in links if lk["category"] == "测试用例"]
    review = "未见用例/评审记录"
    if case_links:
        # check the whole comment that carried the case link, not just its line,
        # since "评审通过" is often on an adjacent line.
        if any(PRESUBMIT_REVIEW_RE.search(lk.get("body") or lk["ctx"]) for lk in case_links):
            review = "用例评审通过"
        else:
            review = "未见用例评审结论"
    # 提测前完成测试用例产出: earliest case link created date vs planned
    # test start. Fall back to actual test-entry transition if the plan is absent.
    # Emit strings the engine's has_traceable_case_link() reads correctly:
    # produced cells must contain "测试用例链接" and no negative token; not-produced
    # cells must contain "未见".
    gate = test_start or test_in
    pre = "提测前未见测试用例链接"
    dated = [lk["created"] for lk in case_links if lk["created"]]
    if dated and gate:
        earliest = min(dated)
        if earliest <= gate:
            tag = "评审通过" if review == "用例评审通过" else "已产出"
            pre = f"测试用例链接（{earliest} {tag}，测试开始 {gate} 前已产出）"
        else:
            pre = f"提测前未见测试用例链接（用例 {earliest} 晚于测试开始 {gate}）"
    elif case_links and not dated:
        pre = "测试用例链接（提测前是否产出待确认）"
    return pre, review


PROD_BUG_RE = re.compile(r"Prod\s*Bug|线上|漏测", re.I)
RISK_RE = re.compile(r"插入|顺延|延期|阻塞|挂起|同步|风险|休假|公休|重新提测|退回")


def classify_acceptance(issue):
    f = issue["fields"]
    prod = []
    for l in f.get("issuelinks", []):
        li = l.get("inwardIssue") or l.get("outwardIssue")
        if not li:
            continue
        summ = li.get("fields", {}).get("summary", "")
        if PROD_BUG_RE.search(summ):
            pr = (li.get("fields", {}).get("priority") or {}).get("name", "?")
            prod.append(f"{li['key']}({pr})")
    if prod:
        return "线上问题：" + "、".join(prod) + "（责任归属待确认）"
    return "无"


def classify_risk(issue):
    f = issue["fields"]
    hits = []
    for c in f.get("comment", {}).get("comments", []):
        body = c.get("body") or ""
        if RISK_RE.search(body):
            hits.append(body.replace("\n", " ")[:40])
    return ("有（" + "；".join(hits[:2]) + "）") if hits else "无"


def linked_test_bug_keys(issue):
    keys = []
    for l in issue["fields"].get("issuelinks", []):
        li = l.get("inwardIssue") or l.get("outwardIssue")
        if not li:
            continue
        summ = li.get("fields", {}).get("summary", "")
        itype = li.get("fields", {}).get("issuetype", {}).get("name", "")
        if summ.startswith("【Test】") or (itype in ("故障", "BUG", "Bug") and not PROD_BUG_RE.search(summ)):
            keys.append(li["key"])
    return keys


# ---------------------------------------------------------------------------
# Main collection
# ---------------------------------------------------------------------------
def collect(tester, month, jira, fetch_lark=True, verbose=True):
    start = first_day(month).isoformat()
    end = first_day(next_month(month)).isoformat()
    jql = (f'project = WWLD AND cf[11622] = "{tester}" '
           f'AND cf[12304] >= "{start}" AND cf[12304] < "{end}" '
           f'ORDER BY cf[12304] ASC, key ASC')
    if verbose:
        print(f"[jql] {jql}", file=sys.stderr)
    demands = jira.search(jql, FIELD_WHITELIST, expand="changelog")
    if verbose:
        print(f"[demands] {len(demands)}", file=sys.stderr)

    rows, evidence = [], []
    for issue in demands:
        key = issue["key"]
        f = issue["fields"]
        links = collect_links(issue)

        # fetch only the decision-relevant docs (用例/测试报告/自测报告/技术/其他)
        docs = {}
        if fetch_lark:
            for lk in links:
                if lk["url"] in docs:
                    continue
                try:
                    docs[lk["url"]] = LARK.fetch(lk["url"])
                except Exception as e:  # noqa: BLE001
                    docs[lk["url"]] = {"ok": False, "note": f"fetch error {e}", "url": lk["url"]}
                time.sleep(0.05)

        test_start = date10(fld(f, "test_start"))
        submit_plan = date10(fld(f, "submit_plan"))
        test_in = first_transition_to(issue, "测试中") or first_transition_to(issue, "已测试")
        # Use the LAST 已测试 transition so reopened/retested demands report the
        # final completion date, not the first round.
        test_done = last_transition_to(issue, "已测试")

        case_links = [lk for lk in links if lk["category"] == "测试用例"]
        case_doc = docs.get(case_links[0]["url"]) if (case_links and fetch_lark) else (None if not case_links else {"ok": False, "note": "not fetched"})

        case_written, case_note = classify_case_doc(case_doc)
        # If no case doc but the test report carries execution scenarios, that is a
        # valid test-execution record per the 用例未编写 boundary.
        report_label = classify_test_report(links, docs, issue)
        if case_doc is None:
            tr_links = [lk for lk in links if lk["category"] == "测试报告"]
            for lk in tr_links:
                d = docs.get(lk["url"])
                if d and d.get("ok") and re.search(r"测试场景|执行情况|预期结果", d.get("text", "") or ""):
                    case_written = "有效（测试报告执行记录）"
                    break

        pre_submit, review = classify_presubmit_and_review(links, test_start, test_in)
        impact = classify_impact(case_doc)
        prod_understanding = classify_understanding(case_doc, "product")
        tech_understanding = classify_understanding(case_doc, "tech")
        self_test = classify_self_test(links, docs)

        # bug quality
        bug_keys = linked_test_bug_keys(issue)
        bug_records = []
        for bk in bug_keys:
            try:
                bd = jira.issue(bk, "summary,status,priority,issuetype,description,assignee")
                bug_records.append(bd)
            except Exception:  # noqa: BLE001
                pass
        bug_results = [classify_bug(b) for b in bug_records]
        bug_summary = summarize_bugs(bug_results) if bug_records else "无关联Bug"
        nonstd = [r["key"] for r in bug_results if not r["is_standard"]]
        if nonstd:
            bug_summary += "；不规范：" + "、".join(nonstd)

        sp = option_value(fld(f, "sp1") or fld(f, "sp2"))
        module = fld(f, "module")
        module = option_value(module)
        # Reuse the engine's own rule to infer 流程类型 from the title (which the
        # engine can't read from the JIRA单 cell, since that holds the key).
        flow_type = AUDIT.infer_process_type({
            "标题": f["summary"], "业务模块": module or "", "测试人员": tester,
            "Story Points": str(sp) if sp is not None else "",
            "预计测试开始时间": test_start,
            "预计测试完成时间": date10(fld(f, "test_end")),
        })
        row = {
            "时间": test_start,
            "JIRA单": format_jira_cell(key, f["summary"]),
            "标题": f["summary"],
            "状态": f["status"]["name"],
            "业务模块": module or "",
            "Story Points": sp if sp is not None else "",
            "测试人员": tester,
            "流程类型": flow_type,
            "预计测试开始时间": test_start,
            "预计测试完成时间": date10(fld(f, "test_end")),
            "测试周期": "",
            "实际测试完成": format_actual_test_completion(fld(f, "test_end"), test_done),
            "提测前完成测试用例产出": pre_submit,
            "用例/评审记录": review,
            "测试用例是否编写": case_written,
            "全局影响面评估分析是否完整": impact,
            "自测报告": self_test,
            "测试报告": report_label,
            "验收/线上问题": classify_acceptance(issue),
            "风险同步/闭环记录": classify_risk(issue),
            "Bug记录是否规范": bug_summary,
            "扣分项": "",
        }
        rows.append(row)
        evidence.append({
            "key": key, "summary": f["summary"], "links": links,
            "case_note": case_note, "product_understanding": prod_understanding,
            "tech_understanding": tech_understanding, "bug_keys": bug_keys,
            "submit_plan": submit_plan, "test_in": test_in, "test_done": test_done,
        })
        if verbose:
            print(f"  {key}: 用例={case_written} 报告={report_label} 自测={self_test} bug={bug_summary[:30]}", file=sys.stderr)
    return rows, evidence


TSV_COLUMNS = [
    "时间", "JIRA单", "标题", "状态", "业务模块", "Story Points", "测试人员", "流程类型",
    "预计测试开始时间", "预计测试完成时间", "测试周期", "实际测试完成",
    "提测前完成测试用例产出", "用例/评审记录", "测试用例是否编写",
    "全局影响面评估分析是否完整", "自测报告", "测试报告", "验收/线上问题",
    "风险同步/闭环记录", "Bug记录是否规范", "扣分项",
]


def main():
    ap = argparse.ArgumentParser(description="Live Jira+Lark collector for monthly QA SOP audit.")
    ap.add_argument("tester", help="Jira tester username, e.g. rain107774")
    ap.add_argument("month", help="Target month YYYY-MM, e.g. 2026-05")
    ap.add_argument("--jira-env", default=".env")
    ap.add_argument("--lark-env", default=".env")
    ap.add_argument("--out", default="audit_input.tsv", help="Evidence TSV for audit_monthly_sop.py")
    ap.add_argument("--json", default=None, help="Optional raw-evidence JSON sidecar")
    ap.add_argument("--no-lark", action="store_true", help="Skip Lark doc fetch (Jira-only)")
    args = ap.parse_args()

    jira_env_path = resolve_env_path(args.jira_env, DEFAULT_JIRA_ENV_CANDIDATES, ["JIRA_URL", "JIRA_USERNAME", "JIRA_TOKEN"])
    lark_env_path = resolve_env_path(args.lark_env, DEFAULT_LARK_ENV_CANDIDATES, [["APP_ID", "app_id"], ["APP_SECRET", "app_secret"]])

    jira = Jira(load_env(jira_env_path))
    who = jira.verify()
    print(f"[jira] authenticated as {who}", file=sys.stderr)
    if not args.no_lark:
        os.environ.setdefault("_", "")  # no-op; LARK reads its own .env
        LARK.ENV = lark_env_path
        LARK._tok = {"v": None, "exp": 0}

    rows, evidence = collect(args.tester, args.month, jira, fetch_lark=not args.no_lark)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[out] wrote {len(rows)} rows -> {args.out}", file=sys.stderr)
    if args.json:
        json.dump(evidence, open(args.json, "w"), ensure_ascii=False, indent=1)
        print(f"[json] evidence -> {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
