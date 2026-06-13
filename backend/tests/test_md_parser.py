import pathlib
import sys

_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.md_parser import scan_md_headings, _split_by_heading_level  # noqa: E402


def test_scan_md_headings_returns_levels_counts_and_lines():
    content = "\n".join([
        "# 第一章",
        "#不是标题",
        "正文",
        "## 1.1 背景",
        "### 子节",
        "####### 七级不识别",
        "## 1.2 方法",
    ])

    result = scan_md_headings(content)

    assert result["headings"] == [
        {"level": 1, "title": "第一章", "line": 1},
        {"level": 2, "title": "1.1 背景", "line": 4},
        {"level": 3, "title": "子节", "line": 5},
        {"level": 2, "title": "1.2 方法", "line": 7},
    ]
    assert result["available_levels"] == [1, 2, 3]
    assert result["level_counts"] == {"1": 1, "2": 2, "3": 1}


def test_split_by_heading_level_uses_only_selected_level_as_boundary():
    content = "\n".join([
        "# 第一章",
        "章简介不应单独成块",
        "## 1.1 背景",
        "正文 A",
        "### 1.1.1 子节",
        "正文 B",
        "# 夹在中间的一级标题",
        "仍属于 1.1",
        "## 1.2 方法",
        "正文 C",
    ])

    chunks = _split_by_heading_level(content, "demo.md", heading_level=2)

    assert [chunk["title"] for chunk in chunks] == ["1.1 背景", "1.2 方法"]
    assert chunks[0]["text"] == "\n".join([
        "## 1.1 背景",
        "正文 A",
        "### 1.1.1 子节",
        "正文 B",
        "# 夹在中间的一级标题",
        "仍属于 1.1",
    ])
    assert chunks[1]["text"] == "## 1.2 方法\n正文 C"
    assert chunks[0]["title_level"] == 2


def test_split_by_heading_level_returns_empty_when_selected_level_missing():
    content = "# 第一章\n正文\n### 子节\n正文"

    assert _split_by_heading_level(content, "demo.md", heading_level=2) == []
