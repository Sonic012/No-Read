#!/usr/bin/env python3
"""
Configuration injection script for GitHub Actions

This script reads environment variables and injects them into the config.py file.
It handles both secrets (sensitive data) and variables (non-sensitive configuration).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Union

def get_env_value(key: str, default: Any = None) -> Any:
    """Get environment variable value with proper type conversion."""
    value = os.getenv(key, default)
    
    if value is None:
        return default
    
    # Handle boolean values
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    # Handle integer values
    if isinstance(default, int):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Handle float values
    if isinstance(default, float):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    return value

def generate_config_content(env_vars: Dict[str, Any]) -> str:
    """Generate the config.py content with injected environment variables."""
    
    config_template = '''# 项目配置 - 由 GitHub Actions 自动生成
# 此文件由 scripts/inject_config.py 自动生成，请勿手动编辑

# ================================
# 微信读书配置
# ================================
WEREAD_COOKIE = "{weread_cookie}"

# ================================
# Notion API 配置
# ================================
NOTION_TOKEN = "{notion_token}"
NOTION_DATABASE_ID = "{notion_database_id}"
NOTION_PARENT_PAGE_ID = "{notion_parent_page_id}"

# ================================
# 同步配置
# ================================
SYNC_ALL_BOOKS = {sync_all_books}
SYNC_FINISHED_BOOKS = {sync_finished_books}
SYNC_UNFINISHED_BOOKS = {sync_unfinished_books}
SYNC_BOOK_COVERS = {sync_book_covers}
SYNC_BOOK_REVIEWS = {sync_book_reviews}
SYNC_READING_NOTES = {sync_reading_notes}

# 批量同步设置
BATCH_SIZE = {batch_size}
BATCH_DELAY = {batch_delay}

# ================================
# API 限制配置
# ================================
WEREAD_RATE_LIMIT = {weread_rate_limit}
WEREAD_REQUEST_DELAY = {weread_request_delay}
NOTION_RATE_LIMIT = {notion_rate_limit}
NOTION_REQUEST_TIMEOUT = {notion_request_timeout}

# ================================
# 日志配置
# ================================
LOG_LEVEL = "{log_level}"
LOG_FILE = "logs/sync.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_MAX_SIZE = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# ================================
# 高级配置
# ================================
MIN_NOTE_LENGTH = {min_note_length}
EXCLUDE_PRIVATE_NOTES = {exclude_private_notes}
EXCLUDE_EMPTY_BOOKS = {exclude_empty_books}
MAX_RETRIES = {max_retries}
RETRY_DELAY = {retry_delay}
ENABLE_CACHE = {enable_cache}
CACHE_EXPIRE_TIME = {cache_expire_time}
'''
    
    return config_template.format(**env_vars)

def main():
    """Main function to inject configuration from environment variables."""
    
    # Define default values and environment variable mappings
    config_mapping = {
        # Secrets (sensitive data)
        'weread_cookie': ('WEREAD_COOKIE', ''),
        'notion_token': ('NOTION_TOKEN', ''),
        'notion_database_id': ('NOTION_DATABASE_ID', ''),
        'notion_parent_page_id': ('NOTION_PARENT_PAGE_ID', ''),
        
        # Variables (non-sensitive configuration)
        'sync_all_books': ('SYNC_ALL_BOOKS', True),
        'sync_finished_books': ('SYNC_FINISHED_BOOKS', True),
        'sync_unfinished_books': ('SYNC_UNFINISHED_BOOKS', True),
        'sync_book_covers': ('SYNC_BOOK_COVERS', True),
        'sync_book_reviews': ('SYNC_BOOK_REVIEWS', True),
        'sync_reading_notes': ('SYNC_READING_NOTES', True),
        'batch_size': ('BATCH_SIZE', 5),
        'batch_delay': ('BATCH_DELAY', 2),
        'weread_rate_limit': ('WEREAD_RATE_LIMIT', 5),
        'weread_request_delay': ('WEREAD_REQUEST_DELAY', 1),
        'notion_rate_limit': ('NOTION_RATE_LIMIT', 3),
        'notion_request_timeout': ('NOTION_REQUEST_TIMEOUT', 60),
        'log_level': ('LOG_LEVEL', 'INFO'),
        'min_note_length': ('MIN_NOTE_LENGTH', 10),
        'exclude_private_notes': ('EXCLUDE_PRIVATE_NOTES', False),
        'exclude_empty_books': ('EXCLUDE_EMPTY_BOOKS', True),
        'max_retries': ('MAX_RETRIES', 3),
        'retry_delay': ('RETRY_DELAY', 2),
        'enable_cache': ('ENABLE_CACHE', True),
        'cache_expire_time': ('CACHE_EXPIRE_TIME', 3600),
    }
    
    # Read environment variables
    env_vars = {}
    for config_key, (env_key, default_value) in config_mapping.items():
        env_vars[config_key] = get_env_value(env_key, default_value)
    
    # Generate config content
    config_content = generate_config_content(env_vars)
    
    # Write to config.py
    config_path = Path(__file__).parent.parent / 'config.py'
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"✅ Configuration successfully injected to {config_path}")
        
        # Print summary of configured values (without sensitive data)
        print("\n📋 Configuration Summary:")
        print(f"  • Sync all books: {env_vars['sync_all_books']}")
        print(f"  • Sync finished books: {env_vars['sync_finished_books']}")
        print(f"  • Sync unfinished books: {env_vars['sync_unfinished_books']}")
        print(f"  • Batch size: {env_vars['batch_size']}")
        print(f"  • Log level: {env_vars['log_level']}")
        print(f"  • Max retries: {env_vars['max_retries']}")
        
        # Check if required secrets are set
        required_secrets = ['weread_cookie', 'notion_token', 'notion_database_id']
        missing_secrets = [secret for secret in required_secrets if not env_vars[secret]]
        
        if missing_secrets:
            print(f"\n⚠️  Warning: Missing required secrets: {', '.join(missing_secrets)}")
            print("   The sync may fail if these are not properly configured.")
        
    except Exception as e:
        print(f"❌ Error writing configuration file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()