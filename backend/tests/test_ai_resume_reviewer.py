import unittest
from unittest.mock import AsyncMock, patch

from app.ai_resume_reviewer import Assignment, ReviewPayload, review_resume
from app.schemas import ResumeParseResponse, ResumeSection


def sample_resume() -> ResumeParseResponse:
    return ResumeParseResponse(
        filename="resume.pdf",
        page_count=1,
        sections=[ResumeSection(title="基本信息", content="候选人\n13800138000 | user@example.com"), ResumeSection(title="项目经历", content="负责真实项目交付")],
        warnings=[],
    )


class AiResumeReviewerTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.ai_resume_reviewer.settings")
    @patch("app.ai_resume_reviewer._call_deepseek", new_callable=AsyncMock)
    async def test_reconstructs_only_from_original_lines(self, call: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        call.return_value = ReviewPayload(assignments=[
            Assignment(line_id="L001", section="基本信息"),
            Assignment(line_id="L002", section="基本信息"),
            Assignment(line_id="L003", section="项目经历"),
        ], issues=[])
        result = await review_resume(sample_resume())
        self.assertEqual(result.review_status, "ai_verified")
        self.assertIn("13800138000", result.sections[0].content)
        sent_lines = call.await_args.args[0]
        self.assertNotIn("13800138000", str(sent_lines))
        self.assertNotIn("user@example.com", str(sent_lines))

    @patch("app.ai_resume_reviewer.settings")
    @patch("app.ai_resume_reviewer._call_deepseek", new_callable=AsyncMock)
    async def test_rejects_missing_line(self, call: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        call.return_value = ReviewPayload(assignments=[Assignment(line_id="L001", section="基本信息")], issues=[])
        with self.assertRaisesRegex(ValueError, "遗漏"):
            await review_resume(sample_resume())

    @patch("app.ai_resume_reviewer.settings")
    @patch("app.ai_resume_reviewer._call_deepseek", new_callable=AsyncMock)
    async def test_rejects_unknown_section(self, call: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        call.return_value = ReviewPayload(assignments=[
            Assignment(line_id="L001", section="基本信息"), Assignment(line_id="L002", section="基本信息"), Assignment(line_id="L003", section="模型猜测"),
        ], issues=[])
        with self.assertRaisesRegex(ValueError, "不允许"):
            await review_resume(sample_resume())


if __name__ == "__main__":
    unittest.main()
