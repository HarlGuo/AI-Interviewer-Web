# 作品集现场演示

这份说明面向面试官或需要 10 分钟内跑起来的评审。完整产品说明见 [PORTFOLIO.md](./PORTFOLIO.md)。

## 最快路径：Docker 一体包

电脑已安装 Docker 时，在解压后的项目根目录执行：

```bash
export DEEPSEEK_API_KEY=你自己的Key
docker compose up --build
```

浏览器打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)。

- 默认 `AUTH_MODE=development`，无需注册，适合现场演示。
- 前端静态资源和 FastAPI 由同一个容器提供，客户端会使用当前页面源站作为 API 地址。
- 演示简历使用仓库内的虚构文件 `examples/sample-resume.pdf`，不要上传真实个人信息。

## 没有 Docker：本地两个终端

1. 复制 `backend/.env.example` 为 `backend/.env`，只填写 `DEEPSEEK_API_KEY`，保持 `AUTH_MODE=development`。
2. 终端 1：

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

3. 终端 2：

```bash
cp .env.example .env.local
# 确认 EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run web
```

## 建议演示顺序（约 6 分钟）

1. 打开首页，说明这是面向校招/初入职场的模拟面试练习产品。
2. 进入「你的简历」，上传 `examples/sample-resume.pdf`，解析并确认。
3. 选择「正式模拟面试」，目标岗位填写「后端开发工程师」。
4. 用文字回答 1–2 题，展示主问题后的追问，而不是一次性抛出题库。
5. 结束或完成一轮后打开报告页，指出六维评分来自用户回答证据，而不是空泛评语。
6. 如有时间，打开 `backend/app/agents/interviewer/`，说明 Agent 编排与 Skill 边界。

## 不要在面试现场做的事

- 不要粘贴真实 DeepSeek / Supabase 密钥到聊天窗口或共享屏幕的文本文件里。
- 不要上传自己或他人的真实简历。
- 不要把 Web 浏览器语音能力当成 App 真机验收结果。
