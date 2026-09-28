import unittest
import json
from unittest.mock import AsyncMock, patch

from app.deepseek import generate_report
from app.scoring import DIMENSIONS
from app.schemas import AnswerEvidence, ReportRequest, SpeechDeliveryMetrics


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
        request = ReportRequest(interview_id="00000000-0000-4000-8000-000000000001", target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer="不知道")])
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
        metrics = SpeechDeliveryMetrics(duration_ms=20_000, voiced_duration_ms=15_000, pause_count=2, average_pause_ms=1_000, longest_pause_ms=1_200, speech_rate_cpm=220, average_volume=3.2, volume_variation=1.1, sample_count=200)
        request = ReportRequest(interview_id="00000000-0000-4000-8000-000000000001", target_role="产品经理", mode="focused", completed=True, answers=[AnswerEvidence(question_id="q1", question="问题", answer=answer, delivery_metrics=metrics)])
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 67)
        self.assertEqual(report.completion, "已完成面试，共完成 1 道题。")
        self.assertTrue(all(item.evidence == [answer] for item in report.dimensions))
        self.assertEqual(next(item.score for item in report.dimensions if item.name == "流畅度"), 100)
        self.assertEqual(report.question_reviews[0].evidence, [answer])
        self.assertEqual(report.question_reviews[0].strengths, ["有具体行动"])

    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
    async def test_evidence_ids_are_filtered_deduplicated_and_limited_to_two(
        self, chat: AsyncMock, settings: object,
    ) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "完成",
            "summary": "测试",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {
                    "name": name,
                    "level": 3,
                    "score": None,
                    "basis": "依据",
                    "evidence": [],
                    "evidence_question_ids": ["q3", "missing", "q1", "q3", "q2"],
                    "suggestion": "补充细节",
                }
                for name in DIMENSIONS
            ],
            "question_reviews": [],
        }
        request = ReportRequest(
            interview_id="00000000-0000-4000-8000-000000000001",
            target_role="产品经理",
            mode="focused",
            completed=True,
            answers=[
                AnswerEvidence(question_id="q1", question="问题1", answer="回答1"),
                AnswerEvidence(question_id="q2", question="问题2", answer="回答2"),
                AnswerEvidence(question_id="q3", question="问题3", answer="回答3"),
            ],
        )
        report = await generate_report(request)
        self.assertTrue(all(item.evidence == ["回答3", "回答1"] for item in report.dimensions if item.name != "流畅度"))

    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
    async def test_dimension_without_valid_evidence_id_is_downgraded(
        self, chat: AsyncMock, settings: object,
    ) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "完成",
            "summary": "测试",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {
                    "name": name,
                    "level": 4,
                    "score": None,
                    "basis": "模型声称有证据",
                    "evidence": ["模型改写的证据"],
                    "evidence_question_ids": ["missing"],
                    "suggestion": "补充细节",
                }
                for name in DIMENSIONS
            ],
            "question_reviews": [],
        }
        request = ReportRequest(
            interview_id="00000000-0000-4000-8000-000000000001",
            target_role="产品经理",
            mode="focused",
            completed=True,
            answers=[AnswerEvidence(question_id="q1", question="问题", answer="真实回答")],
        )
        report = await generate_report(request)
        self.assertEqual(report.overall_score, 0)
        self.assertTrue(all(item.level is None and item.score is None and item.basis == "证据不足" for item in report.dimensions))

    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
    async def test_completion_uses_actual_answer_count_for_ended_early_report(
        self, chat: AsyncMock, settings: object,
    ) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "已完成全14道题",
            "summary": "测试",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {
                    "name": name,
                    "level": None,
                    "score": None,
                    "basis": "证据不足",
                    "evidence": [],
                    "evidence_question_ids": [],
                    "suggestion": "补充细节",
                }
                for name in DIMENSIONS
            ],
            "question_reviews": [],
        }
        request = ReportRequest(
            interview_id="00000000-0000-4000-8000-000000000001",
            target_role="产品经理",
            mode="focused",
            completed=False,
            answers=[
                AnswerEvidence(question_id="q1", question="问题1", answer="回答1"),
                AnswerEvidence(question_id="q2", question="问题2", answer="回答2"),
            ],
        )
        report = await generate_report(request)
        self.assertEqual(report.completion, "本次面试提前结束，共完成 2 道题。")

    @patch("app.deepseek.settings")
    @patch("app.deepseek.chat_json", new_callable=AsyncMock)
    async def test_sensitive_personal_attributes_are_removed_before_model_and_grounding(
        self, chat: AsyncMock, settings: object,
    ) -> None:
        settings.deepseek_api_key = "configured"
        chat.return_value = {
            "overall_score": 0,
            "completion": "完成",
            "summary": "候选人35岁，但项目经验清晰。",
            "evidence_notice": "仅依据回答",
            "dimensions": [
                {
                    "name": name,
                    "level": 3,
                    "score": None,
                    "basis": "项目行动清晰",
                    "evidence": [],
                    "evidence_question_ids": ["q1"],
                    "suggestion": "补充结果",
                }
                for name in DIMENSIONS
            ],
            "question_reviews": [{
                "question_id": "q1",
                "strengths": ["项目经验具体"],
                "issues": ["开头提及年龄、性别和婚育信息"],
                "evidence": [],
                "suggestion": "保持聚焦岗位能力",
            }],
        }
        sensitive_answer = (
            "我今年35岁，是女性，也有孩子，不过这些和工作能力关系不大。"
            "我负责客户培训和反馈整理，推动登录流程建议进入产品迭代。"
        )
        request = ReportRequest(
            interview_id="00000000-0000-4000-8000-000000000001",
            target_role="客户成功经理",
            mode="focused",
            completed=True,
            answers=[AnswerEvidence(question_id="q1", question="请介绍项目。", answer=sensitive_answer)],
        )
        report = await generate_report(request)
        sent_payload = chat.await_args.kwargs["messages"][1]["content"]
        rendered_report = json.dumps(report.model_dump(), ensure_ascii=False)
        for marker in ("35岁", "女性", "有孩子", "年龄", "性别", "婚育"):
            self.assertNotIn(marker, sent_payload)
            self.assertNotIn(marker, rendered_report)
        self.assertIn("推动登录流程建议进入产品迭代", rendered_report)


if __name__ == "__main__":
    unittest.main()
