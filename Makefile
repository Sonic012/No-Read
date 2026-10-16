.PHONY: install run sync sync-full setup-notion status check test clean help

# 默认目标
help:
	@echo "可用命令:"
	@echo "  make install       - 安装依赖"
	@echo "  make run           - 运行主程序"
	@echo "  make sync          - 同步微信读书数据到 Notion"
	@echo "  make sync-full     - 忽略本地缓存，全量刷新一遍"
	@echo "  make setup-notion  - 只补齐 Notion 模板结构"
	@echo "  make status        - 查看同步状态"
	@echo "  make check         - 检查微信读书网关与 Notion 连通性"
	@echo "  make test          - 运行测试"
	@echo "  make clean         - 清理缓存"
	@echo "  make setup         - 完整环境设置"

# 安装依赖
install:
	uv sync

# 运行主程序
run:
	uv run python main.py help

# 同步
sync:
	uv run python main.py sync

sync-full:
	uv run python main.py sync --full

setup-notion:
	uv run python main.py setup-notion

status:
	uv run python main.py status

check:
	uv run python main.py check

# 运行测试
test:
	uv run pytest tests/ -q

# 清理缓存
clean:
	uv cache clean

# 完整环境设置（新人使用）
setup: install
	@echo "环境设置完成！"
	@echo "运行 'make setup-notion' 补齐 Notion 结构，再运行 'make sync' 开始同步"
