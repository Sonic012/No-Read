import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from notion_client import AsyncClient
from aiolimiter import AsyncLimiter

from ..models import BookInfo, ReadingNote, BookReview


class NotionClient:
    """Notion API 客户端"""
    
    def __init__(self, token: str = None, database_id: str = None, rate_limit: int = 3):
        """
        初始化 Notion 客户端
        
        Args:
            token: Notion API Token
            database_id: 书籍数据库 ID
            rate_limit: 每秒最多请求次数
        """
        self.token = token or self._get_token_from_env()
        self.database_id = database_id or os.getenv('NOTION_DATABASE_ID')
        self.client = AsyncClient(auth=self.token)
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=1)
    
    def _get_token_from_env(self) -> str:
        """从环境变量获取 Notion Token"""
        token = os.getenv('NOTION_TOKEN')
        if not token:
            raise ValueError("请设置 NOTION_TOKEN 环境变量或传入 token 参数")
        return token
    
    # database_id 可选；若缺失可以通过 create_database_if_not_exists 创建
    
    async def create_book_page(self, book_info: BookInfo, notes: List[ReadingNote] = None, reviews: List[BookReview] = None) -> Dict[str, Any]:
        """
        创建书籍页面
        
        Args:
            book_info: 书籍信息
            notes: 读书笔记列表
            reviews: 书评列表
            
        Returns:
            创建的页面信息
        """
        async with self.rate_limiter:
            # 构建页面属性
            properties = {
                "书名": {
                    "title": [
                        {
                            "text": {
                                "content": book_info.title
                            }
                        }
                    ]
                },
                "作者": {
                    "rich_text": [
                        {
                            "text": {
                                "content": book_info.author or ""
                            }
                        }
                    ]
                },
                "书籍ID": {
                    "rich_text": [
                        {
                            "text": {
                                "content": book_info.book_id
                            }
                        }
                    ]
                },
                "分类": {
                    "select": {
                        "name": book_info.category or "未分类"
                    } if book_info.category else None
                },
                "阅读进度": {
                    "number": book_info.read_progress
                } if book_info.read_progress is not None else None,
                "评分": {
                    "number": book_info.rating
                } if book_info.rating is not None else None,
                "完成阅读": {
                    "checkbox": book_info.finish_reading == 1
                } if book_info.finish_reading is not None else None,
                "最后阅读时间": {
                    "date": {
                        "start": book_info.last_read_time.isoformat()
                    }
                } if book_info.last_read_time else None
            }
            
            # 过滤掉 None 值
            properties = {k: v for k, v in properties.items() if v is not None}
            
            # 构建页面内容
            children = []
            
            # 添加书籍封面
            if book_info.cover:
                children.append({
                    "object": "block",
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {
                            "url": book_info.cover
                        }
                    }
                })
            
            # 添加书籍简介
            if book_info.intro:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": "📖 书籍简介"
                                }
                            }
                        ]
                    }
                })
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": book_info.intro
                                }
                            }
                        ]
                    }
                })
            
            # 添加读书笔记
            if notes:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": f"📝 读书笔记 ({len(notes)}条)"
                                }
                            }
                        ]
                    }
                })
                
                # 按章节分组笔记
                notes_by_chapter = {}
                for note in notes:
                    chapter = note.chapter_title or "其他"
                    if chapter not in notes_by_chapter:
                        notes_by_chapter[chapter] = []
                    notes_by_chapter[chapter].append(note)
                
                for chapter, chapter_notes in notes_by_chapter.items():
                    # 章节标题
                    children.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": chapter
                                    }
                                }
                            ]
                        }
                    })
                    
                    # 章节笔记
                    for note in chapter_notes:
                        note_type_emoji = "📝" if note.note_type == "review" else "📖"
                        children.append({
                            "object": "block",
                            "type": "callout",
                            "callout": {
                                "icon": {
                                    "type": "emoji",
                                    "emoji": note_type_emoji
                                },
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": note.content
                                        }
                                    }
                                ]
                            }
                        })
            
            # 添加书评
            if reviews:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": f"💭 我的书评 ({len(reviews)}条)"
                                }
                            }
                        ]
                    }
                })
                
                for review in reviews:
                    children.append({
                        "object": "block",
                        "type": "quote",
                        "quote": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": review.content
                                    }
                                }
                            ]
                        }
                    })
            
            # 创建页面
            response = await self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children
            )
            
            return response
    
    async def find_book_page(self, book_id: str) -> Optional[Dict[str, Any]]:
        """
        根据书籍 ID 查找页面
        
        Args:
            book_id: 书籍 ID
            
        Returns:
            页面信息，如果不存在则返回 None
        """
        async with self.rate_limiter:
            response = await self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "书籍ID",
                    "rich_text": {
                        "equals": book_id
                    }
                }
            )
            
            results = response.get("results", [])
            return results[0] if results else None
    
    async def update_book_page(self, page_id: str, book_info: BookInfo, notes: List[ReadingNote] = None, reviews: List[BookReview] = None) -> Dict[str, Any]:
        """
        更新书籍页面
        
        Args:
            page_id: 页面 ID
            book_info: 书籍信息
            notes: 读书笔记列表
            reviews: 书评列表
            
        Returns:
            更新后的页面信息
        """
        async with self.rate_limiter:
            # 更新页面属性
            properties = {
                "阅读进度": {
                    "number": book_info.read_progress
                } if book_info.read_progress is not None else None,
                "完成阅读": {
                    "checkbox": book_info.finish_reading == 1
                } if book_info.finish_reading is not None else None,
                "最后阅读时间": {
                    "date": {
                        "start": book_info.last_read_time.isoformat()
                    }
                } if book_info.last_read_time else None
            }
            
            # 过滤掉 None 值
            properties = {k: v for k, v in properties.items() if v is not None}
            
            # 更新页面属性
            if properties:
                await self.client.pages.update(
                    page_id=page_id,
                    properties=properties
                )
            
            # 如果有新的笔记或书评，追加到页面内容
            if notes or reviews:
                children = []
                
                # 添加分隔线
                children.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
                
                # 添加更新时间
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": f"🔄 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                },
                                "annotations": {
                                    "color": "gray"
                                }
                            }
                        ]
                    }
                })
                
                # 添加新笔记
                if notes:
                    children.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"📝 新增笔记 ({len(notes)}条)"
                                    }
                                }
                            ]
                        }
                    })
                    
                    for note in notes:
                        note_type_emoji = "📝" if note.note_type == "review" else "📖"
                        children.append({
                            "object": "block",
                            "type": "callout",
                            "callout": {
                                "icon": {
                                    "type": "emoji",
                                    "emoji": note_type_emoji
                                },
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": f"[{note.chapter_title}] {note.content}"
                                        }
                                    }
                                ]
                            }
                        })
                
                # 添加新书评
                if reviews:
                    children.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"💭 新增书评 ({len(reviews)}条)"
                                    }
                                }
                            ]
                        }
                    })
                    
                    for review in reviews:
                        children.append({
                            "object": "block",
                            "type": "quote",
                            "quote": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": review.content
                                        }
                                    }
                                ]
                            }
                        })
                
                # 追加内容到页面
                await self.client.blocks.children.append(
                    block_id=page_id,
                    children=children
                )
            
            # 返回更新后的页面信息
            return await self.client.pages.retrieve(page_id=page_id)
    
    async def list_all_books(self) -> List[Dict[str, Any]]:
        """
        获取数据库中所有书籍页面
        
        Returns:
            书籍页面列表
        """
        async with self.rate_limiter:
            response = await self.client.databases.query(
                database_id=self.database_id
            )
            return response.get("results", [])
    
    async def create_database_if_not_exists(self, parent_page_id: str) -> str:
        """
        创建书籍数据库（如果不存在）
        
        Args:
            parent_page_id: 父页面 ID
            
        Returns:
            数据库 ID
        """
        async with self.rate_limiter:
            database = await self.client.databases.create(
                parent={"page_id": parent_page_id},
                title=[
                    {
                        "type": "text",
                        "text": {
                            "content": "📚 我的书架"
                        }
                    }
                ],
                properties={
                    "书名": {
                        "title": {}
                    },
                    "作者": {
                        "rich_text": {}
                    },
                    "书籍ID": {
                        "rich_text": {}
                    },
                    "分类": {
                        "select": {
                            "options": [
                                {"name": "小说", "color": "blue"},
                                {"name": "非虚构", "color": "green"},
                                {"name": "技术", "color": "orange"},
                                {"name": "历史", "color": "purple"},
                                {"name": "哲学", "color": "red"},
                                {"name": "科学", "color": "yellow"},
                                {"name": "传记", "color": "pink"},
                                {"name": "其他", "color": "gray"}
                            ]
                        }
                    },
                    "阅读进度": {
                        "number": {
                            "format": "percent"
                        }
                    },
                    "评分": {
                        "number": {
                            "format": "number"
                        }
                    },
                    "完成阅读": {
                        "checkbox": {}
                    },
                    "最后阅读时间": {
                        "date": {}
                    }
                }
            )
            return database["id"]