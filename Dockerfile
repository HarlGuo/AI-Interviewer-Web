# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS web-build
WORKDIR /workspace

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY app.json tsconfig.json ./
COPY assets ./assets
COPY src ./src
RUN npx expo export --platform web \
    && find dist -type f -name '*.html' -exec sed -i 's#</head>#<script src="/runtime-config.js"></script></head>#' {} +

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /workspace

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip config set global.index-url https://mirrors.cloud.tencent.com/pypi/simple \
    && pip config set global.trusted-host mirrors.cloud.tencent.com \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app ./backend/app
COPY --from=web-build /workspace/dist ./dist

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]
