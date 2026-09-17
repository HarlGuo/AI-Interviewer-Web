import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools import BaseTool

from app.agents.interviewer import InterviewerAgent, build_skill_registry, interviewer_agent
from app.runtime_skills.question_generation import QuestionGenerationInput
from app.runtime_skills.resume_context import SafeResumeSection


def test_agent_descriptor_drives_policy_and_registered_tools() -> None:
    assert interviewer_agent.descriptor.name == "resume_interviewer"
    assert interviewer_agent.descriptor.framework == "langgraph"
    assert interviewer_agent.policy.max_follow_ups == 2
    assert interviewer_agent.policy.stage_plan("focused", "behavioral") == ["behavioral"] * 3
    assert [tool.name for tool in interviewer_agent.tools] == interviewer_agent.descriptor.skills
    assert all(isinstance(tool, BaseTool) for tool in interviewer_agent.tools)


def test_missing_declared_skill_fails_at_agent_startup(tmp_path: Path) -> None:
    descriptor = tmp_path / "AGENT.md"
    descriptor.write_text(
        """---
name: broken_interviewer
version: 1.0.0
description: test
framework: langgraph
skills: [resume_context, missing_skill]
configuration:
  max_follow_ups: 1
  focused_main_questions: 2
  formal_stages:
    - {key: behavioral, label: 行为面试}
  skill_bindings:
    resume_context: resume_context
    question_generation: missing_skill
    answer_evaluation: missing_skill
    report_generation: missing_skill
---
# test agent
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="未注册"):
        InterviewerAgent(build_skill_registry(), descriptor)


@patch("app.runtime_skills.question_generation.skill.chat_json", new_callable=AsyncMock)
def test_skill_markdown_is_used_as_runtime_instruction(chat: AsyncMock) -> None:
    chat.return_value = {"question": "请介绍你的用户研究经历。", "resume_evidence": ""}
    skill = interviewer_agent.registry.require("question_generation")
    asyncio.run(skill.invoke(QuestionGenerationInput(
        stage="behavioral",
        stage_label="行为面试",
        main_question_number=1,
        target_role="产品经理",
        confirmed_resume=[SafeResumeSection(title="项目经历", content="负责用户访谈")],
        searchable_resume_text="负责用户访谈",
    )))
    system_message = chat.await_args.kwargs["messages"][0]["content"]
    assert "个性化主问题生成" in system_message
    assert "不得编造公司、项目、职责" in system_message
