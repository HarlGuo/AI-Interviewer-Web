#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_ROOT="$PROJECT_ROOT/build/functiongraph"
PACKAGE_PATH="$PROJECT_ROOT/build/ai-interviewer-functiongraph.zip"
PYTHON_CMD="${PYTHON_CMD:-$PROJECT_ROOT/backend/.venv/bin/python}"

if [ ! -x "$PYTHON_CMD" ]; then
  PYTHON_CMD=python3
fi

if [ -z "${EXPO_PUBLIC_SUPABASE_URL:-}" ] || [ -z "${EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY:-}" ]; then
  echo "请先设置 EXPO_PUBLIC_SUPABASE_URL 和 EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY。" >&2
  exit 1
fi

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

cd "$PROJECT_ROOT"
npx expo export --platform web
cp -R backend/app "$BUILD_ROOT/app"
cp -R dist "$BUILD_ROOT/dist"
cp deploy/functiongraph/bootstrap "$BUILD_ROOT/bootstrap"
chmod 755 "$BUILD_ROOT/bootstrap"

"$PYTHON_CMD" -m pip install \
  --quiet \
  --disable-pip-version-check \
  --requirement deploy/functiongraph/requirements.txt \
  --target "$BUILD_ROOT" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade

# 简历解析只做文字提取，不调用 pdfplumber 的页面转图片功能；移除其可选图像依赖以满足直传限制。
rm -rf \
  "$BUILD_ROOT/PIL" \
  "$BUILD_ROOT/pillow.libs" \
  "$BUILD_ROOT/Pillow-"*.dist-info \
  "$BUILD_ROOT/pypdfium2" \
  "$BUILD_ROOT/pypdfium2-"*.dist-info \
  "$BUILD_ROOT/pypdfium2_cfg" \
  "$BUILD_ROOT/pypdfium2_cli" \
  "$BUILD_ROOT/pypdfium2_raw"

cd "$BUILD_ROOT"
rm -f "$PACKAGE_PATH"
zip -q -9 -r "$PACKAGE_PATH" .

PACKAGE_MB=$(du -m "$PACKAGE_PATH" | awk '{print $1}')
echo "已生成：${PACKAGE_PATH}（约 ${PACKAGE_MB} MB）"
if [ "$PACKAGE_MB" -gt 40 ]; then
  echo "程序包超过 FunctionGraph ZIP 接口的 40 MB 限制，请缩减依赖或改为通过 OBS 部署。" >&2
  exit 1
fi
