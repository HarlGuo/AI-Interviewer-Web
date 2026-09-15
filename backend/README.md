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

## LangGraph 目录

- `app/agents/`：LangGraph 状态、节点、条件边和工作流入口。
- `app/skills/`：问题生成、回答判断、脱敏和确定性校验。
- `app/prompts/`：独立提示词。
- `app/llm/`：DeepSeek 等模型服务商适配器。
- `app/schemas.py`：API 数据契约。

运行测试：

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```
