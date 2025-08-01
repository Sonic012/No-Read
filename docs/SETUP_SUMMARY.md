# GitHub Actions 配置总结

## 🎯 配置完成

已成功为微信读书到 Notion 同步工具配置了完整的 GitHub Actions 工作流系统。

## 📁 创建的文件

### 1. GitHub Actions 工作流
- `.github/workflows/sync.yml` - 主同步工作流
- `.github/workflows/test.yml` - 配置测试工作流

### 2. 配置脚本
- `scripts/inject_config.py` - 环境变量注入脚本
- `scripts/test_config.py` - 配置测试脚本

### 3. 文档
- `docs/GITHUB_SETUP.md` - 详细的配置指南
- `docs/SETUP_SUMMARY.md` - 本总结文档

## 🔧 工作流功能

### 主同步工作流 (sync.yml)

**触发条件：**
- 手动触发 (workflow_dispatch)
- 每日自动运行 (cron: '0 2 * * *')
- 代码推送时触发 (push to main/master)

**执行步骤：**
1. 检出代码
2. 设置 Python 环境
3. 安装依赖
4. 创建日志目录
5. 注入配置（从环境变量）
6. 运行同步程序
7. 上传日志文件

### 测试工作流 (test.yml)

**触发条件：**
- 手动触发
- Pull Request 时触发

**功能：**
- 测试配置注入
- 验证配置文件
- 检查环境变量

## 🔐 环境变量配置

### Secrets (敏感信息)
- `WEREAD_COOKIE` - 微信读书 Cookie
- `NOTION_TOKEN` - Notion API Token
- `NOTION_DATABASE_ID` - Notion 数据库 ID
- `NOTION_PARENT_PAGE_ID` - Notion 父页面 ID (可选)

### Variables (配置参数)
- `SYNC_ALL_BOOKS` - 是否同步所有书籍
- `SYNC_FINISHED_BOOKS` - 是否同步已读完的书籍
- `SYNC_UNFINISHED_BOOKS` - 是否同步未读完的书籍
- `SYNC_BOOK_COVERS` - 是否同步书籍封面
- `SYNC_BOOK_REVIEWS` - 是否同步书评
- `SYNC_READING_NOTES` - 是否同步读书笔记
- `BATCH_SIZE` - 每批次同步的书籍数量
- `BATCH_DELAY` - 批次之间的延迟
- `WEREAD_RATE_LIMIT` - 微信读书 API 限制
- `WEREAD_REQUEST_DELAY` - 请求之间的延迟
- `NOTION_RATE_LIMIT` - Notion API 限制
- `NOTION_REQUEST_TIMEOUT` - 请求超时时间
- `LOG_LEVEL` - 日志级别
- `MIN_NOTE_LENGTH` - 最小笔记长度
- `EXCLUDE_PRIVATE_NOTES` - 是否排除私有笔记
- `EXCLUDE_EMPTY_BOOKS` - 是否排除空书籍
- `MAX_RETRIES` - 最大重试次数
- `RETRY_DELAY` - 重试延迟
- `ENABLE_CACHE` - 是否启用缓存
- `CACHE_EXPIRE_TIME` - 缓存过期时间

## 🚀 使用方法

### 1. 设置环境变量
1. 进入 GitHub 仓库 → Settings → Secrets and variables → Actions
2. 添加必需的 Secrets
3. 可选：添加 Variables 来自定义行为

### 2. 运行工作流
1. 进入 Actions 标签页
2. 选择 "Sync WeChat Reading to Notion"
3. 点击 "Run workflow"

### 3. 查看结果
1. 查看工作流运行日志
2. 下载同步日志文件
3. 检查 Notion 数据库

## 🧪 测试功能

### 本地测试
```bash
# 设置环境变量
export WEREAD_COOKIE="your_cookie"
export NOTION_TOKEN="your_token"
export NOTION_DATABASE_ID="your_database_id"

# 运行测试
python scripts/test_config.py
```

### GitHub Actions 测试
1. 进入 Actions 标签页
2. 选择 "Test Configuration"
3. 点击 "Run workflow"

## 📊 监控和日志

### 日志文件
- 工作流运行日志：GitHub Actions 界面
- 同步详细日志：下载 `sync-logs` 工件
- 本地日志：`logs/sync.log`

### 监控指标
- 同步成功率
- 处理书籍数量
- API 请求次数
- 错误类型和频率

## 🔒 安全特性

1. **敏感信息保护**：Secrets 在日志中自动隐藏
2. **权限控制**：只给 Notion 集成必要权限
3. **配置验证**：测试脚本验证配置正确性
4. **错误处理**：完善的错误处理和重试机制

## 📈 性能优化

1. **批量处理**：可配置批量大小和延迟
2. **API 限制**：可调整请求频率限制
3. **缓存机制**：支持启用缓存减少重复请求
4. **异步处理**：使用异步 I/O 提高效率

## 🛠️ 故障排除

### 常见问题
1. **配置注入失败**：检查环境变量名称和格式
2. **认证失败**：确认 Cookie 和 Token 有效性
3. **API 限制**：调整请求频率设置
4. **网络问题**：检查 GitHub Actions 网络连接

### 调试技巧
1. 启用详细日志：设置 `LOG_LEVEL=DEBUG`
2. 减少批量大小：设置 `BATCH_SIZE=1`
3. 增加延迟：设置 `BATCH_DELAY=5`
4. 查看详细错误：下载日志文件

## 📚 相关文档

- [GitHub Actions 配置指南](GITHUB_SETUP.md)
- [项目 README](../../README.md)
- [配置示例](../../config.example.py)

## 🎉 总结

通过这个配置，用户可以：

1. **自动化同步**：每天自动同步微信读书数据到 Notion
2. **安全存储**：敏感信息安全存储在 GitHub Secrets 中
3. **灵活配置**：通过 Variables 自定义同步行为
4. **监控和调试**：完整的日志和测试功能
5. **易于维护**：清晰的工作流结构和文档

这个配置为微信读书到 Notion 同步工具提供了完整的 CI/CD 解决方案，使用户可以轻松实现自动化数据同步。