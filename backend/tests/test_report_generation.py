import unittest
from unittest.mock import AsyncMock, patch

from app.deepseek import generate_report
from app.scoring import DIMENSIONS
from app.schemas import AnswerEvidence, ReportRequest


class ReportGenerationTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
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
        request = ReportRequest(target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer="不知道")])
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 0)
        self.assertTrue(all(item.score is None and not item.evidence for item in report.dimensions))
        self.assertEqual(report.question_reviews[0].strengths, ["亮点"])
        self.assertEqual(report.question_reviews[0].evidence, ["不知道"])

    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
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
        request = ReportRequest(target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer=answer)])
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 60)
        self.assertTrue(all(item.score == 60 and item.evidence == [answer] for item in report.dimensions))
        self.assertEqual(report.question_reviews[0].evidence, [answer])
        self.assertEqual(report.question_reviews[0].strengths, ["有具体行动"])


if __name__ == "__main__":
    unittest.main()
