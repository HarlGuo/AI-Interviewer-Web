#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT_DIR="$PROJECT_ROOT/build/portfolio"
STAGE_DIR="$OUT_DIR/AI-Interviewer-portfolio"
ZIP_PATH="$OUT_DIR/AI-Interviewer-portfolio.zip"
REVISION=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
DATE_UTC=$(date -u +%Y-%m-%d)

cd "$PROJECT_ROOT"

if [ ! -f examples/sample-resume.pdf ]; then
  echo "缺少 examples/sample-resume.pdf，请先运行 scripts/generate_sample_resume.py" >&2
  exit 1
fi

rm -rf "$OUT_DIR"
mkdir -p "$STAGE_DIR"

git -C "$PROJECT_ROOT" archive --format=tar HEAD | tar -x -C "$STAGE_DIR"

# git archive 只包含已跟踪文件；演示简历若尚未入库则补一份。
if [ ! -f "$STAGE_DIR/examples/sample-resume.pdf" ]; then
  mkdir -p "$STAGE_DIR/examples"
  cp examples/sample-resume.pdf "$STAGE_DIR/examples/sample-resume.pdf"
fi

{
  echo "AI 面试官 · 作品集打包"
  echo "revision: $REVISION"
  echo "date_utc: $DATE_UTC"
  echo "source: https://github.com/HarlGuo/AI-Interviewer-Web"
  echo
  echo "本压缩包不含 node_modules、Python 虚拟环境、.env 密钥和构建产物。"
  echo "面试演示请先阅读 docs/PORTFOLIO.md 与 docs/DEMO.md。"
} > "$STAGE_DIR/BUNDLE.txt"

# 防止误把密钥打进作品集
if git -C "$PROJECT_ROOT" ls-files --error-unmatch '.env' >/dev/null 2>&1 \
  || git -C "$PROJECT_ROOT" ls-files --error-unmatch 'backend/.env' >/dev/null 2>&1; then
  echo "拒绝打包：仓库跟踪了 .env 文件。" >&2
  exit 1
fi

if find "$STAGE_DIR" -type f \( -name '.env' -o -name '.env.local' -o -name '.env.*' ! -name '.env.example' \) | grep -q .; then
  echo "拒绝打包：暂存目录中出现环境变量文件。" >&2
  exit 1
fi

if grep -RInE 'DEEPSEEK_API_KEY=sk-|SUPABASE_SECRET_KEY=[^[:space:]]+' "$STAGE_DIR" \
  --exclude='*.example' \
  --exclude='package-portfolio.sh' \
  --exclude='PORTFOLIO.md' \
  --exclude='DEMO.md' \
  --exclude='README.md' \
  >/dev/null 2>&1; then
  echo "拒绝打包：疑似密钥出现在源码中。" >&2
  exit 1
fi

rm -f "$ZIP_PATH"
(
  cd "$OUT_DIR"
  zip -q -r "AI-Interviewer-portfolio.zip" "AI-Interviewer-portfolio"
)

SIZE=$(du -h "$ZIP_PATH" | awk '{print $1}')
echo "已生成作品集压缩包：$ZIP_PATH（$SIZE）"
echo "revision $REVISION"
echo "解压后阅读 docs/DEMO.md 即可开始演示。"
