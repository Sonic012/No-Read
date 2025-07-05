#!/bin/bash

# 项目启动脚本

echo "🚀 启动 No-Read 项目..."

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ uv 未安装，请先安装 uv"
    echo "运行: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 检查是否首次运行
if [ ! -d ".venv" ]; then
    echo "🔧 首次运行，正在安装依赖..."
    uv sync
    uv run playwright install
fi

# 启动项目
echo "▶️  启动项目..."
uv run python src/main.py 