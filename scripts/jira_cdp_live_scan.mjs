#!/usr/bin/env node
/**
 * Live Jira evidence collector using an authenticated Chrome/CDP session.
 *
 * This script does not own KPI scoring rules. It collects Jira evidence through
 * REST fetch calls executed inside the user's logged-in Chrome session, writes
 * standard audit rows, and can pipe them into audit_monthly_sop.py.
 */
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const JIRA_BASE = "https://jira.weex.tech";
const FIELD_TESTER = "customfield_11622";
const FIELD_TEST_START = "customfield_12304";
const FIELD_TEST_END = "customfield_11617";

const REPORT_COLUMNS = [
  "时间",
  "JIRA单",
  "状态",
  "业务模块",
  "Story Points",
  "测试人员",
  "流程类型",
  "测试周期",
  "预计测试开始",
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
  "月度工作量加分在汇总项统计",
  "扣分项",
];

const STEP_PATTERNS = [/复现步骤/i, /操作步骤/i, /步骤/i, /\bsteps?\b/i, /点击/, /进入/, /选择/, /输入/, /配置/, /提交/, /处理/];
const ACTUAL_PATTERNS = [/实际结果/i, /实际/, /现象/, /问题/, /报错/, /失败/, /无法/, /没有/, /未/, /错误/];
const EXPECTED_PATTERNS = [/预期结果/i, /预期/, /应该/, /应为/, /需/, /需要/, /期望/];
const URL_RE = /https?:\/\/[^\s)\]}>"]+/gi;
const CASE_KEYWORDS = /(测试用例|用例|测试点|case|测试脑图)/i;
const SELF_TEST_KEYWORDS = /(自测报告|自测文档|自测结果|提测报告|提测文档)/i;
const TEST_REPORT_KEYWORDS = /(测试报告|测试完成报告|测试总结)/i;

