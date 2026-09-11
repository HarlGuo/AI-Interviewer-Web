# AI Interviewer Web

一个面向毕业生和初入职场用户的 AI 模拟面试 Web 应用。用户上传并确认自己的 PDF 简历、填写目标岗位后，可进行个性化模拟面试、有限动态追问并获得基于实际回答证据的报告。

当前版本适合封闭测试，不提供公共 DeepSeek API Key。部署者必须配置自己的 Supabase 项目和 DeepSeek Key。

## 已实现

- 邮箱密码注册、登录、人工审核
- 每个已审核账号按北京时间每天一次面试
- PDF 确定性提取、AI 复核、程序校验、用户确认
- LangGraph 面试流程、简历深挖、有限动态追问
- 语音转写和文字备用输入
- 六维证据型面试报告
- Supabase RLS 用户隔离和私有简历文件策略

> 账号、审核状态和每日限额已经保存在 Supabase。简历、面试过程和报告目前仍保存在当前浏览器本地；清除浏览器数据或更换设备后无法恢复，云端同步尚待完成。

## 代码结构

```text
src/                    Expo Web 页面、状态与 API 调用
backend/app/agents/     LangGraph 流程
backend/app/skills/     运行时业务能力
backend/app/prompts/    模型提示词
backend/app/llm/        DeepSeek API 适配器
backend/tests/          后端测试
.agents/skills/         Codex 开发工作流，不参与线上运行
supabase/migrations/    数据表、RLS、人工审核和每日限额
render.yaml             Render 前后端部署配置
```

## 本地从零启动

需要安装 Git、Node.js LTS 和 Python 3.11 或更高版本。

```bash
git clone https://github.com/HarlGuo/AI-Interviewer-Web.git
cd AI-Interviewer-Web
npm install
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cp .env.example .env.local
```

在 `backend/.env` 填写自己的 Key：

```dotenv
DEEPSEEK_API_KEY=你的DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
ALLOWED_ORIGINS=http://localhost:8081
AUTH_MODE=development
```

真实 Key 只能写在 `backend/.env`，不得提交到 GitHub，也不得写入 `EXPO_PUBLIC_*` 变量。

打开终端 1，启动后端并保持运行：

```bash
source backend/.venv/bin/activate
python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

打开终端 2，启动 Web：

```bash
npm run web
```

浏览器访问 `http://localhost:8081`。本地默认使用 `AUTH_MODE=development`，不要求登录。

## 启用账号、人工审核和每日限额

1. 在 Supabase 新建项目。
2. 依次在 SQL Editor 运行：
   - `supabase/migrations/202609070001_initial_account_cloud.sql`
   - `supabase/migrations/202609110001_manual_approval_daily_limit.sql`
   - `supabase/migrations/202609110002_approved_user_rls.sql`
3. 在 Authentication 的 Email Provider 中启用邮箱密码注册。封闭测试可关闭 Confirm email；公开运营前应配置 SMTP、重新启用邮箱确认并增加 CAPTCHA。
4. 从 Supabase API 设置复制 Project URL 和 publishable key。
5. 将客户端公开配置写入 `.env.local`，将后端配置写入 `backend/.env`。

客户端 `.env.local`：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
EXPO_PUBLIC_SUPABASE_URL=https://你的项目编号.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=你的publishable-key
```

后端 `backend/.env` 追加：

```dotenv
AUTH_MODE=supabase
SUPABASE_URL=https://你的项目编号.supabase.co
SUPABASE_PUBLISHABLE_KEY=你的publishable-key
SUPABASE_JWT_AUDIENCE=authenticated
```

新用户注册后状态为 `pending`。管理员在 Supabase 的 `profiles` 表将对应用户的 `account_status` 改为 `approved`，用户刷新审核状态后才能使用。

## 免费部署到 Render

1. Fork 或使用自己的本仓库。
2. 登录 Render，选择 **New → Blueprint**。
3. 连接该 GitHub 仓库；Render 会读取根目录的 `render.yaml`。
4. 在 Render 页面填写三个未提交的变量：
   - 后端 `DEEPSEEK_API_KEY`
   - 后端 `SUPABASE_PUBLISHABLE_KEY`
   - Web `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
5. 部署完成后访问生成的 Web 地址。

Render 免费后端会在闲置后休眠，首次请求可能需要等待约一分钟，只适合 MVP 内测。长期数据应保存在 Supabase，不要写入 Render 临时磁盘。

## 验证

```bash
npx tsc --noEmit
npx expo export --platform web
source backend/.venv/bin/activate
cd backend && python -m pytest tests -q
```

## 安全说明

- DeepSeek Key、Supabase secret/service-role key 和数据库密码不得进入前端或 Git。
- 客户端只使用 Supabase publishable key；真实授权由 RLS 和后端 JWT 校验完成。
- 待审核用户在数据库层也不能读写面试业务数据。
- 用户只能访问自己的记录和私有简历路径。
- 面试评分必须给出理由、用户回答证据和可执行建议；证据不足必须明确标注。

## License

见 [LICENSE](LICENSE)。
