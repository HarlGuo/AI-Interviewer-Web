# AI 面试官 · 作品集说明

一款面向毕业生和初入职场用户的 **AI 模拟面试练习产品**。用户确认 PDF 简历和目标岗位后，系统生成个性化问题、有限动态追问，并基于回答证据输出六维报告。

仓库：[HarlGuo/AI-Interviewer-Web](https://github.com/HarlGuo/AI-Interviewer-Web)

## 要解决的问题

校招准备里常见的是题库刷题或一次性生成「面试题清单」。真实面试更依赖：

- 简历里的项目能不能被追问清楚
- 回答有没有行为证据
- 练习反馈能不能对应当下这轮表现

本项目把流程收成一条可演示路径：**解析简历 → 用户确认 → 按岗位提问 → 限制追问次数 → 出具报告**。

## 功能边界

已实现：

- PDF 文本提取、联系方式脱敏、模型分类复核、用户确认后才进入面试
- 正式模拟与自我介绍 / 简历深挖 / 行为面试 / 岗位专业题专项训练
- 每道主问题最多两次追问，达到上限由程序推进，而不是把控制权完全交给模型
- 六维证据型报告；Web 可演示完整文字流程
- 可选的邮箱登录、人工审核、每日限额、RLS 用户隔离（Supabase）

刻意不做或尚未作为作品集卖点：

- 不提供公共大模型额度；演示使用面试者自己的 Key
- Web 语音能力不能代替 iOS/Android 真机验收
- 扫描件 OCR、支付、应用商店上架材料未作为当前范围

## 技术结构

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
| Agent | `backend/app/agents/interviewer/` | 状态、阶段策略、图编排 |
| Skills | `backend/app/runtime_skills/` | 可单独演进的生成与评价能力 |
| LLM | `backend/app/llm/deepseek.py` | 供应商适配；换模型不应改业务流程 |
| 数据 | `supabase/migrations/` | 账号、RLS、私有简历桶、用量与埋点 |

生产形态可以把 Web 静态资源和 API 打进同一个容器或 FunctionGraph 包，避免面试官还要配两套 URL。

## 实现上可讲的点

1. **确认前不面试**：解析结果必须用户确认，降低「模型读错简历还继续问」的风险。
2. **追问有硬上限**：策略写在 Agent/后端，而不是只写在提示词里。
3. **报告要对着回答**：评分输入是本轮问答，而不是简历本身的自我评价。
4. **密钥不出前端**：`EXPO_PUBLIC_*` 只放公开地址和 publishable key；模型 Key 只在后端环境变量。
5. **开发模式可演示**：`AUTH_MODE=development` 保留单人本地路径，方便作品集；云端模式才启用审核和日限额。

## 如何打包本仓库

```bash
python3 -m pip install reportlab   # 仅生成演示 PDF 时需要
python3 scripts/generate_sample_resume.py
./scripts/package-portfolio.sh
```

产物：`build/portfolio/AI-Interviewer-portfolio.zip`（不含依赖、密钥和 `dist/`）。

现场运行见 [DEMO.md](./DEMO.md)。Docker 一体包：

```bash
export DEEPSEEK_API_KEY=你自己的Key
docker compose up --build
```

## 面试时建议怎么介绍（90 秒）

「这是一个模拟面试练习产品，不是聊天机器人套皮。用户先上传并确认简历，系统按目标岗位出题；每道主问题最多追问两次，最后根据实际回答生成六维报告。前端是 Expo，后端是 FastAPI，面试流程用 LangGraph 编排，模型调用收口在独立适配器。作品集演示用 Docker 或本地 development 模式，不需要评委先注册账号。」