function parseArgs(argv) {
  const args = {
    jiraBase: JIRA_BASE,
    cdp: "http://localhost:9222",
    format: "tsv",
    audit: false,
    json: false,
    readLarkCases: true,
    caseTimeoutMs: 15000,
    maxResults: 50,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => argv[++i];
    if (arg === "--tester") args.tester = next();
    else if (arg === "--display-name") args.displayName = next();
    else if (arg === "--month") args.month = next();
    else if (arg === "--start") args.start = next();
    else if (arg === "--end") args.end = next();
    else if (arg === "--jira-base") args.jiraBase = next();
    else if (arg === "--cdp") args.cdp = next();
    else if (arg === "--case-timeout-ms") args.caseTimeoutMs = Number(next());
    else if (arg === "--max-results") args.maxResults = Number(next());
    else if (arg === "--json") args.json = true;
    else if (arg === "--audit") args.audit = true;
    else if (arg === "--no-lark-cases") args.readLarkCases = false;
    else if (arg === "--selftest") args.selftest = true;
    else if (arg === "-h" || arg === "--help") args.help = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (args.month && (!args.start || !args.end)) {
    const [year, month] = args.month.split("-").map(Number);
    if (!year || !month) throw new Error("--month must be YYYY-MM");
    args.start = `${year}-${String(month).padStart(2, "0")}-01`;
    const nextMonth = month === 12 ? 1 : month + 1;
    const nextYear = month === 12 ? year + 1 : year;
    args.end = `${nextYear}-${String(nextMonth).padStart(2, "0")}-01`;
  }
  return args;
}

function usage() {
  return `Usage:
  node scripts/jira_cdp_live_scan.mjs --tester rain107774 --display-name Rain --month 2026-05 --audit

Options:
  --tester <jiraUser>        Required. Jira tester value, e.g. rain107774.
  --display-name <name>      Optional fallback tester display name, e.g. Rain.
  --month <YYYY-MM>          Month scope. Alternative: --start/--end.
  --start <YYYY-MM-DD>       Inclusive test-start lower bound.
  --end <YYYY-MM-DD>         Exclusive test-start upper bound.
  --cdp <url>                Chrome CDP endpoint. Default: http://localhost:9222.
  --audit                    Pipe collected TSV into audit_monthly_sop.py and output the four-section report.
  --json                     Output collected evidence JSON.
  --no-lark-cases            Do not open Lark test-case links; mark case details as pending.
  --selftest                 Run deterministic helper tests without Jira/Chrome.
`;
}

function buildJqlCandidates({ tester, displayName, start, end }) {
  const date = `cf[12304] >= "${start}" AND cf[12304] < "${end}"`;
  const candidates = [
    `project = WWLD AND cf[11622] in ("${tester}") AND ${date} ORDER BY cf[12304] ASC, key ASC`,
    `project = WWLD AND cf[11622] = "${tester}" AND ${date} ORDER BY cf[12304] ASC, key ASC`,
  ];
  if (displayName && displayName !== tester) {
    candidates.push(`project = WWLD AND cf[11622] in ("${displayName}") AND ${date} ORDER BY cf[12304] ASC, key ASC`);
    candidates.push(`project = WWLD AND cf[11622] = "${displayName}" AND ${date} ORDER BY cf[12304] ASC, key ASC`);
  }
  candidates.push(
    `project = WWLD AND "测试人员（多选）" in ("${tester}") AND "预计测试开始时间" >= "${start}" AND "预计测试开始时间" < "${end}" ORDER BY "预计测试开始时间" ASC, key ASC`,
  );
  return candidates;
}

function bugSampleSize(total) {
  if (total <= 0) return 0;
  if (total <= 3) return total;
  return Math.max(3, Math.ceil(total * 0.3));
}

function priorityRank(name = "") {
  const t = String(name).toUpperCase();
  if (/\bP0\b|BLOCKER|最高|紧急/.test(t)) return 0;
  if (/\bP1\b|CRITICAL|严重|高/.test(t)) return 1;
  if (/\bP2\b|MAJOR|中/.test(t)) return 2;
  if (/\bP3\b|MINOR|低/.test(t)) return 3;
  return 9;
}

function selectBugSample(bugs) {
  const size = bugSampleSize(bugs.length);
  return [...bugs]
    .sort((a, b) => {
      const aProd = /prod bug|线上|漏测/i.test(`${a.key} ${a.summary || ""}`) ? 0 : 1;
      const bProd = /prod bug|线上|漏测/i.test(`${b.key} ${b.summary || ""}`) ? 0 : 1;
      if (aProd !== bProd) return aProd - bProd;
      const p = priorityRank(a.priority) - priorityRank(b.priority);
      if (p !== 0) return p;
      return String(b.created || "").localeCompare(String(a.created || ""));
    })
    .slice(0, size);
}

function stripAdf(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(stripAdf).join("\n");
  if (typeof value === "object") {
    const parts = [];
    if (value.text) parts.push(value.text);
    if (value.attrs?.href) parts.push(value.attrs.href);
    if (value.attrs?.url) parts.push(value.attrs.url);
    if (value.content) parts.push(stripAdf(value.content));
    return parts.join("\n");
  }
  return String(value);
}

function hasAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function classifyBug(issue) {
  const fields = issue.fields || issue;
  const description = stripAdf(fields.description || issue.description || "");
  const missing = [];
  if (!description.trim()) missing.push("描述为空");
  else if (/^\s*https?:\/\/\S+\s*$/i.test(description)) missing.push("仅贴外部链接");
  if (!hasAny(description, STEP_PATTERNS)) missing.push("缺复现步骤");
  if (!hasAny(description, ACTUAL_PATTERNS)) missing.push("缺实际结果");
  if (!hasAny(description, EXPECTED_PATTERNS)) missing.push("缺预期结果");
  if (!fieldName(fields.priority)) missing.push("缺优先级");
  if (!fieldName(fields.status)) missing.push("缺状态");
  if (!userName(fields.assignee)) missing.push("缺经办人/修复人");
  return {
    key: issue.key,
    summary: fields.summary || issue.summary || "",
    priority: fieldName(fields.priority),
    status: fieldName(fields.status),
    assignee: userName(fields.assignee),
    is_standard: missing.length === 0,
    missing_items: missing,
  };
}

function summarizeBugQuality(total, checkedResults) {
  if (!total) return "无关联Bug";
  if (!checkedResults.length) return `关联 Bug ${total} 个；待确认：Bug详情未打开`;
  const standard = checkedResults.filter((r) => r.is_standard).length;
  const notStandard = checkedResults.length - standard;
  if (!notStandard) return `关联 Bug ${total} 个；已抽查 ${checkedResults.length} 个；规范 ${standard} 个，不规范 0 个`;
  const counter = new Map();
  for (const result of checkedResults) {
    if (result.is_standard) continue;
    for (const item of result.missing_items) counter.set(item, (counter.get(item) || 0) + 1);
  }
  const mainIssues = [...counter.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k).join("、");
  return `关联 Bug ${total} 个；已抽查 ${checkedResults.length} 个；规范 ${standard} 个，不规范 ${notStandard} 个；主要问题：${mainIssues}`;
}

function extractUrls(text) {
  return [...String(text || "").matchAll(URL_RE)].map((m) => m[0].replace(/[，。；,.;]+$/, ""));
}

function hasUrl(text) {
  URL_RE.lastIndex = 0;
  return URL_RE.test(String(text || ""));
}

function findKeywordLinks(comments, keywordRe) {
  const found = [];
  for (const comment of comments) {
    const body = stripAdf(comment.body || "");
    if (!keywordRe.test(body)) continue;
    const urls = extractUrls(body);
    for (const url of urls) {
      const index = body.indexOf(url);
      const before = body.slice(Math.max(0, index - 80), index);
      const after = body.slice(index, Math.min(body.length, index + url.length + 80));
      if (keywordRe.test(before) || keywordRe.test(after) || keywordRe.test(body)) {
        found.push({ url, created: dateOnly(comment.created), body });
      }
    }
  }
  return found;
}

function dateOnly(value) {
  return String(value || "").slice(0, 10);
}

function fieldName(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  return value.name || value.value || value.displayName || "";
}

function userName(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  return value.name || value.displayName || value.emailAddress || "";
}

function fieldArrayNames(value) {
  if (!value) return "";
  const list = Array.isArray(value) ? value : [value];
  return list.map((item) => userName(item) || fieldName(item) || String(item)).filter(Boolean).join(",");
}

function classifySelfTest(combinedText) {
  return SELF_TEST_KEYWORDS.test(combinedText) && hasUrl(combinedText) ? "有自测报告" : "缺自测报告";
}

function classifyTestReport(combinedText) {
  if (TEST_REPORT_KEYWORDS.test(combinedText) && hasUrl(combinedText)) return "有测试报告";
  if (/测试结论|测试结果|验证结果/.test(combinedText) && /通过|完成|风险|遗留|阻塞/.test(combinedText)) return "有测试结论";
  if (/测试完成|验证通过|已测完|待发布|已发布|已上线/.test(combinedText)) return "仅测试完成备注";
  return "缺测试报告/结论";
}

function classifyReview(combinedText, hasCaseLink) {
  if (/用例评审不通过|评审不通过|打回/.test(combinedText)) return "用例评审不通过";
  if (/用例评审通过|评审通过|评审已通过/.test(combinedText)) return "用例评审通过";
  if (/用例.{0,20}评审|评审.{0,20}用例/.test(combinedText) || hasCaseLink) return "未见用例评审结论";
  return "缺失评审";
}

function actualCompletion(comments) {
  const hits = comments
    .map((comment) => ({ date: dateOnly(comment.created), body: stripAdf(comment.body || "") }))
    .filter((comment) => /测试完成|测试通过|验证通过|已测完|已测试/.test(comment.body));
  if (!hits.length) return "未见测试完成备注";
  hits.sort((a, b) => a.date.localeCompare(b.date));
  return `${hits[0].date} 测试完成`;
}

function classifyAcceptance(combinedText) {
  if (/Prod Bug|线上漏测|线上问题|验收问题/.test(combinedText)) return "待确认：存在验收/线上问题";
  if (/验收通过|验收完成|产品验收通过|验证完成/.test(combinedText)) return "验收通过";
  return "未见验收通过备注";
}

function classifyRisk(combinedText) {
  if (/风险|阻塞|顺延|延期|遗留|观察|同步|闭环|插入|排期调整|环境问题/.test(combinedText)) return "有风险同步/闭环记录";
  return "无";
}

function casePreSubmitStatus(caseLinks, startDate) {
  if (!caseLinks.length) return "否，未见提测前用例留痕";
  const dated = caseLinks.filter((link) => link.created).sort((a, b) => a.created.localeCompare(b.created));
  const first = dated[0] || caseLinks[0];
  if (first.created && startDate && first.created <= startDate) return `是，${first.created} 已产出 ${first.url}`;
  if (first.created) return `否，${first.created} 才有用例链接 ${first.url}`;
  return `是，有用例链接 ${first.url}`;
}

async function importPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    try {
      const require = createRequire(import.meta.url);
      return require("playwright");
    } catch {
      throw new Error("Cannot import playwright. Run with NODE_PATH pointing to bundled node_modules or install playwright.");
    }
  }
}

