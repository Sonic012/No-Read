"""页面正文分块写入的纯逻辑测试（不访问 Notion）。"""

from src.notion.template_client import (
    BODY_CHUNK_LIMIT,
    TITLE_LIMIT,
    _body_chunks,
    _batched,
    _clip_text,
    _is_managed_body,
    _simple_paragraph_text,
)


def _paragraph(text):
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def test_body_chunks_splits_within_notion_limit():
    chunks = _body_chunks("长" * (BODY_CHUNK_LIMIT * 2 + 10))
    assert [len(chunk) for chunk in chunks] == [BODY_CHUNK_LIMIT, BODY_CHUNK_LIMIT, 10]
    assert all(len(chunk) <= 2000 for chunk in chunks)


def test_body_chunks_roundtrip_preserves_every_character():
    content = "".join(str(index % 10) for index in range(4321))
    assert "".join(_body_chunks(content)) == content


def test_body_chunks_empty_for_short_content():
    assert _body_chunks("短内容") == []
    assert _body_chunks(None) == []
    assert _body_chunks("x" * TITLE_LIMIT) == []


def test_batched_respects_batch_size():
    assert [len(batch) for batch in _batched([str(i) for i in range(250)], 100)] == [100, 100, 50]


def test_clip_text_keeps_title_within_limit():
    clipped = _clip_text("y" * 5000)
    assert len(clipped) <= TITLE_LIMIT
    assert clipped.endswith("…")


def test_simple_paragraph_text_rejects_user_structures():
    assert _simple_paragraph_text(_paragraph("正文")) == "正文"
    assert _simple_paragraph_text({"type": "heading_1", "heading_1": {}}) is None
    assert _simple_paragraph_text({"type": "paragraph", "paragraph": {"rich_text": []}}) is None
    assert _simple_paragraph_text({"type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "href": "https://example.com", "text": {"content": "链接"}}
    ]}}) is None


def test_is_managed_body_only_true_for_our_chunks():
    long_chunks = _body_chunks("z" * (BODY_CHUNK_LIMIT + 5))
    assert _is_managed_body([_paragraph(chunk) for chunk in long_chunks]) is True
    assert _is_managed_body([]) is False
    assert _is_managed_body([_paragraph("用户手写的一段话")]) is False
    assert _is_managed_body([_paragraph("a"), _paragraph("b"), _paragraph("c")]) is False
