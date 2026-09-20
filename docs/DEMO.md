# 本地快速跑通

已部署的 Web 体验见仓库根目录 README 的「在线体验」。下面只适用于要在本机启动源码的情况。

## Docker

```bash
export DEEPSEEK_API_KEY=你的Key
docker compose up --build
```

浏览器打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)。

- 默认 `AUTH_MODE=development`，无需注册。
- 前端静态资源和 FastAPI 由同一个容器提供。
- 可用虚构简历 `examples/sample-resume.pdf`，不要上传真实个人信息。

## 不用 Docker

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

建议路径：首页 → 上传示例简历并确认 → 正式模拟（岗位可填后端开发工程师）→ 文字回答一两题 → 查看报告。
