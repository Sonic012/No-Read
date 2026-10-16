"""标题文本归一测试。

Notion 标题属性会吞掉结尾的换行与行分隔符（实测 \\u2028 被丢弃）。
不归一的话，以这些字符结尾的划线每次同步都会被判成「已变更」并重写。
"""

from src.notion.template_client import TITLE_LIMIT, _title_text


def test_strips_trailing_line_separators():
    assert _title_text("正文\u2028\n") == "正文"
    assert _title_text("正文\n\n") == "正文"
    assert _title_text("正文\r\n") == "正文"


def test_keeps_inner_line_separators_and_text():
    assert _title_text("第一行\u2028第二行") == "第一行\u2028第二行"
    assert _title_text("  前导空格保留") == "  前导空格保留"


def test_truncates_over_limit_before_stripping():
    long_text = "字" * (TITLE_LIMIT + 50)
    result = _title_text(long_text)

    assert len(result) == TITLE_LIMIT
    assert result.endswith("…")


def test_empty_content_is_safe():
    assert _title_text("") == ""
    assert _title_text(None) == ""
