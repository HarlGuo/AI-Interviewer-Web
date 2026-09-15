#!/usr/bin/env python3
"""把 Supabase 导出的四份周报 CSV 汇总为一份可复盘的 Markdown。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"缺少文件：{path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0


def percent(numerator: float, denominator: float) -> str:
    return "—" if denominator == 0 else f"{numerator / denominator:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI 面试官内测周报")
    parser.add_argument("folder", type=Path, help="存放四份 CSV 的周目录")
    args = parser.parse_args()
    folder = args.folder
    funnel = rows(folder / "funnel_weekly.csv")
    engagement = rows(folder / "engagement_weekly.csv")
    tokens = rows(folder / "token_weekly.csv")
    errors = rows(folder / "errors_weekly.csv")

    registrations = sum(number(r.get("registered_users")) for r in funnel)
    started = sum(number(r.get("started_users")) for r in funnel)
    completed = sum(number(r.get("completed_users")) for r in funnel)
    completed_ids = {r.get("interview_id") for r in tokens if r.get("interview_status") == "completed" and r.get("interview_id")}
    completed_tokens = sum(number(r.get("total_tokens")) for r in tokens if r.get("interview_id") in completed_ids)
    all_tokens = sum(number(r.get("total_tokens")) for r in tokens)
    wasted_requests = sum(number(r.get("wasted_request_count")) for r in tokens)
    all_requests = sum(number(r.get("request_count")) for r in tokens)

    metrics = {r.get("metric", ""): r for r in engagement if r.get("section") != "daily"}
    def metric(name: str) -> str:
        row = metrics.get(name, {})
        if row.get("rate") not in (None, ""):
            return f"{number(row.get('rate')):.1%}（{int(number(row.get('value')))}/{int(number(row.get('denominator'))) }）"
        return row.get("value", "—") or "—"

    lines = [
        "# AI 面试官内测数据周报",
        "",
        "> 本报告由真实 CSV 自动汇总；空样本显示为“—”，不会补造数据。",
        "",
        "## 核心漏斗",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 注册用户 | {int(registrations)} |",
        f"| 启动面试 | {int(started)}（注册→启动 {percent(started, registrations)}） |",
        f"| 完整面试 | {int(completed)}（启动→完成 {percent(completed, started)}） |",
        "",
        "## 留存、满意度与付费意愿",
        "",
        f"- 次日面试留存：{metric('d1_interview_retention')}",
        f"- 7 天内复用：{metric('d7_reuse_window')}",
        f"- 平均满意度：{metric('average_satisfaction')} / 5",
        f"- 满意用户占比：{metric('satisfied_share')}",
        f"- 正向付费意愿：{metric('payment_interest_share')}",
        "",
        "## Token 效率",
        "",
        f"- 总 Token：{int(all_tokens)}",
        f"- 每次完整面试 Token：{'—' if not completed_ids else f'{completed_tokens / len(completed_ids):.0f}'}（完整面试 {len(completed_ids)} 次）",
        f"- 无效/重试请求占比：{percent(wasted_requests, all_requests)}",
        "",
        "## 渠道对比",
        "",
        "| 渠道 / 活动 / 内容 | 注册 | 启动率 | 完成率 |",
        "|---|---:|---:|---:|",
    ]
    for row in sorted(funnel, key=lambda r: number(r.get("registered_users")), reverse=True):
        label = " / ".join([row.get("utm_source", "direct"), row.get("utm_campaign", "none"), row.get("utm_content", "none")])
        lines.append(f"| {label} | {int(number(row.get('registered_users')))} | {number(row.get('registration_to_start_rate')):.1%} | {number(row.get('completion_rate')):.1%} |")

    lines += ["", "## 错误排行", "", "| 阶段 | 错误码 | 次数 |", "|---|---|---:|"]
    for row in sorted(errors, key=lambda r: number(r.get("error_count")), reverse=True)[:10]:
        lines.append(f"| {row.get('stage','')} | {row.get('error_code','')} | {int(number(row.get('error_count')))} |")
    if not errors:
        lines.append("| 无已记录错误 | — | 0 |")

    lines += [
        "", "## 产品结论填写区", "",
        "1. 本周最大流失步骤：",
        "2. 低满意度主要标签或错误：",
        "3. Token 消耗最高的 operation / 版本：",
        "4. 下周只验证的一个假设：",
        "5. 主指标与护栏指标：",
    ]
    output = folder / "weekly_summary.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成：{output}")


if __name__ == "__main__":
    main()