async function jiraFetch(page, path) {
  const result = await page.evaluate(async (requestPath) => {
    const res = await fetch(requestPath, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    const text = await res.text();
    return { status: res.status, ok: res.ok, text };
  }, path);
  let json = null;
  try {
    json = result.text ? JSON.parse(result.text) : null;
  } catch {
    // Keep text for error messages.
  }
  if (!result.ok) {
    const message = json ? JSON.stringify(json) : result.text.slice(0, 500);
    throw new Error(`Jira API ${path} failed: HTTP ${result.status} ${message}`);
  }
  return json;
}

async function jiraSearch(page, jql, fields, startAt = 0, maxResults = 50) {
  const params = new URLSearchParams({
    jql,
    startAt: String(startAt),
    maxResults: String(maxResults),
    fields: fields.join(","),
  });
  return jiraFetch(page, `/rest/api/2/search?${params.toString()}`);
}

async function chooseWorkingJql(page, args) {
  const fields = ["key", "summary", "status", FIELD_TESTER, FIELD_TEST_START, FIELD_TEST_END];
  const errors = [];
  for (const jql of buildJqlCandidates(args)) {
    try {
      const probe = await jiraSearch(page, jql, fields, 0, 1);
      if ((probe.total || 0) > 0) return { jql, total: probe.total };
      errors.push({ jql, total: 0 });
    } catch (error) {
      errors.push({ jql, error: error.message });
    }
  }
  throw new Error(`No Jira JQL candidate matched target tester/month. Probe results: ${JSON.stringify(errors, null, 2)}`);
}

async function fetchAllSearch(page, jql, fields, maxResults) {
  const issues = [];
  let startAt = 0;
  while (true) {
    const data = await jiraSearch(page, jql, fields, startAt, maxResults);
    issues.push(...(data.issues || []));
    startAt += data.maxResults || maxResults;
    if (startAt >= (data.total || 0)) break;
  }
  return issues;
}

function issueLinkBugKeys(issue) {
  const bugs = new Map();
  for (const link of issue.fields?.issuelinks || []) {
    for (const side of ["inwardIssue", "outwardIssue"]) {
      const linked = link[side];
      if (!linked) continue;
      const type = linked.fields?.issuetype?.name || "";
      if (!/bug/i.test(type)) continue;
      bugs.set(linked.key, {
        key: linked.key,
        summary: linked.fields?.summary || "",
        priority: fieldName(linked.fields?.priority),
        status: fieldName(linked.fields?.status),
      });
    }
  }
  return bugs;
}

async function fetchLinkedBugs(page, demandIssue) {
  const bugs = issueLinkBugKeys(demandIssue);
  const jql = `issuetype = BUG AND issue in linkedIssues(${demandIssue.key})`;
  try {
    const linked = await fetchAllSearch(page, jql, ["key", "summary", "description", "status", "priority", "assignee", "reporter", "created"], 50);
    for (const issue of linked) {
      bugs.set(issue.key, {
        key: issue.key,
        summary: issue.fields?.summary || "",
        description: issue.fields?.description || "",
        priority: fieldName(issue.fields?.priority),
        status: fieldName(issue.fields?.status),
        assignee: userName(issue.fields?.assignee),
        reporter: userName(issue.fields?.reporter),
        created: issue.fields?.created,
        fields: issue.fields,
      });
    }
  } catch {
    // Some Jira instances disable linkedIssues() for the current permission.
    // Keep issue-link Bugs collected from the demand payload.
  }
  return [...bugs.values()];
}

async function fetchIssueByKey(page, key) {
  const params = new URLSearchParams({
    fields: ["key", "summary", "description", "status", "priority", "assignee", "reporter", "created"].join(","),
  });
  return jiraFetch(page, `/rest/api/2/issue/${encodeURIComponent(key)}?${params.toString()}`);
}

async function inspectCaseDoc(context, link, timeoutMs) {
  const p = await context.newPage();
  try {
    await p.goto(link.url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    await p.waitForTimeout(Math.min(3000, Math.floor(timeoutMs / 3)));
    const text = await p.evaluate(() => document.body?.innerText || "");
    const hasCases = /六[.、\s]*测试用例|测试用例|用例ID|前置条件|预期结果|测试点|TC[-_ ]?\d+/i.test(text);
    const hasImpact = /全局影响面评估|影响面评估/.test(text);
    const impactComplete = hasImpact && /具体影响点|验证要求|是否需要用例覆盖|本次需求是否涉及/.test(text);
    return {
      caseContent: hasCases ? "有效" : "待确认：内容无法读取",
      impact: impactComplete ? "完整：涉及且需覆盖的影响项均有具体影响点" : hasImpact ? "全局影响面评估不完整" : "缺影响面评估",
    };
  } catch {
    return { caseContent: "待确认：链接无法打开", impact: "待确认：链接无法打开" };
  } finally {
    await p.close().catch(() => {});
  }
}

async function issueToAuditRow(context, page, issue, args) {
  const fields = issue.fields || {};
  const comments = fields.comment?.comments || [];
  const commentText = comments.map((comment) => stripAdf(comment.body || "")).join("\n");
  const description = stripAdf(fields.description || "");
  const combinedText = `${description}\n${commentText}`;
  const startDate = dateOnly(fields[FIELD_TEST_START]);
  const endDate = dateOnly(fields[FIELD_TEST_END]);
  const caseLinks = findKeywordLinks(comments, CASE_KEYWORDS);
  let caseContent = caseLinks.length ? "待确认：需打开用例文档" : "缺失用例";
  let impact = caseLinks.length ? "待确认：需打开用例文档" : "缺影响面评估";
  if (args.readLarkCases && caseLinks.length) {
    const inspected = await inspectCaseDoc(context, caseLinks[0], args.caseTimeoutMs);
    caseContent = inspected.caseContent;
    impact = inspected.impact;
  }

  const bugs = await fetchLinkedBugs(page, issue);
  const sample = selectBugSample(bugs);
  const checked = [];
  for (const bug of sample) {
    const full = bug.fields?.description !== undefined ? bug : await fetchIssueByKey(page, bug.key);
    checked.push(classifyBug(full));
  }

  return {
    "时间": startDate,
    "JIRA单": `${issue.key}${fields.summary ? ` ${fields.summary}` : ""}`,
    "状态": fieldName(fields.status),
    "业务模块": fieldName(fields.components?.[0]) || "",
    "Story Points": "",
    "测试人员": fieldArrayNames(fields[FIELD_TESTER]) || args.tester,
    "流程类型": "",
    "测试周期": "",
    "预计测试开始": startDate,
    "预计测试完成": endDate,
    "实际测试完成": actualCompletion(comments),
    "提测前完成测试用例产出": casePreSubmitStatus(caseLinks, startDate),
    "用例/评审记录": classifyReview(combinedText, caseLinks.length > 0),
    "测试用例是否编写": caseContent,
    "全局影响面评估分析是否完整": impact,
    "自测报告": classifySelfTest(combinedText),
    "测试报告": classifyTestReport(combinedText),
    "验收/线上问题": classifyAcceptance(combinedText),
    "风险同步/闭环记录": classifyRisk(combinedText),
    "Bug记录是否规范": summarizeBugQuality(bugs.length, checked),
    "月度工作量加分在汇总项统计": "",
    "扣分项": "",
  };
}

function toTsv(rows) {
  const escape = (value) => String(value ?? "").replace(/\r?\n/g, " ").replace(/\t/g, " ");
  return [REPORT_COLUMNS.join("\t"), ...rows.map((row) => REPORT_COLUMNS.map((column) => escape(row[column])).join("\t"))].join("\n") + "\n";
}

async function collect(args) {
  const { chromium } = await importPlaywright();
  const browser = await chromium.connectOverCDP(args.cdp);
  const context = browser.contexts()[0] || await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto(args.jiraBase, { waitUntil: "domcontentloaded", timeout: 20000 });
    const myself = await jiraFetch(page, "/rest/api/2/myself");
    if (!myself || !myself.name) throw new Error("Jira auth verification failed: /myself did not return a user.");
    const { jql, total } = await chooseWorkingJql(page, args);
    const fields = [
      "summary",
      "status",
      "assignee",
      "reporter",
      "priority",
      "issuetype",
      "description",
      "comment",
      "issuelinks",
      "labels",
      "components",
      "created",
      "updated",
      FIELD_TESTER,
      FIELD_TEST_START,
      FIELD_TEST_END,
    ];
    const issues = await fetchAllSearch(page, jql, fields, args.maxResults);
    const rows = [];
    for (const issue of issues) rows.push(await issueToAuditRow(context, page, issue, args));
    return { authUser: myself.name, jql, total, rows };
  } finally {
    await page.close().catch(() => {});
    // Do not close the connected browser; it is the user's Chrome session.
  }
}

function runSelftest() {
  const jql = buildJqlCandidates({ tester: "rain107774", displayName: "Rain", start: "2026-05-01", end: "2026-06-01" });
  if (!jql[0].includes('cf[11622] in ("rain107774")')) throw new Error("default JQL must use cf[11622] in tester");
  if (!jql[0].includes('cf[12304] >= "2026-05-01"')) throw new Error("default JQL must use cf[12304] start");
  const counts = [[0, 0], [1, 1], [3, 3], [4, 3], [10, 3], [11, 4], [20, 6]];
  for (const [input, expected] of counts) {
    const actual = bugSampleSize(input);
    if (actual !== expected) throw new Error(`bugSampleSize(${input}) expected ${expected}, got ${actual}`);
  }
  const bugs = [
    { key: "B-1", summary: "normal", priority: "P3", created: "2026-05-01" },
    { key: "B-2", summary: "Prod Bug one", priority: "P2", created: "2026-05-02" },
    { key: "B-3", summary: "normal", priority: "P0", created: "2026-05-03" },
    { key: "B-4", summary: "normal", priority: "P1", created: "2026-05-04" },
  ];
  const sample = selectBugSample(bugs);
  if (sample.length !== 3 || sample[0].key !== "B-2") throw new Error("Bug sampling priority should prefer Prod Bug first");
  const bad = classifyBug({ key: "BUG-1", fields: { summary: "bad", description: "", priority: { name: "P2" }, status: { name: "Open" }, assignee: { name: "dev" } } });
  if (bad.is_standard || !bad.missing_items.includes("描述为空")) throw new Error("empty Bug description must be non-standard");
  console.log("selftest passed");
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    console.log(usage());
    return;
  }
  if (args.selftest) {
    runSelftest();
    return;
  }
  if (!args.tester || !args.start || !args.end) throw new Error("--tester and --month or --start/--end are required.");
  const result = await collect(args);
  if (args.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }
  const tsv = toTsv(result.rows);
  if (!args.audit) {
    process.stdout.write(tsv);
    return;
  }
  const dir = mkdtempSync(join(tmpdir(), "qa-sop-live-"));
  const input = join(dir, "audit_input.tsv");
  writeFileSync(input, tsv, "utf8");
  const scriptDir = dirname(fileURLToPath(import.meta.url));
  const auditor = join(scriptDir, "audit_monthly_sop.py");
  const proc = spawnSync("python3", [auditor, input, "--format", "tsv"], { encoding: "utf8" });
  if (proc.error) throw proc.error;
  if (proc.status !== 0) throw new Error(proc.stderr || `audit_monthly_sop.py exited ${proc.status}`);
  process.stdout.write(proc.stdout);
}

main()
  .then(() => {
    process.exit(0);
  })
  .catch((error) => {
  console.error(error.message || error);
  process.exit(1);
  });
