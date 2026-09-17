import unittest
from unittest.mock import AsyncMock, patch

from app.agents.interview_graph import advance_interview, start_interview
from app.skills.interview import AnswerDecision, generate_main_question, stage_plan
from app.schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnAnswer, InterviewTurnRequest, ResumeSection


def start_request(mode: str = "formal", focus: str | None = None) -> InterviewAgentStartRequest:
    return InterviewAgentStartRequest(
        target_role="产品经理", job_description="负责用户研究和需求分析", mode=mode, focus=focus,
        resume_sections=[ResumeSection(title="项目经历", content="负责 CoachCraft 产品规划并完成 20 项验收")],
        resume_review_status="ai_verified",
    )


def turn_request(follow_up_count: int, answer: str) -> InterviewTurnRequest:
    return InterviewTurnRequest(
        **start_request().model_dump(), interview_id="session-1",
        current_question=InterviewQuestion(id="q1", stage="简历深挖", text="请介绍该项目。", is_follow_up=follow_up_count > 0, main_question_index=1, follow_up_count=follow_up_count),
        answers=[InterviewTurnAnswer(question_id="q1", question="请介绍该项目。", answer=answer, stage="简历深挖", is_follow_up=follow_up_count > 0)],
    )


class InterviewAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_stage_plans_are_deterministic(self) -> None:
        self.assertEqual(len(stage_plan("formal", None)), 5)
        self.assertEqual(stage_plan("focused", "behavioral"), ["behavioral"] * 3)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_start_uses_resume_agent_question(self, generate: AsyncMock) -> None:
        generate.return_value = {"question": "请结合 CoachCraft 经历做自我介绍。", "resume_evidence": "CoachCraft 产品规划"}
        result = await start_interview(start_request())
        self.assertEqual(result.source, "resume_driven_agent")
        self.assertEqual(result.total_main_questions, 5)

    @patch("app.runtime_skills.answer_evaluation.skill.chat_json", new_callable=AsyncMock)
    async def test_follow_up_keeps_main_question_index(self, evaluate: AsyncMock) -> None:
        evaluate.return_value = {"action": "follow_up", "question": "你个人具体负责了哪部分？", "reason": "个人贡献不清楚"}
        result = await advance_interview(turn_request(0, "我们团队完成了这个项目。"))
        self.assertFalse(result.completed)
        self.assertTrue(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.main_question_index, 1)
        self.assertEqual(result.next_question.follow_up_count, 1)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_third_follow_up_is_overridden_to_next_main(self, generate: AsyncMock) -> None:
        generate.return_value = {"question": "下一道主问题", "resume_evidence": ""}
        result = await advance_interview(turn_request(2, "还是比较笼统。"))
        self.assertFalse(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.main_question_index, 2)
        self.assertIn("最多 2 次", result.decision_reason)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_unknown_answer_advances_without_model_evaluation(self, generate: AsyncMock) -> None:
        generate.return_value = {"question": "下一道主问题", "resume_evidence": ""}
        result = await advance_interview(turn_request(0, "不知道"))
        self.assertFalse(result.next_question.is_follow_up)
        self.assertIn("不知道", result.decision_reason)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_paraphrased_resume_evidence_is_removed_without_blocking(self, chat: AsyncMock) -> None:
        chat.return_value = {"question": "请继续说明你在项目中补充的细节。", "resume_evidence": "模型概括但并非简历原文"}
        previous = turn_request(0, "我还负责了简历中没有展开说明的用户访谈。" ).answers
        result = await generate_main_question(start_request(), "behavioral", 2, previous)
        self.assertEqual(result.resume_evidence, "")
        sent_data = __import__('json').loads(chat.await_args.kwargs["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(sent_data["previous_answers"][0]["answer"], "我还负责了简历中没有展开说明的用户访谈。")


if __name__ == "__main__":
    unittest.main()
