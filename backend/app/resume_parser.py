from __future__ import annotations

import io
import logging
import re
import unicodedata

import pdfplumber

from .schemas import ResumeParseResponse, ResumeSection

logging.getLogger("pdfminer").setLevel(logging.ERROR)

MAX_PDF_BYTES = 10 * 1024 * 1024
SECTION_ALIASES = {
    "个人总结": "个人总结", "个人简介": "个人总结", "教育经历": "教育经历", "教育背景": "教育经历",
    "工作经历": "工作/实习经历", "实习经历": "工作/实习经历", "项目经历": "项目经历",
    "技能/证书及其他": "技能/证书及其他", "技能证书": "技能/证书及其他", "专业技能": "技能/证书及其他",
}


def parse_pdf(filename: str, data: bytes) -> ResumeParseResponse:
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF 文件不能超过 10 MB")
    if not data.startswith(b"%PDF"):
        raise ValueError("文件不是有效 PDF")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_texts = [(page.extract_text(x_tolerance=2, y_tolerance=3) or "").strip() for page in pdf.pages]
        page_count = len(pdf.pages)
    full_text = "\n".join(filter(None, page_texts)).replace("\x00", "")
    if not full_text.strip():
        raise ValueError("PDF 没有可提取文本；当前版本尚未启用 OCR")
    sections = _split_sections(full_text)
    warnings = ["请确认解析内容；排版复杂的 PDF 可能出现换行或顺序偏差。", "联系方式属于敏感信息，发送给模型前应移除。"]
    return ResumeParseResponse(filename=filename, page_count=page_count, sections=sections, warnings=warnings)


def _split_sections(text: str) -> list[ResumeSection]:
    buckets: list[tuple[str, list[str]]] = [("基本信息", [])]
    for raw_line in text.splitlines():
        line = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", raw_line).strip())
        normalized = line.replace(" ", "")
        heading = next((canonical for alias, canonical in SECTION_ALIASES.items() if normalized == alias), None)
        if heading:
            buckets.append((heading, []))
        elif line:
            buckets[-1][1].append(line)
    return [ResumeSection(title=title, content="\n".join(lines)) for title, lines in buckets if lines]
