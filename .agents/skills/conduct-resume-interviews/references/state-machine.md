# 面试状态机

## 阶段

```text
正式：self-introduction → resume-deep-dive → behavioral → role-specific → closing → complete
专项：所选专项 × 3 道主问题 → complete
```

## 状态

- `interview_id`：会话 ID
- `stage_plan`：不可变阶段列表
- `main_question_index`：后端控制的主问题索引
- `follow_up_count`：当前主问题追问次数（0–2）
- `current_question`：唯一当前问题
- `answers`：有序问答记录及追问标记
- `confirmed_resume_sections`：已确认且已排除联系方式/无关信息的简历章节
- `target_role`、`job_description`：目标岗位与职位描述

## 模型输出

```json
{
  "action": "follow_up | next_main | complete",
  "question": "一道问题；仅 complete 时可为空",
  "reason": "回答充分性理由",
  "weakness": "可选；基于回答的薄弱点",
  "resume_evidence": "可选；使用的已确认简历摘录"
}
```

## 后端转换

```text
follow_up 且次数 < 2  → 保持主问题，追问次数 +1
follow_up 且次数 >= 2 → 覆盖为 next_main
next_main 且有下一阶段 → 主问题索引 +1，追问次数归零
next_main 且已到末段 → complete
提前 complete → 覆盖为 next_main；客户端明确提前结束除外
```

后端生成确定的下一阶段主问题；不信任模型提供的计数器。

## 隐私与文件

只发送相关的已确认简历章节、职位描述和回答历史；不发送或记录电话、邮箱、地址、证件号、肖像、原始 PDF 字节或完整载荷。

- LangGraph 编排：`backend/app/agents/interview_graph.py`
- 运行时 Skills：`backend/app/skills/interview.py`
- 提示词：`backend/app/prompts/interview.py`
- LLM 适配：`backend/app/llm/deepseek.py`
- 数据结构：`backend/app/schemas.py`
- 路由：`backend/app/main.py`
- 客户端 API/状态：`src/services/gateways.ts`、`src/state/app-context.tsx`
- 界面：`src/app/interview.tsx`
