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

# LangSmith 仅在开启链路追踪时才使用 zstandard；本项目未启用追踪。
# 删除该可选扩展及缓存，避免 Base64 后的请求体超过 FunctionGraph API 网关限制。
rm -rf \
  "$BUILD_ROOT/zstandard" \
  "$BUILD_ROOT/zstandard-"*.dist-info
find "$BUILD_ROOT" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$BUILD_ROOT" -type d -name tests -prune -exec rm -rf {} +

# GitHub Actions 在 Linux 上构建时移除二进制符号；本地 macOS 构建跳过此步骤。
if [ "$(uname -s)" = "Linux" ] && command -v strip >/dev/null 2>&1; then
  find "$BUILD_ROOT" -type f -name '*.so' -exec strip --strip-unneeded {} +
fi

cd "$BUILD_ROOT"
rm -f "$PACKAGE_PATH"
zip -q -9 -r "$PACKAGE_PATH" .

PACKAGE_MB=$(du -m "$PACKAGE_PATH" | awk '{print $1}')
echo "已生成：${PACKAGE_PATH}（约 ${PACKAGE_MB} MB）"
if [ "$PACKAGE_MB" -gt 28 ]; then
  echo "程序包超过 FunctionGraph API 直传安全阈值 28 MB；请改用 OBS 部署，不再删除运行依赖。" >&2
  exit 1
fi
