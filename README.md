# AI 面试官

面向校招和初入职场的模拟面试练习产品。用户确认 PDF 简历和目标岗位后，系统生成个性化问题、有限动态追问，并基于本轮回答给出六维报告。

技术栈是 Expo / React Native、FastAPI 和 LangGraph。线上 Web 已接入 DeepSeek 与 Supabase：体验只需邮箱注册并等待审核，页面上不会要求填写模型 Key 或数据库配置。

## 在线体验

1. 打开[作者提供](https://ai-interviewer-web-d3c7u5b38cfb5-1486840156.ap-shanghai.app.tcloudbase.com/)的 Web 地址。
2. 用邮箱注册，审核通过后登录。
3. 上传简历（可用仓库中的虚构示例 `examples/sample-resume.pdf`），确认解析结果。
4. 选择正式模拟或专项训练，填写目标岗位后开始面试。

请不要上传真实个人信息。模型 Key 只存在于服务端环境变量，不会出现在前端。

## 当前功能

- PDF 简历选择、大小与格式检查
- 确定性文本提取、联系方式脱敏、DeepSeek 分类复核和用户确认
- 正式模拟面试，以及自我介绍、简历深挖、行为面试、岗位专业题专项训练
- 基于已确认简历与真实 JD 生成个性化问题
- 每道主问题最多两次动态追问，达到上限后由程序强制推进
- 语音优先回答：iOS/Android 系统持续识别，用户结束回答后自动提交；文字用于查看、修正或备用输入
- 基于用户实际回答证据生成六维面试报告
- 本地草稿和当前会话恢复

## 技术栈

- Expo SDK 57、React Native 0.86、TypeScript、Expo Router
- FastAPI、Pydantic、pdfplumber、HTTPX
- DeepSeek Chat Completions API
- AsyncStorage 本地保存开发阶段状态
- Supabase Auth、PostgreSQL RLS 和私有 Storage（账号与云数据基础框架）
- iOS Speech framework / Android SpeechRecognizer

## 目录结构

```text
AI面试官/
├── src/                    # 页面、组件、状态和 API gateway
├── backend/                # FastAPI、LangGraph Agent、Skills、LLM 与测试
├── docs/                   # 设计说明与本地快速跑通
├── examples/               # 虚构演示简历（非真实个人信息）
├── .agents/skills/         # 简历解析与动态面试工作流
├── supabase/migrations/    # 数据表、RLS 与私有文件策略
├── assets/                 # App 图标和静态资源
├── docker-compose.yml      # 本地一体包：Web 静态资源 + FastAPI
├── app.json                # Expo 与原生权限配置
├── .env.example            # 客户端后端地址示例
└── backend/.env.example    # 后端模型配置示例
```

设计取舍见 [docs/DESIGN.md](docs/DESIGN.md)。本机跑通主路径见 [docs/DEMO.md](docs/DEMO.md)。

## 生产部署（腾讯云 CloudBase）

内测环境部署在腾讯云 CloudBase Run 服务 `ai-interviewer-web-git`：一个容器同时提供 Expo Web 页面和 FastAPI。账号、审核状态、每日限额和面试记录保存在 Supabase。

在 CloudBase 控制台对该服务发布新版本（GitHub 仓库 `HarlGuo/AI-Interviewer-Web`，根目录 `Dockerfile`，端口 8080）。DeepSeek API Key、Supabase Secret Key 只放在云托管环境变量中，不要提交到 GitHub。

用户注册后默认只能看到“等待审核”。管理员在 Supabase 打开 **Table Editor → profiles**，将 `account_status` 从 `pending` 改成 `approved`。

每日限额在表 `daily_interview_allowances`：按北京时间每个账号每天只能成功启动一场新面试。`interview_id` 只标识这一场；同一场超时重试不会重复扣次。面试未完成时进度保存在本机，切回页面会恢复；完成后首页显示今日次数已用完。按文件名顺序执行 `supabase/migrations/`。

## 本地运行要求

- [VS Code](https://code.visualstudio.com/)
- [Node.js LTS](https://nodejs.org/)（会同时安装 npm）
- [Python 3.11 或更高版本](https://www.python.org/downloads/)
- 只看 Web 页面不需要 Xcode；运行 iPhone 版本需要 macOS + Xcode；运行 Android 版本需要 Android Studio
- 自己申请的 DeepSeek API Key
- 测试简历必须是你有权使用的 PDF；建议先移除不必要的敏感信息

下面的命令默认使用 macOS。命令应粘贴到 VS Code 顶部菜单“终端 → 新建终端”打开的终端中，不要粘贴到 Python 文件里，也不要复制命令前面的 `$`、`%` 等提示符。

## 零基础启动总览

第一次启动需要依次完成：

```text
下载代码 → 安装前端依赖 → 创建 Python 虚拟环境 → 配置自己的模型 Key
→ 启动后端 → 配置客户端地址 → 启动 App
```

需要同时保留两个终端：

- **终端 1：后端**，成功后会持续显示 `Uvicorn running`，不要关闭。
- **终端 2：前端**，执行 `npm run web`、`npm run ios` 或真机构建命令。

以后再次运行时不必重复安装，只需要启动后端和前端。

> 默认 `AUTH_MODE=development`，因此原有本地单人测试不要求注册账号。要测试邮箱注册和用户隔离，请按本文“启用邮箱登录”配置自己的 Supabase 项目。

## 本地对接自己的 Supabase（二次开发）

已部署内测的用户不需要做这一节。只有你在自己电脑上要测「邮箱登录 + 审核 + 日限额」，才需要新建一个 Supabase 项目。

### 1. 创建属于你的项目

1. 登录 [Supabase](https://supabase.com/) 并新建项目。
2. 打开项目的 SQL Editor。
3. 完整复制并运行 `supabase/migrations/202609070001_initial_account_cloud.sql`。
4. 再按文件名顺序运行 `supabase/migrations/` 中其余迁移，包括 `202609140001_product_analytics.sql`。
5. 在 **Authentication → Sign In / Providers → Email** 中启用邮箱密码登录。内测阶段可关闭 **Confirm email**，注册后由管理员在 `profiles` 表人工审核；正式公开前应配置 SMTP、重新开启邮箱确认并增加 CAPTCHA。

迁移会创建用户、简历、岗位、面试、问题、回答、报告、用量、删除请求和审计结构，并创建非公开的 `resumes` 文件桶。

### 2. 配置客户端公开变量

在 Supabase 项目设置中复制 **Project URL** 和 **publishable key**。写入项目根目录 `.env.local`：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
EXPO_PUBLIC_SUPABASE_URL=https://你的项目编号.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=你的publishable-key
```

publishable key允许放入客户端，但它不等于管理员密钥；安全性依赖迁移中已经开启的 RLS。**不要**把 service-role key、secret key或数据库密码写进 `.env.local`。

### 3. 让后端验证登录身份

在 `backend/.env` 增加：

```dotenv
AUTH_MODE=supabase
SUPABASE_URL=https://你的项目编号.supabase.co
SUPABASE_PUBLISHABLE_KEY=你的publishable-key
SUPABASE_SECRET_KEY=你的后端secret-key
SUPABASE_JWT_AUDIENCE=authenticated
```

`SUPABASE_SECRET_KEY` 只允许出现在 `backend/.env` 或云后端环境变量中，用于保存面试记录、埋点和 Token 用量。绝不能以 `EXPO_PUBLIC_` 开头，也不能提交到 GitHub。

修改环境变量后必须重新启动后端和 Expo。健康检查中的 `auth_mode` 应为 `supabase`，`supabase_configured` 应为 `true`。

### 4. 测试邮箱登录

1. 打开 Web 后应先进入登录页。
2. 输入邮箱和至少 8 位密码，选择“注册”。
3. 注册成功后只能看到“等待审核”，不能开始面试。
4. 管理员在 Supabase 的 `profiles` 表把该用户的 `account_status` 改为 `approved`。
5. 用户点击“刷新审核状态”后进入首页；每天第一次成功生成面试首题后，当日额度即用完。
6. 退出登录后应回到登录页。

当前设备缓存会按 Supabase 用户 ID 隔离，不会把 A 用户的本地简历展示给 B 用户。下一阶段仍需要将这些数据真正写入云表，不能把当前缓存当成云备份。

## 1. 获取代码并安装前端依赖

在 VS Code 中打开终端，然后逐行执行：

```bash
git clone https://github.com/HarlGuo/AI_Interviewer.git
cd AI_Interviewer
npm install
```

如果已经下载过项目，不要再次 `git clone`，直接在 VS Code 中打开 `AI_Interviewer` 文件夹。终端执行下面的命令时，应能看到 `backend`、`src` 和 `package.json`：

```bash
pwd
ls
```

如果看不到这些文件，说明终端不在项目根目录，需要先执行 `cd` 进入项目文件夹。

## 2. 配置本地大模型 API

项目不提供公共或官方模型 Key。复制后端环境变量模板：

```bash
cp backend/.env.example backend/.env
```

在 VS Code 左侧展开 `backend`，打开新出现的 `.env`，填写：

```dotenv
DEEPSEEK_API_KEY=填写你自己的DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
ALLOWED_ORIGINS=http://localhost:8081,http://localhost:19006
```

API Key 只能写在 `backend/.env`。不要写入 `app.json`、`.env.local`、`src/`、截图、Issue 或 Git 提交。`backend/.env` 已在 `.gitignore` 中排除。

当前后端按 DeepSeek Chat Completions 接口实现。模型 HTTP 调用统一位于 `backend/app/llm/deepseek.py`；Agent 角色和阶段定义位于 `backend/app/agents/interviewer/AGENT.md`；LangGraph 编排位于 `backend/app/agents/interviewer/`；可执行 Skill 位于 `backend/app/runtime_skills/`。更换模型供应商时应新增 LLM 适配器，而不是修改 Agent 流程。

## 3. 首次安装本地后端

先确认 Python 版本：

```bash
python3 --version
```

版本必须是 3.11 或更高，例如 `Python 3.12.7`。如果显示 3.8、3.9、命令不存在或版本不符合要求，请先安装新版 Python，再关闭并重新打开 VS Code。

在项目根目录执行：

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

激活成功后，终端提示符前通常会出现 `(.venv)`。再检查程序是否来自项目虚拟环境：

```bash
which python
python --version
```

`which python` 返回的路径应包含 `AI_Interviewer/backend/.venv/`。

### 如果提示 activate 不存在

如果看到以下错误：

```text
source: no such file or directory: backend/.venv/bin/activate
```

说明虚拟环境没有成功创建、创建过程被中断，或者终端不在项目根目录。先用 `pwd` 和 `ls` 确认位置；位置正确后执行：

```bash
python3 -m venv --clear backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

不要从 GitHub 寻找 `.venv`：它是每台电脑单独生成的依赖环境，已被 `.gitignore` 排除，不会上传到仓库。

### Windows PowerShell

Windows 用户创建和激活环境的命令是：

```powershell
py -3.11 -m venv backend/.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

## 4. 启动并验证后端

每次重新打开项目后，在项目根目录新建“终端 1”并执行：

```bash
source backend/.venv/bin/activate
python -m uvicorn app.main:app \
  --app-dir backend \
  --reload \
  --host 0.0.0.0 \
  --port 8000
```

看到下面的文字表示后端已启动：

```text
Uvicorn running on http://0.0.0.0:8000
```

此时 **Terminal 1 正在运行后端，不能继续输入其他命令，也不要关闭它**。这是正常状态，不是卡住。

现在立刻新建 **Terminal 2**：

1. 点击 VS Code 顶部菜单“终端 → 新建终端”，或者点击终端面板右上角的 `+`。
2. 新终端出现命令提示符后，用 `pwd` 和 `ls` 检查位置。
3. `ls` 应该能看到 `backend`、`src` 和 `package.json`。如果看不到，先用 `cd` 进入 `AI_Interviewer` 项目根目录。

从下面的健康检查开始，直到启动 App，所有命令都在 **Terminal 2** 中执行。先验证后端：

```bash
curl http://127.0.0.1:8000/health
```

预期返回 `status: ok`，并且 `deepseek_configured` 为 `true`。如果是 `false`，检查 Key 是否写在 `backend/.env`。修改后回到 Terminal 1 按 `Control + C` 停止后端，再重新执行启动命令。接口文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

## 5. 配置客户端后端地址

**本节所有命令继续在 Terminal 2 中执行；Terminal 1 保持 Uvicorn 运行。**

在 Terminal 2 复制客户端环境变量模板：

```bash
cp .env.example .env.local
```

然后在 VS Code 左侧文件列表打开项目根目录下的 `.env.local`。它和 `backend/.env` 是两个不同文件：

- `backend/.env` 保存自己的 DeepSeek Key，只给后端使用。
- 项目根目录的 `.env.local` 只保存客户端访问后端的公开地址，绝不能填写模型 Key。

先决定下一节要使用哪种运行方式，再填写对应地址。

### Web 或 iOS 模拟器

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### iPhone 或 Android 真机

这里的“真机”指现实中拿在手里的实体 iPhone 或 Android 手机，不是电脑里的模拟器，也不是浏览器。

手机与电脑需连接同一个 Wi-Fi。在 **Terminal 2** 执行下面的命令查看 Mac 的 Wi-Fi 地址：

```bash
ipconfig getifaddr en0
```

假设结果为 `192.168.1.23`，则 `.env.local` 应写为：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.23:8000
```

先在手机浏览器访问 `http://192.168.1.23:8000/health`。能够看到健康检查结果后再启动 App。

Android Studio 模拟器通常使用：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
```

`EXPO_PUBLIC_*` 变量会进入客户端安装包，只能放公开的后端地址，绝不能放模型 Key。

## 6. 启动 App

继续使用 **Terminal 2**，不要新建或占用 Terminal 1。确认 Terminal 2 位于项目根目录，然后从下面三种方式中选择一种。

| 方式 | 是什么 | 能否验证完整语音功能 | 适合谁 |
|---|---|---:|---|
| Web | 在电脑浏览器打开 | 不保证 | 第一次启动、检查页面和后端 |
| iOS 模拟器 | Mac 里运行的虚拟 iPhone | 不保证 | 没有实体 iPhone 时测试 iOS 页面 |
| iPhone 真机 | 实体 iPhone 安装开发版 App | 可以 | 完整测试麦克风、权限和实际体验 |

建议先完成 Web 测试，确认简历解析和问题生成正常，再进行真机测试。

### 路线 A：Web，最快看到页面

确认 `.env.local` 是：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

执行：

```bash
npm run web
```

终端会显示一个本地网址，浏览器通常会自动打开。确保终端 1 的后端仍在运行，然后按下面顺序检查：

1. 首页能打开。
2. 上传并解析一份有权使用的 PDF 简历。
3. 检查解析结果并确认简历。
4. 进入“面试”，选择训练类型并填写目标岗位。
5. 点击“开始面试”，等待第一道问题。
6. 输入文字、提交回答并完成报告。

Web 适合验证核心流程，但浏览器语音能力不一致，不能作为最终语音验收结果。

### 路线 B：iOS 模拟器，不需要实体 iPhone

仅适用于 Mac。

1. 从 Mac App Store 安装 Xcode。
2. 第一次打开 Xcode，等待它完成组件安装并同意许可。
3. 确认 `.env.local` 使用 `http://127.0.0.1:8000`。
4. 保持终端 1 的后端运行。
5. 在终端 2 执行：


```bash
npx expo run:ios
```

第一次会生成原生工程并编译，耗时通常比 Web 长。编译完成后，Mac 会打开一个虚拟 iPhone 并安装 App。模拟器适合检查页面和业务流程，但麦克风及系统语音识别能力不能代替实体设备验收。

### 路线 C：实体 iPhone，完整功能推荐

这是测试麦克风权限、系统语音识别和真实手机体验的推荐方式。需要 Mac、Xcode、Apple ID、实体 iPhone 和连接线。

1. 安装并打开 Xcode，进入 `Xcode → Settings → Accounts`，登录自己的 Apple ID。
2. 用数据线连接 iPhone 和 Mac，解锁手机并选择“信任此电脑”。
3. 在 iPhone 打开“设置 → 隐私与安全性 → 开发者模式”，按提示重启并确认开启。
4. 打开 `app.json`，把占位 Bundle ID：

   ```json
   "bundleIdentifier": "com.placeholder.aiinterviewer"
   ```

   改成属于自己的唯一值，例如：

   ```json
   "bundleIdentifier": "com.yourname.aiinterviewer"
   ```

   `yourname` 需要替换为自己的英文或拼音标识。
5. 确保手机和 Mac 连接同一个 Wi-Fi。
6. 按上一节查出 Mac 局域网 IP，并写入 `.env.local`，不能使用 `127.0.0.1`。
7. 用手机 Safari 打开 `http://电脑IP:8000/health`。打不开时先解决网络问题，不要继续构建。
8. 保持终端 1 的后端运行，在终端 2 执行：

```bash
npx expo run:ios --device
```

9. 出现设备列表时选择自己的 iPhone；出现签名选项时选择刚登录的 Apple 开发团队。
10. 安装完成后在 iPhone 打开“AI 面试官”。首次点击语音输入时，再按系统提示允许麦克风和语音识别权限。

这个项目使用自定义原生语音模块，普通 Expo Go 不包含它，所以不能用 Expo Go 完整测试语音功能。`npx expo run:ios --device` 安装的是包含该模块的开发构建。

### 路线 D：实体 Android 手机

需要先安装 Android Studio、Android SDK，并在手机开启开发者选项和 USB 调试。手机与电脑连接后执行：

```bash
npx expo run:android --device
```

`.env.local` 同样要填写电脑局域网 IP。不同品牌手机的开发者模式入口不同，应以手机厂商说明为准。

## 7. 以后如何再次启动

以后打开项目时，不需要重新创建虚拟环境或重复安装依赖。

终端 1：

```bash
source backend/.venv/bin/activate
python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

终端 2：

```bash
npm run web
```

如果你使用模拟器或真机，把最后一条替换为对应命令：

```bash
npx expo run:ios
# 或
npx expo run:ios --device
# 或
npx expo run:android --device
```

## 8. 常见问题

### `npm: command not found`

Node.js 尚未安装，或安装后没有重启 VS Code。安装 Node.js LTS，然后重新打开 VS Code。

### `python3: command not found` 或 Python 版本低于 3.11

安装 Python 3.11 以上版本，重新打开 VS Code，再运行 `python3 --version`。

### `No module named uvicorn`

虚拟环境没有激活或依赖没有安装。重新执行：

```bash
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
```

### `deepseek_configured` 是 `false`

Key 没有写在正确位置。只检查 `backend/.env`，不要把 Key 写到项目根目录的 `.env.local`。

### App 提示无法连接后端

- 确认终端 1 仍显示后端正在运行。
- 模拟器使用 `127.0.0.1`，真机使用电脑的局域网 IP。
- 真机和电脑必须连接同一个局域网。
- 先用手机浏览器打开 `http://电脑IP:8000/health`。
- 修改 `.env.local` 后，停止前端并重新启动。

### 点击“开始面试”后提示无法连接

这通常不是按钮失效，而是后端没有运行。回到终端 1，确认仍能看到 Uvicorn 日志，并重新执行健康检查。Web 版本会显示实际错误；如果页面是旧版本，先执行 `git pull` 后重新启动前端。

### 页面能打开，但语音识别不能使用

普通 Expo Go 不包含项目使用的原生语音模块。请使用 `npx expo run:ios --device` 或 `npx expo run:android --device` 安装开发构建。

### 真机 Safari 打不开 `/health`

- 确认后端使用了 `--host 0.0.0.0`，而不是只监听 `127.0.0.1`。
- 确认手机和电脑在同一个 Wi-Fi，且没有启用访客网络隔离。
- 检查 macOS 防火墙是否阻止 Python 接收连接。
- `.env.local` 中填写电脑局域网 IP，不是手机 IP。

### iPhone 构建提示签名或 Bundle Identifier 错误

- 确认 Xcode 已登录 Apple ID。
- 确认 `app.json` 中的 `bundleIdentifier` 已改成自己的唯一值。
- 保持 iPhone 解锁、信任电脑并开启开发者模式，然后重试 `npx expo run:ios --device`。

## 9. App 使用流程

1. 上传有权使用的 PDF 简历。
2. 点击解析和 AI 复核，逐项核对提取结果。
3. 用户确认简历后，进入“面试”。
4. 选择正式模拟或一种专项训练。
5. 填写真实目标岗位；JD 可选，但不得虚构。
6. 开始面试并逐题回答。
7. 使用语音时，中间停顿后应继续识别；点击“结束回答并自动提交”后无需再次确认转写。
8. 每道主问题最多追问两次；完成后查看证据型面试报告。

AI 复核不能保证简历绝对零错误，也不验证简历陈述真实性。报告仅用于练习反馈，不代表录用概率。

## 测试与检查

前端：

```bash
npx tsc --noEmit
npx expo install --check
npx expo export --platform web
```

后端：

```bash
cd backend
.venv/bin/python -m unittest discover -s tests -v
```

私人测试简历不存在时，相关本地测试会跳过，不应把私人 PDF 加入仓库。

如需在本机运行私人简历解析测试，只通过临时环境变量提供 Git 忽略目录中的文件路径，不要把姓名或文件名写进测试代码：

```bash
cd backend
PRIVATE_RESUME_PATH="../local-data/private-resume.pdf" .venv/bin/python -m unittest tests.test_resume_parser -v
```

## 隐私和安全

- 已部署环境里，DeepSeek Key 和 Supabase Secret 只存在于云端环境变量，不进 Git，也不进前端安装包。
- 本地开发时，模型 Key 只写在 `backend/.env`，不要写进 `EXPO_PUBLIC_*`。
- 联系方式会在简历内容发送给模型前脱敏，但使用者仍应避免上传不必要的敏感信息。
- 麦克风和语音识别权限只在用户主动点击语音输入后申请。
- 未经用户确认的语音转写不能提交、评分或进入报告。
- 云端内测已启用邮箱登录、人工审核、每日限额和 RLS 用户隔离；本地默认 `AUTH_MODE=development` 仍是单人调试，不能把本机缓存当成多用户隔离。
- 正式对公开放前仍应补齐邮箱验证、SMTP、隐私政策和数据删除入口。

## 更多文档

- [可验证简历解析 Skill](.agents/skills/verified-resume-parsing/SKILL.md)
- [简历驱动动态面试 Skill](.agents/skills/conduct-resume-interviews/SKILL.md)

## 当前限制

- 内测用户使用已部署服务时，不需要自己提供 DeepSeek 或 Supabase。仓库本身不内置密钥；你要在本机跑或另外部署时，仍需自备 Key 并配置环境变量。
- 扫描版 PDF 的 OCR、支付和 App Store 上架材料尚未完成。
- Web 浏览器语音能力不稳定，原生语音识别需要在目标 iOS/Android 设备上验收。
