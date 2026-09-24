import unittest
from unittest.mock import AsyncMock, patch

from app.deepseek import generate_report
from app.scoring import DIMENSIONS
from app.schemas import AnswerEvidence, ReportRequest, SpeechDeliveryMetrics


class ReportGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.selector_patcher = patch("app.agent_runtime.selection.chat_json", new_callable=AsyncMock)
        self.selector_chat = self.selector_patcher.start()
        self.selector_chat.return_value = {"skill_name": "report_generation", "reason": "需要生成证据型报告"}

    async def asyncTearDown(self) -> None:
        self.selector_patcher.stop()

    @patch("app.deepseek.settings")
    @patch("app.runtime_skills.report_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_unverifiable_evidence_is_safely_downgraded(self, chat: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "完成",
            "summary": "测试",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {"name": name, "level": 3, "score": None, "basis": "依据", "evidence": ["不存在的证据"], "suggestion": "补充细节"}
                for name in DIMENSIONS
            ],
            "question_reviews": [
                {"question_id": "q1", "strengths": ["亮点"], "issues": [], "evidence": ["不存在的证据"], "suggestion": "补充细节"}
            ],
        }
        request = ReportRequest(interview_id="00000000-0000-4000-8000-000000000001", target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer="不知道")])
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 0)
        self.assertTrue(all(item.score is None and not item.evidence for item in report.dimensions))
        self.assertEqual(report.question_reviews[0].strengths, ["亮点"])
        self.assertEqual(report.question_reviews[0].evidence, ["不知道"])

    @patch("app.deepseek.settings")
    @patch("app.runtime_skills.report_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_question_ids_are_grounded_to_exact_answer_text(self, chat: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "完成",
            "summary": "测试",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {"name": name, "level": 3, "score": None, "basis": "依据", "evidence": [], "evidence_question_ids": ["q1"], "suggestion": "补充细节"}
                for name in DIMENSIONS
            ],
            "question_reviews": [
                {"question_id": "q1", "strengths": ["有具体行动"], "issues": [], "evidence": ["模型改写的文字"], "suggestion": "补充结果"}
            ],
        }
        answer = "我先访谈用户，再根据反馈调整了功能优先级。"
        metrics = SpeechDeliveryMetrics(duration_ms=20_000, voiced_duration_ms=15_000, pause_count=2, average_pause_ms=1_000, longest_pause_ms=1_200, speech_rate_cpm=220, average_volume=3.2, volume_variation=1.1, sample_count=200)
        request = ReportRequest(interview_id="00000000-0000-4000-8000-000000000001", target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer=answer, delivery_metrics=metrics)])
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 67)
        self.assertTrue(all(item.evidence == [answer] for item in report.dimensions))
        self.assertEqual(next(item.score for item in report.dimensions if item.name == "流畅度"), 100)
        self.assertEqual(report.question_reviews[0].evidence, [answer])
        self.assertEqual(report.question_reviews[0].strengths, ["有具体行动"])


if __name__ == "__main__":
    unittest.main()
