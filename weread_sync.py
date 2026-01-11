#!/usr/bin/env python3.11
"""
微信读书同步到Notion - 简化版
一个文件完成所有同步功能
"""

import requests
import json
import time
from datetime import datetime
from config import WEREAD_COOKIE, NOTION_TOKEN

# Notion配置
NOTION_VERSION = "2022-06-28"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

# 微信读书配置
WEREAD_HEADERS = {
    'Cookie': WEREAD_COOKIE,
    'User-Agent': 'Mozilla/5.0'
}

# 加载Notion数据库ID
with open('/home/ubuntu/notion_db_ids.json', 'r') as f:
    DB_IDS = json.load(f)

BOOKSHELF_DB_ID = DB_IDS['bookshelf_db_id']
AUTHOR_DB_ID = DB_IDS['author_db_id']


def get_weread_data():
    """获取微信读书书架数据"""
    response = requests.get('https://weread.qq.com/web/shelf/sync', headers=WEREAD_HEADERS)
    if response.status_code != 200:
        print(f"❌ 获取书架数据失败: {response.status_code}")
        return None
    
    data = response.json()
    books = data.get('books', [])
    book_progress = data.get('bookProgress', [])
    
    # 创建progress字典方便查找
    progress_dict = {p['bookId']: p for p in book_progress}
    
    return books, progress_dict


def find_notion_page_by_book_id(book_id):
    """根据书籍ID查找Notion页面"""
    url = f"https://api.notion.com/v1/databases/{BOOKSHELF_DB_ID}/query"
    payload = {
        "filter": {
            "property": "书籍ID",
            "rich_text": {
                "equals": book_id
            }
        }
    }
    
    response = requests.post(url, headers=NOTION_HEADERS, json=payload)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]
    return None


def find_or_create_author(author_name):
    """查找或创建作者"""
    if not author_name or author_name == '未知作者':
        return None
    
    # 查找作者
    url = f"https://api.notion.com/v1/databases/{AUTHOR_DB_ID}/query"
    payload = {
        "filter": {
            "property": "作者名",
            "title": {
                "equals": author_name
            }
        }
    }
    
    response = requests.post(url, headers=NOTION_HEADERS, json=payload)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]['id']
    
    # 创建作者
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": AUTHOR_DB_ID},
        "properties": {
            "作者名": {
                "title": [{"text": {"content": author_name}}]
            }
        }
    }
    
    response = requests.post(url, headers=NOTION_HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()['id']
    
    return None


def create_or_update_book(book_data, progress_data):
    """创建或更新书籍"""
    book_id = book_data.get('bookId')
    title = book_data.get('title', '未知书名')
    author = book_data.get('author', '未知作者')
    cover = book_data.get('cover', '')
    
    # 从 progress_data获取正确的阅读数据
    reading_time = progress_data.get('readingTime', 0)
    progress = progress_data.get('progress', 0)
    
    # 格式化阅读时长为文本
    if reading_time > 0:
        hours = reading_time // 3600
        minutes = (reading_time % 3600) // 60
        if hours > 0:
            reading_time_text = f"{hours}小时{minutes}分"
        else:
            reading_time_text = f"{minutes}分钟"
    else:
        reading_time_text = "0分钟"    
    # 获取年份（从更新时间）
    update_time = progress_data.get('updateTime', 0)
    if update_time > 0:
        year = datetime.fromtimestamp(update_time).year
        year_label = f"{year}年"
    else:
        year_label = "未知"
    
    # 查找或创建作者
    author_id = find_or_create_author(author)
    
    # 构建Notion页面属性
    properties = {
        "书名": {
            "title": [{"text": {"content": title}}]
        },
        "书籍ID": {
            "rich_text": [{"text": {"content": book_id}}]
        },
        "阅读时长": {
            "rich_text": [{"text": {"content": reading_time_text}}]
        },
        "阅读进度": {
            "number": progress
        },
        "年份标签": {
            "select": {"name": year_label}
        }
    }
    
    # 添加作者关联
    if author_id:
        properties["作者"] = {
            "relation": [{"id": author_id}]
        }
    
    # 添加封面
    if cover:
        properties["封面"] = {
            "files": [{"name": "封面", "external": {"url": cover}}]
        }
    
    # 查找是否已存在
    existing_page = find_notion_page_by_book_id(book_id)
    
    if existing_page:
        # 更新
        page_id = existing_page['id']
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"properties": properties}
        response = requests.patch(url, headers=NOTION_HEADERS, json=payload)
        
        if response.status_code == 200:
            return "updated", title
        else:
            error_msg = response.text[:200]
            print(f"    更新失败 ({response.status_code}): {error_msg}")
            return "failed", title
    else:
        # 创建
        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": BOOKSHELF_DB_ID},
            "properties": properties
        }
        response = requests.post(url, headers=NOTION_HEADERS, json=payload)
        
        if response.status_code == 200:
            return "created", title
        else:
            error_msg = response.text[:200]
            print(f"    创建失败 ({response.status_code}): {error_msg}")
            return "failed", title


def sync_books(limit=None):
    """同步书籍"""
    print("=" * 70)
    print("微信读书同步到Notion")
    print("=" * 70)
    
    # 获取数据
    print("\n📚 获取微信读书数据...")
    result = get_weread_data()
    if not result:
        return
    
    books, progress_dict = result
    print(f"   找到 {len(books)} 本书籍")
    print(f"   其中 {len(progress_dict)} 本有阅读进度数据")
    
    # 限制数量
    if limit:
        books = books[:limit]
        print(f"   限制同步前 {limit} 本")
    
    print(f"\n🔄 开始同步...\n")
    
    created_count = 0
    updated_count = 0
    failed_count = 0
    
    for i, book in enumerate(books, 1):
        book_id = book.get('bookId')
        progress_data = progress_dict.get(book_id, {})
        
        status, title = create_or_update_book(book, progress_data)
        
        if status == "created":
            print(f"[{i}/{len(books)}] ✅ 新增: {title}")
            created_count += 1
        elif status == "updated":
            print(f"[{i}/{len(books)}] 🔄 更新: {title}")
            updated_count += 1
        else:
            print(f"[{i}/{len(books)}] ❌ 失败: {title}")
            if isinstance(status, tuple) and len(status) > 2:
                print(f"    错误: {status[2]}")
            failed_count += 1
        
        # 延迟避免API限流
        time.sleep(0.35)
    
    print(f"\n" + "=" * 70)
    print(f"✅ 同步完成！")
    print(f"   新增: {created_count}")
    print(f"   更新: {updated_count}")
    print(f"   失败: {failed_count}")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    # 解析命令行参数
    limit = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            limit = None
        elif sys.argv[1].isdigit():
            limit = int(sys.argv[1])
        else:
            print("用法:")
            print("  python3.11 weread_sync.py           # 同步前10本（测试）")
            print("  python3.11 weread_sync.py 50        # 同步前50本")
            print("  python3.11 weread_sync.py --all     # 同步所有书籍")
            sys.exit(1)
    else:
        limit = 10  # 默认同步10本
    
    sync_books(limit)
