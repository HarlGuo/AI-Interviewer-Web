#!/usr/bin/env python3
"""Generate a fictional, text-extractable PDF resume for portfolio demos."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

LINES = [
    ("title", "林晓桐"),
    ("meta", "应届本科 · 计算机科学与技术 · 求职意向：后端开发工程师"),
    ("meta", "本文件为虚构演示简历，不含真实联系方式。"),
    ("heading", "个人总结"),
    ("body", "熟悉 Python 与 TypeScript，能独立完成 Web API、数据表设计和前端联调。"),
    ("body", "课程项目中负责面试练习产品的后端编排、简历解析与报告生成，关注可测试性和隐私边界。"),
    ("heading", "教育经历"),
    ("body", "某大学 · 计算机科学与技术 · 本科 · 2022.09 – 2026.06"),
    ("body", "核心课程：数据结构、操作系统、数据库系统、软件工程。GPA 3.6/4.0"),
    ("heading", "项目经历"),
    ("body", "AI 模拟面试练习系统 · 核心开发 · 2025.12 – 2026.04"),
    ("body", "基于已确认简历和目标岗位生成个性化问题，主问题最多两次动态追问，输出六维证据型报告。"),
    ("body", "前端使用 Expo 与 React Native，后端使用 FastAPI 与 LangGraph Agent。"),
    ("body", "校园二手书交易平台 · 后端负责人 · 2025.03 – 2025.07"),
    ("body", "设计商品、订单与消息接口，使用 PostgreSQL 约束库存，接口测试覆盖核心下单路径。"),
    ("heading", "实习经历"),
    ("body", "某互联网公司 · 后端开发实习生 · 2025.07 – 2025.10"),
    ("body", "参与内容审核后台接口改造，将同步任务改为队列处理，高峰期超时率下降。"),
    ("heading", "技能/证书及其他"),
    ("body", "Python、TypeScript、FastAPI、PostgreSQL、React Native、Git、单元测试"),
    ("body", "英语 CET-6；能阅读英文技术文档并撰写接口说明。"),
]


def _font_path() -> Path:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    raise SystemExit("未找到可用的中文字体，无法生成演示简历 PDF。")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "examples" / "sample-resume.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)

    font_path = _font_path()
    pdfmetrics.registerFont(TTFont("ResumeCJK", str(font_path), subfontIndex=0))

    page = canvas.Canvas(str(output), pagesize=A4)
    width, height = A4
    x = 22 * mm
    y = height - 24 * mm
    max_width = width - 44 * mm

    for kind, text in LINES:
        if kind == "title":
            page.setFont("ResumeCJK", 20)
            leading = 12 * mm
        elif kind == "heading":
            y -= 4 * mm
            page.setFont("ResumeCJK", 13)
            leading = 9 * mm
        elif kind == "meta":
            page.setFont("ResumeCJK", 10)
            leading = 6.5 * mm
        else:
            page.setFont("ResumeCJK", 10)
            leading = 6.2 * mm

        wrapped = _wrap(page, text, "ResumeCJK", page._fontsize, max_width)
        for index, line in enumerate(wrapped):
            page.drawString(x, y, line)
            y -= leading if index == 0 else leading * 0.95
            if y < 22 * mm:
                page.showPage()
                y = height - 24 * mm
                page.setFont("ResumeCJK", 10)

    page.save()
    print(f"已生成：{output}")


def _wrap(page: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    if page.stringWidth(text, font_name, font_size) <= max_width:
        return [text]
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if page.stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    main()
