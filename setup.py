#!/usr/bin/env python3
"""
微信读书到 Notion 同步工具设置脚本

这个脚本帮助用户快速设置配置文件。
"""

import os
import sys
from pathlib import Path


def create_config_file():
    """创建配置文件"""
    config_example = Path("config.example.py")
    config_file = Path("config.py")
    
    if not config_example.exists():
        print("❌ config.example.py 文件不存在！")
        return False
    
    if config_file.exists():
        overwrite = input("⚠️  config.py 已存在，是否覆盖？ (y/N): ").lower().strip()
        if overwrite != 'y':
            print("✅ 保留现有配置文件")
            return True
    
    # 复制配置文件
    with open(config_example, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 配置文件已创建: config.py")
    return True


def interactive_config():
    """交互式配置"""
    print("\n🔧 交互式配置")
    print("=" * 50)
    
    # 读取现有配置
    config_file = Path("config.py")
    if not config_file.exists():
        print("❌ 配置文件不存在，请先运行基本设置")
        return False
    
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 获取微信读书 Cookie
    print("\n📚 微信读书配置")
    print("获取方法：")
    print("1. 打开浏览器，访问 https://weread.qq.com/")
    print("2. 登录你的微信读书账号")
    print("3. 打开开发者工具 (F12)")
    print("4. 在 Network 标签页中刷新页面")
    print("5. 找到任意一个请求，复制 Cookie 值")
    
    weread_cookie = input("\n请输入微信读书 Cookie (留空跳过): ").strip()
    if weread_cookie:
        content = content.replace(
            'WEREAD_COOKIE = "your_weread_cookie_here"',
            f'WEREAD_COOKIE = "{weread_cookie}"'
        )
        print("✅ 微信读书 Cookie 已设置")
    
    # 获取 Notion Token
    print("\n📝 Notion API 配置")
    print("获取方法：")
    print("1. 访问 https://www.notion.so/my-integrations")
    print("2. 点击 'New integration' 创建新的集成")
    print("3. 填写基本信息，获取 Internal Integration Token")
    
    notion_token = input("\n请输入 Notion API Token (留空跳过): ").strip()
    if notion_token:
        content = content.replace(
            'NOTION_TOKEN = "secret_your_notion_integration_token"',
            f'NOTION_TOKEN = "{notion_token}"'
        )
        print("✅ Notion API Token 已设置")
    
    # 获取数据库 ID
    print("\n🗂️  Notion 数据库配置")
    print("获取方法：")
    print("1. 在 Notion 中创建一个数据库页面")
    print("2. 复制页面链接，32位字符串就是数据库 ID")
    print("3. 在数据库页面点击 'Share' 添加你的集成")
    
    database_id = input("\n请输入 Notion 数据库 ID (留空跳过): ").strip()
    if database_id:
        content = content.replace(
            'NOTION_DATABASE_ID = "your_notion_database_id"',
            f'NOTION_DATABASE_ID = "{database_id}"'
        )
        print("✅ Notion 数据库 ID 已设置")
    
    # 保存配置
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n✅ 配置已保存到 config.py")
    return True


def check_dependencies():
    """检查依赖"""
    print("\n📦 检查依赖")
    print("=" * 50)
    
    try:
        import httpx
        print("✅ httpx 已安装")
    except ImportError:
        print("❌ httpx 未安装")
        return False
    
    try:
        import notion_client
        print("✅ notion-client 已安装")
    except ImportError:
        print("❌ notion-client 未安装")
        return False
    
    try:
        import aiolimiter
        print("✅ aiolimiter 已安装")
    except ImportError:
        print("❌ aiolimiter 未安装")
        return False
    
    print("✅ 所有依赖都已安装")
    return True


def main():
    """主函数"""
    print("🚀 微信读书到 Notion 同步工具设置")
    print("=" * 50)
    
    while True:
        print("\n请选择操作：")
        print("1. 创建配置文件")
        print("2. 交互式配置")
        print("3. 检查依赖")
        print("4. 退出")
        
        choice = input("\n请输入选项 (1-4): ").strip()
        
        if choice == '1':
            create_config_file()
        elif choice == '2':
            interactive_config()
        elif choice == '3':
            check_dependencies()
        elif choice == '4':
            print("👋 再见！")
            break
        else:
            print("❌ 无效选项，请重新选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 设置失败: {str(e)}")
        sys.exit(1)