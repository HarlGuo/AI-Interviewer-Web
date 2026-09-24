# 设计说明

校招准备里常见的是题库刷题，或一次性生成「面试题清单」。真实面试更依赖：简历项目能不能被追问清楚、回答有没有行为证据、反馈能不能对应当下这轮表现。

本项目把流程收成：**解析简历 → 用户确认 → 按岗位提问 → 限制追问次数 → 出具报告**。

## 能力边界

已实现：

- PDF 文本提取、联系方式脱敏、模型分类复核；确认前不进入面试
- 正式模拟，以及自我介绍 / 简历深挖 / 行为面试 / 岗位专业题
- 每道主问题最多两次追问，上限由后端推进，而不是只写在提示词里
- 六维报告的输入是本轮问答，而不是简历上的自我评价
- 线上内测：邮箱登录、人工审核、每日限额、RLS 用户隔离；体验者不必自备模型 Key 或数据库

尚未覆盖：

- 扫描件 OCR、支付、应用商店上架
- Web 浏览器语音不能代替 iOS / Android 真机验收
- 在本机单独启动源码时，开发者仍需自备 DeepSeek Key（密钥不进仓库）

## 结构

```text
Expo / React Native（Web + 移动端）
        │  REST
        ▼
FastAPI ── PDF 解析 / 鉴权 / 限额
        │
        ▼
LangGraph Interviewer Agent
        ├── question_generation
        ├── resume_project_followup
        ├── answer_evaluation
        └── report_generation
        │
        ▼
DeepSeek Chat Completions（可替换的 LLM 适配器）
```

| 层 | 位置 | 职责 |
|---|---|---|
| 客户端 | `src/` | 页面、本地会话草稿、语音/文字输入、API gateway |
| HTTP API | `backend/app/main.py` | 简历解析、面试回合、报告、健康检查；生产包同时托管 `dist/` |
| Agent | `backend/app/agents/interviewer/` | 状态、阶段策略、运行时 Skill 选择与图编排 |
| Skills | `backend/app/runtime_skills/` | 带描述和输入输出契约、可由 Agent 自主发现的执行能力 |
| LLM | `backend/app/llm/deepseek.py` | 供应商适配；换模型不应改业务流程 |
| 数据 | `supabase/migrations/` | 账号、RLS、私有简历桶、用量与埋点 |

线上把 Web 静态资源和 API 打进同一个腾讯云 CloudBase Run 容器，体验者只访问一个网址。本地默认 `AUTH_MODE=development` 可跳过登录，专门用来调试流程；云端模式才启用审核和日限额。
