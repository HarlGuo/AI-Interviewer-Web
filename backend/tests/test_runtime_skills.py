import json
import unittest
from unittest.mock import AsyncMock, patch

from app.agents.resume_agent import parse_resume_with_agent
from app.schemas import ResumeParseResponse, ResumeSection
from app.skills.runtime import AgentToolCall, RUNTIME_SKILLS, RUNTIME_TOOLS


def tool_call(name: str, *, arguments: dict | None = None, call_id: str = "call-1") -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False)},
        }],
    }


def final_message() -> dict:
    return {"role": "assistant", "content": json.dumps({"status": "ready", "reason": "Skill 已完成"}, ensure_ascii=False)}


def parsed_resume(*, verified: bool = False) -> ResumeParseResponse:
    return ResumeParseResponse(
        filename="resume.pdf",
        page_count=1,
        sections=[ResumeSection(title="基本信息", content="13800138000 user@example.com"), ResumeSection(title="项目经历", content="负责产品规划")],
        warnings=["请确认"],
        review_status="ai_verified" if verified else "rule_only",
    )


class RuntimeSkillTests(unittest.IsolatedAsyncioTestCase):
    def test_product_catalog_contains_two_real_runtime_skills(self) -> None:
        catalog = {item["name"]: item for item in RUNTIME_SKILLS.catalog()}
        self.assertIn("verified_resume_parsing", catalog)
        self.assertIn("conduct_resume_interviews", catalog)
        self.assertIn("resume_uploaded", catalog["verified_resume_parsing"]["supported_events"])
        self.assertIn("answer_submitted", catalog["conduct_resume_interviews"]["supported_events"])
        activated = RUNTIME_SKILLS.activate("verified_resume_parsing", event="resume_uploaded").activation_result()
        self.assertTrue(activated["input_contract"])
        self.assertTrue(activated["output_contract"])
        self.assertTrue(activated["fact_constraints"])
        self.assertTrue(activated["failure_policy"])
        self.assertTrue(activated["acceptance_criteria"])

    def test_skill_activation_rejects_wrong_product_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "不支持事件"):
            RUNTIME_SKILLS.activate("verified_resume_parsing", event="answer_submitted")

    async def test_skill_cannot_call_another_skills_tool(self) -> None:
        skill = RUNTIME_SKILLS.activate("verified_resume_parsing", event="resume_uploaded")
        call = AgentToolCall(id="call-1", name="generate_interview_question", arguments_json="{}")
        with self.assertRaisesRegex(ValueError, "不允许调用"):
            await RUNTIME_TOOLS.execute(call, {}, allowed_tools=skill.tool_names)

    @patch("app.agents.resume_agent.chat_with_tools", new_callable=AsyncMock)
    @patch("app.skills.resume.review_resume", new_callable=AsyncMock)
    @patch("app.skills.resume.parse_pdf")
    async def test_resume_agent_activates_skill_then_uses_its_tools_without_exposing_resume_text(
        self, parse: object, review: AsyncMock, chat: AsyncMock,
    ) -> None:
        parse.return_value = parsed_resume()
        review.return_value = parsed_resume(verified=True)
        chat.side_effect = [
            tool_call("activate_skill", arguments={"skill_name": "verified_resume_parsing"}, call_id="skill"),
            tool_call("extract_resume_pdf", call_id="extract"),
            tool_call("verify_resume_structure", call_id="verify"),
            final_message(),
        ]
        result = await parse_resume_with_agent("resume.pdf", b"%PDF test")
        self.assertEqual(result.review_status, "ai_verified")
        self.assertEqual(chat.await_count, 4)
        activation_observation = chat.await_args_list[1].kwargs["messages"][-1]["content"]
        self.assertIn("verified_resume_parsing", activation_observation)
        extraction_observation = chat.await_args_list[2].kwargs["messages"][-1]["content"]
        verification_observation = chat.await_args_list[3].kwargs["messages"][-1]["content"]
        self.assertNotIn("13800138000", extraction_observation + verification_observation)
        self.assertNotIn("user@example.com", extraction_observation + verification_observation)
        self.assertIn("requires_user_confirmation", verification_observation)


if __name__ == "__main__":
    unittest.main()
