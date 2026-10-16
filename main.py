#!/usr/bin/env python3
"""
微信读书到 Notion 同步工具（入口）。

实际逻辑在 src/main.py。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ 程序执行失败: {exc}")
        sys.exit(1)
