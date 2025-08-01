#!/usr/bin/env python3
"""
微信读书到 Notion 同步工具

这个文件是项目的主入口点，会调用 src/main.py 中的实际逻辑。
"""

import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 导入并运行主逻辑
if __name__ == "__main__":
    from main import main
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序执行失败: {str(e)}")
        sys.exit(1)
