import unittest
from unittest.mock import AsyncMock, patch

from app.agents.interviewer import interviewer_agent
from app.agents.interview_graph import advance_interview, start_interview
from app.runtime_skills.question_generation import PreviousAnswer, QuestionGenerationInput
from app.runtime_skills.resume_context import SafeResumeSection
from app.schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnAnswer, InterviewTurnRequest, ProjectInterviewContext, ResumeSection


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


def project_turn_request(*, follow_up_count: int = 0, answer: str = "我负责用户访谈。", insufficient_count: int = 0, round_count: int = 1) -> InterviewTurnRequest:
    question_id = f"project-q-{round_count}"
    context = ProjectInterviewContext(
        project_key="project-12345678",
        project_resume_evidence="负责 CoachCraft 产品规划并完成 20 项验收",
        round_count=round_count,
        consecutive_insufficient_count=insufficient_count,
        question_ids=[question_id],
        visited_project_evidence=["负责 CoachCraft 产品规划并完成 20 项验收"],
    )
    return InterviewTurnRequest(
        **start_request().model_dump(),
        interview_id="session-project",
        current_question=InterviewQuestion(
            id=question_id,
            stage="简历深挖",
            text="请介绍 CoachCraft 项目。",
            is_follow_up=follow_up_count > 0,
            main_question_index=1,
            follow_up_count=follow_up_count,
            resume_evidence=context.project_resume_evidence,
            project_context=context,
        ),
        answers=[InterviewTurnAnswer(
            question_id=question_id,
            question="请介绍 CoachCraft 项目。",
            answer=answer,
            stage="简历深挖",
            is_follow_up=follow_up_count > 0,
        )],
    )


class InterviewAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_stage_plans_are_deterministic(self) -> None:
        self.assertEqual(len(interviewer_agent.policy.stage_plan("formal", None)), 5)
        self.assertEqual(interviewer_agent.policy.stage_plan("focused", "behavioral"), ["behavioral"] * 3)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_formal_start_uses_stable_skill_template_without_llm(self, generate: AsyncMock) -> None:
        result = await start_interview(start_request())
        self.assertEqual(result.source, "resume_driven_agent")
        self.assertEqual(result.total_main_questions, 5)
        self.assertIn("产品经理", result.question.text)
        self.assertIn("自我介绍", result.question.text)
        generate.assert_not_awaited()

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    async def test_resume_deep_dive_question_creates_project_context(self, generate: AsyncMock) -> None:
        evidence = "负责 CoachCraft 产品规划并完成 20 项验收"
        generate.return_value = {"question": "请介绍 CoachCraft 项目的背景。", "resume_evidence": evidence}
        result = await start_interview(start_request(mode="focused", focus="resume-deep-dive"))
        context = result.question.project_context
        self.assertIsNotNone(context)
        self.assertEqual(context.project_resume_evidence, evidence)
        self.assertEqual(context.round_count, 1)
        self.assertEqual(context.question_ids, [result.question.id])

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
        skill = interviewer_agent.registry.require("question_generation")
        result = await skill.invoke(QuestionGenerationInput(
            stage="behavioral",
            stage_label="行为面试",
            main_question_number=3,
            target_role="产品经理",
            job_description="负责用户研究和需求分析",
            confirmed_resume=[SafeResumeSection(title="项目经历", content="负责 CoachCraft 产品规划并完成 20 项验收")],
            previous_answers=[PreviousAnswer(question=item.question, answer=item.answer) for item in previous],
            searchable_resume_text="负责 CoachCraft 产品规划并完成 20 项验收",
        ))
        self.assertEqual(result.resume_evidence, "")
        sent_data = __import__('json').loads(chat.await_args.kwargs["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(sent_data["previous_answers"][0]["answer"], "我还负责了简历中没有展开说明的用户访谈。")

    @patch("app.runtime_skills.resume_project_followup.skill.chat_json", new_callable=AsyncMock)
    async def test_resume_project_stage_uses_dedicated_followup_skill(self, project_chat: AsyncMock) -> None:
        project_chat.return_value = {
            "action": "follow_up",
            "information_quality": "effective",
            "newly_covered_targets": [{
                "target": "personal_responsibility",
                "answer_id": "project-q-1",
                "evidence_quote": "我负责用户访谈",
            }],
            "next_target": "result",
            "question": "这些访谈最终产生了什么可核对的结果？",
            "reason": "个人职责已覆盖，项目结果未覆盖。",
        }
        result = await advance_interview(project_turn_request())
        self.assertTrue(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.project_context.round_count, 2)
        self.assertEqual(result.next_question.project_context.coverage.personal_responsibility, "covered")
        self.assertEqual(project_chat.await_count, 1)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    @patch("app.runtime_skills.resume_project_followup.skill.chat_json", new_callable=AsyncMock)
    async def test_two_consecutive_insufficient_project_answers_force_topic_switch(
        self, project_chat: AsyncMock, question_chat: AsyncMock,
    ) -> None:
        project_chat.return_value = {
            "action": "follow_up",
            "information_quality": "insufficient",
            "newly_covered_targets": [],
            "next_target": "personal_responsibility",
            "question": "你个人具体负责了什么？",
            "reason": "回答缺少有效信息。",
        }
        question_chat.return_value = {"question": "请介绍一次你解决团队分歧的经历。", "resume_evidence": ""}
        result = await advance_interview(project_turn_request(answer="不太清楚。", insufficient_count=1, round_count=2, follow_up_count=1))
        self.assertFalse(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.stage, "行为面试")
        self.assertIn("连续两次", result.decision_reason)

    @patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
    @patch("app.runtime_skills.resume_project_followup.skill.chat_json", new_callable=AsyncMock)
    async def test_not_responsible_switches_without_calling_project_model(
        self, project_chat: AsyncMock, question_chat: AsyncMock,
    ) -> None:
        question_chat.return_value = {"question": "请介绍一次跨团队合作经历。", "resume_evidence": ""}
        result = await advance_interview(project_turn_request(answer="这个部分由其他人负责。"))
        self.assertEqual(project_chat.await_count, 0)
        self.assertEqual(result.next_question.stage, "行为面试")
        self.assertIn("不是本人负责", result.decision_reason)


if __name__ == "__main__":
    unittest.main()
