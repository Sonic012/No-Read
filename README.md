# No-Read 项目

这是一个基于 Playwright 的爬虫项目，使用 uv 进行依赖管理。

## 环境要求

- Python 3.12+
- uv (Python 包管理器)

## 快速开始

### 1. 安装 uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**或者使用 pip:**
```bash
pip install uv
```

### 2. 克隆项目
```bash
git clone <你的仓库地址>
cd No-Read
```

### 3. 安装依赖
```bash
# uv 会自动创建虚拟环境并安装所有依赖
uv sync
```

### 4. 安装 Playwright 浏览器
```bash
uv run playwright install
```

### 5. 运行项目
```bash
# 运行主程序
uv run python src/main.py

# 或者运行特定脚本
uv run python your_script.py
```

## 开发指南

### 添加新依赖
```bash
# 添加生产依赖
uv add package_name

# 添加开发依赖
uv add --dev package_name
```

### 查看依赖
```bash
# 查看依赖树
uv tree

# 查看特定包信息
uv show package_name
```

### 更新依赖
```bash
uv sync
```

## 项目结构

```
No-Read/
├── src/                    # 源代码
│   ├── main.py            # 主入口
│   ├── notion/            # Notion 相关
│   ├── sync/              # 同步逻辑
│   └── wechat_reader/     # 微信读书相关
├── tests/                 # 测试文件
├── pyproject.toml         # 项目配置和依赖
├── uv.lock               # 锁定文件（不要手动修改）
└── README.md             # 项目说明
```

## 常见问题

### Q: 如何激活虚拟环境？
A: 使用 uv 不需要手动激活虚拟环境，直接用 `uv run` 即可。

### Q: 如何查看当前 Python 版本？
A: 运行 `uv run python --version`

### Q: 依赖安装失败怎么办？
A: 尝试清理缓存：`uv cache clean`，然后重新运行 `uv sync`

### Q: 如何导出 requirements.txt？
A: 运行 `uv export --format requirements-txt > requirements.txt`

## 许可证

[你的许可证信息]
