# Backend

## 本地配置

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

然后只在 `backend/.env` 中填写新生成的 Key：

```dotenv
DEEPSEEK_API_KEY=你的新Key
AUTH_MODE=supabase
SUPABASE_URL=https://你的项目编号.supabase.co
SUPABASE_PUBLISHABLE_KEY=你的publishable-key
SUPABASE_SECRET_KEY=你的后端secret-key
```

`backend/.env` 已被 Git 忽略。不要使用已经出现在聊天、截图、日志或 Git 历史中的 Key。
`SUPABASE_SECRET_KEY` 也只能保存在后端，用于持久化面试、报告、埋点和 DeepSeek Token 用量，不能写进任何 `EXPO_PUBLIC_*` 变量。

启动：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

DeepSeek 用于已确认简历的结构复核、个性化面试问题、动态追问决策和证据型报告。阶段索引与每道主问题最多两次追问由后端代码强制控制。

## Agent、Skill 与 Tool 目录

- `app/agents/`：LangGraph 承载的简历和面试有限 Agent loop、运行状态及停止条件。
- `app/skills/runtime.py`：产品运行时 Skill/Tool 注册表与 `activate_skill`。
- `app/skills/resume.py`：可验证简历解析 Skill 及其 Tools。
- `app/skills/interview.py`：动态面试 Skill 及其 Tools。
- `app/prompts/`：独立提示词。
- `app/llm/`：DeepSeek 等模型服务商适配器。
- `app/schemas.py`：API 数据契约。

每次 API 请求启动一个 Agent run。模型先从产品 Skill 目录调用 `activate_skill`，加载该 Skill 的 instructions 和 Tool 白名单，再调用 Tools、读取结果并继续规划。后端设置最大步骤数，并确定性控制隐私、阶段、追问上限和最终用户可见结果。

运行测试：

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```
