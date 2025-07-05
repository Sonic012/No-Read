.PHONY: install run test clean help

# 默认目标
help:
	@echo "可用命令:"
	@echo "  make install    - 安装依赖"
	@echo "  make run        - 运行主程序"
	@echo "  make test       - 运行测试"
	@echo "  make clean      - 清理缓存"
	@echo "  make setup      - 完整环境设置"

# 安装依赖
install:
	uv sync
	uv run playwright install

# 运行主程序
run:
	uv run python src/main.py

# 运行测试
test:
	uv run pytest

# 清理缓存
clean:
	uv cache clean

# 完整环境设置（新人使用）
setup: install
	@echo "环境设置完成！"
	@echo "运行 'make run' 启动项目" 