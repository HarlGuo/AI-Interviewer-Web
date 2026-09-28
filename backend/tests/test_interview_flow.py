import json
import unittest
from unittest.mock import AsyncMock, patch

from app.agents.interview_graph import MAX_AGENT_TURNS, advance_interview, start_interview
from app.schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnAnswer, InterviewTurnRequest, ResumeSection
from app.skills.interview import AnswerDecision, generate_main_question, stage_plan

STAGE_LABELS = ["自我介绍", "简历深挖", "行为面试", "岗位专业", "结束反问"]


def start_request(mode: str = "formal", focus: str | None = None) -> InterviewAgentStartRequest:
    return InterviewAgentStartRequest(
        target_role="产品经理", job_description="负责用户研究和需求分析", mode=mode, focus=focus,
        resume_sections=[ResumeSection(title="项目经历", content="负责 CoachCraft 产品规划并完成 20 项验收")],
        resume_review_status="ai_verified",
    )


def turn_request(follow_up_count: int, answer: str, main_question_index: int = 1) -> InterviewTurnRequest:
    return InterviewTurnRequest(
        **start_request().model_dump(exclude={"interview_id"}), interview_id="session-1",
        current_question=InterviewQuestion(id="q1", stage=STAGE_LABELS[main_question_index], text="请介绍该项目。", is_follow_up=follow_up_count > 0, main_question_index=main_question_index, follow_up_count=follow_up_count),
        answers=[InterviewTurnAnswer(question_id="q1", question="请介绍该项目。", answer=answer, stage="简历深挖", is_follow_up=follow_up_count > 0)],
    )


def tool_call(name: str, call_id: str = "call-1") -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": "{}"}}]}


def activate_interview_skill(call_id: str = "call-skill") -> dict:
    message = tool_call("activate_skill", call_id)
    message["tool_calls"][0]["function"]["arguments"] = json.dumps({"skill_name": "conduct_resume_interviews"})
    return message


def final_message() -> dict:
    return {"role": "assistant", "content": json.dumps({"status": "ready", "reason": "工具结果已经足够"}, ensure_ascii=False)}


class InterviewAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_stage_plans_are_deterministic(self) -> None:
        self.assertEqual(len(stage_plan("formal", None)), 5)
        self.assertEqual(stage_plan("focused", "behavioral"), ["behavioral"] * 3)

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.generate_main_question", new_callable=AsyncMock)
    async def test_start_agent_runs_tool_then_model_again(self, generate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [activate_interview_skill(), tool_call("generate_interview_question"), final_message()]
        generate.return_value = InterviewQuestion(id="q1", stage="自我介绍", text="请结合 CoachCraft 经历做自我介绍。", main_question_index=0, follow_up_count=0)
        result = await start_interview(start_request())
        self.assertEqual(result.source, "resume_driven_agent")
        self.assertEqual(result.total_main_questions, 5)
        self.assertEqual(chat.await_count, 3)
        self.assertIn("conduct_resume_interviews", chat.await_args_list[1].kwargs["messages"][-1]["content"])
        third_messages = chat.await_args_list[2].kwargs["messages"]
        self.assertEqual(third_messages[-1]["role"], "tool")
        self.assertIn("CoachCraft", third_messages[-1]["content"])

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.evaluate_answer", new_callable=AsyncMock)
    async def test_follow_up_keeps_main_question_index(self, evaluate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [activate_interview_skill(), tool_call("evaluate_interview_answer"), final_message()]
        evaluate.return_value = AnswerDecision(action="follow_up", question="你个人具体负责了哪部分？", reason="个人贡献不清楚")
        result = await advance_interview(turn_request(0, "我们团队完成了这个项目。"))
        self.assertFalse(result.completed)
        self.assertTrue(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.main_question_index, 1)
        self.assertEqual(result.next_question.follow_up_count, 1)
        self.assertEqual(chat.await_count, 3)

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.generate_main_question", new_callable=AsyncMock)
    async def test_agent_observes_decision_then_calls_next_tool(self, generate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [
            activate_interview_skill(),
            tool_call("evaluate_interview_answer", "call-evaluate"),
            tool_call("generate_interview_question", "call-generate"),
            final_message(),
        ]
        generate.return_value = InterviewQuestion(id="q2", stage="行为面试", text="下一道主问题", main_question_index=2, follow_up_count=0)
        result = await advance_interview(turn_request(2, "还是比较笼统。"))
        self.assertFalse(result.next_question.is_follow_up)
        self.assertEqual(result.next_question.main_question_index, 2)
        self.assertIn("最多 2 次", result.decision_reason)
        self.assertEqual(chat.await_count, 4)
        fourth_messages = chat.await_args_list[3].kwargs["messages"]
        self.assertEqual([item["role"] for item in fourth_messages[-4:]], ["assistant", "tool", "assistant", "tool"])

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.generate_main_question", new_callable=AsyncMock)
    async def test_unknown_answer_advances_without_answer_model_call(self, generate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [activate_interview_skill(), tool_call("evaluate_interview_answer"), tool_call("generate_interview_question", "call-2"), final_message()]
        generate.return_value = InterviewQuestion(id="q2", stage="行为面试", text="下一道主问题", main_question_index=2, follow_up_count=0)
        result = await advance_interview(turn_request(0, "不知道"))
        self.assertFalse(result.next_question.is_follow_up)
        self.assertIn("不知道", result.decision_reason)

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    async def test_final_answer_before_required_tool_is_rejected_and_loop_continues(self, chat: AsyncMock) -> None:
        chat.side_effect = [final_message(), activate_interview_skill(), tool_call("generate_interview_question"), final_message()]
        with patch("app.skills.interview.generate_main_question", new_callable=AsyncMock) as generate:
            generate.return_value = InterviewQuestion(id="q1", stage="自我介绍", text="第一题", main_question_index=0, follow_up_count=0)
            result = await start_interview(start_request())
        self.assertEqual(result.question.text, "第一题")
        self.assertEqual(chat.await_count, 4)
        self.assertIn("还不足以结束", chat.await_args_list[1].kwargs["messages"][-1]["content"])

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.generate_main_question", new_callable=AsyncMock)
    async def test_malformed_final_output_is_corrected_once(self, generate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [
            activate_interview_skill(),
            tool_call("generate_interview_question"),
            {"role": "assistant", "content": '已完成\n{"status":"ready","reason":"问题已生成"}'},
            final_message(),
        ]
        generate.return_value = InterviewQuestion(
            id="q1", stage="自我介绍", text="第一题", main_question_index=0, follow_up_count=0,
        )
        result = await start_interview(start_request())
        self.assertEqual(result.question.text, "第一题")
        self.assertEqual(chat.await_count, 4)
        self.assertIn("只返回纯 JSON", chat.await_args_list[3].kwargs["messages"][-1]["content"])

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.interview.generate_main_question", new_callable=AsyncMock)
    async def test_malformed_final_output_fails_after_one_correction(self, generate: AsyncMock, chat: AsyncMock) -> None:
        chat.side_effect = [
            activate_interview_skill(),
            tool_call("generate_interview_question"),
            {"role": "assistant", "content": "not-json"},
            {"role": "assistant", "content": "still-not-json"},
        ]
        generate.return_value = InterviewQuestion(
            id="q1", stage="自我介绍", text="第一题", main_question_index=0, follow_up_count=0,
        )
        with self.assertRaisesRegex(ValueError, "一次纠正后"):
            await start_interview(start_request())

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    async def test_agent_loop_has_hard_turn_limit(self, chat: AsyncMock) -> None:
        chat.return_value = final_message()
        with self.assertRaisesRegex(RuntimeError, f"最多 {MAX_AGENT_TURNS} 轮"):
            await start_interview(start_request())
        self.assertEqual(chat.await_count, MAX_AGENT_TURNS)

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    async def test_unregistered_tool_is_rejected(self, chat: AsyncMock) -> None:
        bad = tool_call("activate_skill")
        bad["tool_calls"][0]["function"]["arguments"] = json.dumps({"skill_name": "invented_skill"})
        chat.return_value = bad
        with self.assertRaisesRegex(ValueError, "未注册"):
            await start_interview(start_request())

    @patch("app.agents.interview_graph.chat_with_tools", new_callable=AsyncMock)
    async def test_malformed_tool_arguments_are_rejected(self, chat: AsyncMock) -> None:
        bad = tool_call("generate_interview_question")
        bad["tool_calls"][0]["function"]["arguments"] = "{"
        chat.side_effect = [activate_interview_skill(), bad]
        with self.assertRaisesRegex(ValueError, "无效 JSON"):
            await start_interview(start_request())

    @patch("app.skills.interview.chat_json", new_callable=AsyncMock)
    async def test_paraphrased_resume_evidence_is_removed_without_blocking(self, chat: AsyncMock) -> None:
        chat.return_value = {"question": "请继续说明你在项目中补充的细节。", "resume_evidence": "模型概括但并非简历原文"}
        previous = turn_request(0, "我还负责了简历中没有展开说明的用户访谈。").answers
        result = await generate_main_question(start_request(), "behavioral", 2, previous)
        self.assertEqual(result.resume_evidence, "")
        sent_data = json.loads(chat.await_args.kwargs["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(sent_data["previous_answers"][0]["answer"], "我还负责了简历中没有展开说明的用户访谈。")


if __name__ == "__main__":
    unittest.main()
