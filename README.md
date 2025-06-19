# 微信读书同步到Notion

## 项目简介
本项目旨在将微信读书个人账号中的书架、在读书籍、书籍评论、划线内容和个人笔记等信息自动同步到Notion笔记中，方便知识管理与归档。

## 主要功能
- 同步微信读书书架书单到Notion
- 同步当前在读书籍信息到Notion
- 同步书籍评论到Notion
- 同步划线内容和个人笔记到Notion

## 技术栈
- Python 3.8+
- [Playwright](https://playwright.dev/python/)（用于自动化登录和数据抓取）
- [aiohttp](https://docs.aiohttp.org/)（用于异步HTTP请求）
- [Notion API](https://developers.notion.com/)（用于数据写入Notion）
- pytest（测试驱动开发）

## 目录结构
```
No-Read/
├── src/                # 核心代码
│   ├── wechat_reader/  # 微信读书相关逻辑
│   ├── notion/         # Notion API相关逻辑
│   └── sync/           # 同步流程与调度
├── tests/              # 测试用例
├── README.md           # 项目说明
├── requirements.txt    # 依赖列表
└── .env.example        # 环境变量示例
```

## 开发模式
本项目采用测试驱动开发（TDD），即先编写测试用例，再实现功能代码。

## 使用方法
1. 克隆本项目：
   ```bash
   git clone https://github.com/yourname/No-Read.git
   cd No-Read
   ```
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 配置环境变量（参考.env.example）
4. 运行测试：
   ```bash
   pytest
   ```
5. 启动同步脚本：
   ```bash
   python src/main.py
   ```

## 贡献指南
欢迎提交PR和Issue，完善功能和修复bug。

## License
MIT
