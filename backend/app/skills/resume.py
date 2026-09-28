from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..ai_resume_reviewer import review_resume
from ..resume_parser import parse_pdf
from ..schemas import ResumeParseResponse
from .runtime import RUNTIME_SKILLS, RUNTIME_TOOLS, RuntimeSkill, RuntimeTool


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeExtractionObservation(BaseModel):
    status: str = "extracted"
    page_count: int
    section_count: int
    requires_ai_review: bool = True


class ResumeVerificationObservation(BaseModel):
    status: str = "ai_verified"
    section_count: int
    issue_count: int
    requires_user_confirmation: bool = True


async def _extract_resume_pdf(context: dict, arguments: BaseModel) -> ResumeExtractionObservation:
    NoArguments.model_validate(arguments)
    parsed = parse_pdf(context["filename"], context["data"])
    context["parsed"] = parsed
    return ResumeExtractionObservation(page_count=parsed.page_count, section_count=len(parsed.sections))


async def _verify_resume_structure(context: dict, arguments: BaseModel) -> ResumeVerificationObservation:
    NoArguments.model_validate(arguments)
    parsed = context.get("parsed")
    if not isinstance(parsed, ResumeParseResponse):
        raise ValueError("必须先完成确定性 PDF 提取，才能执行 AI 结构复核")
    verified = await review_resume(parsed)
    context["result"] = verified
    return ResumeVerificationObservation(section_count=len(verified.sections), issue_count=len(verified.review_issues))


RUNTIME_TOOLS.register(RuntimeTool(
    name="extract_resume_pdf",
    description="对用户上传的 PDF 执行类型、大小、文本层校验、NFKC 规范化和规则分段。原始文件由后端上下文提供，不接受模型生成的文件参数。",
    input_model=NoArguments,
    handler=_extract_resume_pdf,
))

RUNTIME_TOOLS.register(RuntimeTool(
    name="verify_resume_structure",
    description="对确定性提取结果执行隐私脱敏的 AI 行分类和程序完整性校验，并只用原始行重建章节。必须在 extract_resume_pdf 成功后调用。",
    input_model=NoArguments,
    handler=_verify_resume_structure,
))

RUNTIME_SKILLS.register(RuntimeSkill(
    name="verified_resume_parsing",
    description="以确定性 PDF 提取、隐私保护的 AI 分类、程序校验和用户确认准备可用于个性化面试的简历。",
    instructions="""你正在执行“可验证简历解析”Skill。
- 先调用 extract_resume_pdf 完成确定性提取；成功后调用 verify_resume_structure。
- 不得跳过顺序，不得要求模型处理原始 PDF 字节，不得改写或补充简历事实。
- 工具 observation 只包含流程状态和计数；简历正文保留在受控后端上下文。
- verify_resume_structure 成功后结束本轮。结果仍需用户在界面确认，不能宣称简历事实已被证明真实。""",
    tool_names=("extract_resume_pdf", "verify_resume_structure"),
    supported_events=("resume_uploaded",),
    input_contract=(
        "用户主动上传的 PDF 文件，格式有效且大小不超过 10 MB",
        "原始文件字节只存在于后端受控上下文，不作为模型参数",
    ),
    output_contract=(
        "返回 ResumeParseResponse、原始行重建的章节、警告和复核问题",
        "只有完整 AI 分类和程序校验通过时 review_status 才能为 ai_verified",
    ),
    fact_constraints=(
        "源 PDF 提取文本是唯一事实来源，不改写、概括、增删或推断事实",
        "联系方式在 AI 分类前脱敏；外层 Agent observation 不包含简历正文",
    ),
    failure_policy=(
        "非法类型、超限、无文本层、行遗漏、重复、未知 ID 或非法章节时明确失败",
        "任何校验失败都不得标记为 ai_verified，也不得进入个性化面试",
    ),
    acceptance_criteria=(
        "每个原始内容行恰好一次归入允许章节且顺序不变",
        "界面展示解析警告并要求用户最终确认后才能用于面试",
    ),
))
