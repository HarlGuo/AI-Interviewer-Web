# LangGraph Agent 架构

后端按职责分层，API 路由不再直接承载 Agent 逻辑：

```text
backend/app/
├── agents/
│   └── interview_graph.py   # LangGraph 节点、条件边和流程入口
├── skills/
│   └── interview.py         # 生成主问题、评估回答、脱敏与确定性校验
├── prompts/
│   └── interview.py         # 面试提示词
├── llm/
│   └── deepseek.py          # 唯一的 DeepSeek HTTP/JSON 适配层
├── schemas.py               # API 数据契约
├── scoring.py               # 确定性评分规则
└── main.py                  # FastAPI 路由与错误映射
```

## 边界

- `agents` 只负责流程：开始、校验、评估、追问或推进、结束。
- `skills` 是可单测能力，不掌握路由和密钥。
- `prompts` 只保存模型指令，禁止混入 API 调用。
- `llm` 只处理服务商协议、超时、重试和 JSON，不决定面试业务。
- 追问次数、阶段推进和完成条件仍由程序控制，不能交给模型。
- LangGraph 输入继续使用现有 Pydantic 请求模型，因此移动端 API 无需变更。

## 面试图

```text
开始图：START → 准备阶段计划 → 生成首题 → END

答题图：START → 校验状态 → 评估回答
                          ├─ follow_up → 构造追问 → END
                          └─ next_main → 下一主问题/完成 → END
```

当前图使用请求携带的完整状态，兼容现有客户端。接入 Supabase 持久化后，可增加 LangGraph checkpointer，但数据库仍应作为产品数据的事实来源。

## 与 `.agents/skills` 的关系

`.agents/skills` 是 Codex 开发时读取的规则，不会进入产品运行时。`backend/app/skills` 是 LangGraph 实际调用的 Python 能力。两者保留同一组业务不变量，但用途不同：前者防止后续开发破坏规则，后者在服务器上真正执行规则。

`agents/openai.yaml` 只提供 Codex UI 名称、简介和默认提示，不参与 App 构建与 LangGraph 执行。保留它便于发现 Skill；删除它不会影响线上 App，但会降低开发时的可发现性。
