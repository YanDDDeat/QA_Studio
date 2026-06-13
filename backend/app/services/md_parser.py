import re
from pathlib import Path
from typing import List, Dict, Any, Optional


HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')

# ---------------------------------------------------------------------------
# 编号深度推断模式（从深到浅排列，避免前缀误匹配）
# ---------------------------------------------------------------------------
_NUMBERING_PATTERNS = [
    # 四段编号 1.2.3.4（编号后允许空格/行尾/直接接中文标题）
    (re.compile(r'^(\d+\.\d+\.\d+\.\d+)(?:\s|[^\.\d]|$)'), 4),
    # 三段编号 1.2.3
    (re.compile(r'^(\d+\.\d+\.\d+)(?:\s|[^\.\d]|$)'), 3),
    # 两段编号 1.2
    (re.compile(r'^(\d+\.\d+)(?:\s|[^\.\d]|$)'), 2),
    # 单段编号：1-2位数字（排除年份如"2024届"），后面允许空格/行尾/直接接中文标题
    (re.compile(r'^(\d{1,2})(?:\s|[^\.\d]|$)'), 1),
    # 中文：第X章 → depth=1
    (re.compile(r'^第[一二三四五六七八九十百零\d]+章'), 1),
    # 中文：第X节 → depth=2
    (re.compile(r'^第[一二三四五六七八九十百零\d]+节'), 2),
]


def infer_numbering_depth(title_text: str) -> int:
    """从标题文本的编号模式推断层级深度。

    返回值：
      0 = 无编号（封面/元数据）
      1 = 章级（1、第一章）
      2 = 节级（1.1、第二节）
      3 = 小节级（1.2.3）
      4 = 更细层级（1.2.3.1）

    正则从深到浅依次匹配，确保 "1.2.3.4" 不会被 "1.2" 误匹配。
    """
    stripped = title_text.strip()
    if not stripped:
        return 0
    for pattern, depth in _NUMBERING_PATTERNS:
        if pattern.match(stripped):
            return depth
    return 0


def parse_md_file(file_path: Path, split_mode: str, **options) -> List[Dict[str, Any]]:
    """
    Parse a Markdown file and split it into chunks based on the specified mode.

    Args:
        file_path: Path to the Markdown file
        split_mode: 'section' or 'paragraph'
        **options: Additional options for the split mode
            - For 'section': min_title_level (int), max_title_level (int), heading_level (int)
            - For 'paragraph': min_chars (int)

    Returns:
        List of chunks, each containing:
        - text: the chunk content
        - md_file: the source file name
        - Additional metadata depending on split mode:
            * section mode: title, title_level
            * paragraph mode: paragraph_index
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if split_mode == "section":
        heading_level = options.pop("heading_level", None)
        if heading_level is not None:
            return _split_by_heading_level(content, file_path.name, heading_level=heading_level)
        return _split_by_section(content, file_path.name, **options)
    elif split_mode == "paragraph":
        return _split_by_paragraph(content, file_path.name, **options)
    elif split_mode == "numbering":
        depth = options.pop("depth", 1)
        return _split_by_numbering_depth(content, file_path.name, depth=depth)
    else:
        raise ValueError(f"Unknown split mode: {split_mode}")


def scan_md_headings(content: str) -> Dict[str, Any]:
    """
    Scan Markdown ATX headings in content.

    A valid heading starts at the beginning of a line with 1-6 '#', followed by
    at least one whitespace character and then heading text.

    Returns heading info with both markdown level and inferred numbering depth.
    """
    headings = []
    level_counts: Dict[str, int] = {}
    numbering_depth_counts: Dict[str, int] = {}

    for line_no, line in enumerate(content.split('\n'), start=1):
        match = HEADING_PATTERN.match(line)
        if not match:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        inferred_depth = infer_numbering_depth(title)

        headings.append({
            "level": level,
            "title": title,
            "line": line_no,
            "inferred_depth": inferred_depth,
        })
        key = str(level)
        level_counts[key] = level_counts.get(key, 0) + 1
        depth_key = str(inferred_depth)
        numbering_depth_counts[depth_key] = numbering_depth_counts.get(depth_key, 0) + 1

    available_levels = sorted({heading["level"] for heading in headings})
    numbering_available_depths = sorted({heading["inferred_depth"] for heading in headings})
    all_same_md_level = len(headings) > 0 and len(available_levels) == 1

    return {
        "headings": headings,
        "available_levels": available_levels,
        "level_counts": level_counts,
        "numbering_depth_counts": numbering_depth_counts,
        "numbering_available_depths": numbering_available_depths,
        "all_headings_same_md_level": all_same_md_level,
    }


def _split_by_heading_level(content: str, filename: str, heading_level: int) -> List[Dict[str, Any]]:
    """
    Split Markdown content using only the specified heading level as chunk boundary.

    Content before the first heading of the selected level is ignored. Lower-level
    headings and body text are kept inside the current chunk. Higher-level headings
    between two selected-level headings are also kept inside the current chunk.
    """
    if not 1 <= heading_level <= 6:
        raise ValueError("heading_level must be between 1 and 6")

    chunks = []
    current_section: List[str] = []
    current_title: Optional[str] = None

    for line in content.split('\n'):
        match = HEADING_PATTERN.match(line)
        is_boundary = bool(match and len(match.group(1)) == heading_level)

        if is_boundary:
            if current_section and current_title is not None:
                text = '\n'.join(current_section).strip()
                if text:
                    chunks.append({
                        "text": text,
                        "title": current_title,
                        "title_level": heading_level,
                        "md_file": filename,
                    })

            current_section = [line]
            current_title = match.group(2).strip()
            continue

        if current_title is not None:
            current_section.append(line)

    if current_section and current_title is not None:
        text = '\n'.join(current_section).strip()
        if text:
            chunks.append({
                "text": text,
                "title": current_title,
                "title_level": heading_level,
                "md_file": filename,
            })

    return chunks


def _split_by_numbering_depth(content: str, filename: str, depth: int = 1) -> List[Dict[str, Any]]:
    """
    Split Markdown content by inferred numbering depth.

    Uses infer_numbering_depth() to detect the real hierarchy from title text
    numbering patterns (e.g. "1绪论" → depth=1, "1.1研究目的" → depth=2).

    Headings with inferred_depth == depth serve as chunk boundaries.
    Headings with inferred_depth == 0 (no numbering) are not boundaries;
    their content is accumulated and attached to the first numbered chunk
    (or discarded if no numbered chunk follows).

    Args:
        content: Markdown full text
        filename: Source file name
        depth: Numbering depth boundary (1=chapter, 2=section, 3=subsection, 4=finer)

    Returns:
        List of chunks with title, title_level (inferred depth), text, md_file.
    """
    chunks = []
    current_section: List[str] = []
    current_title: Optional[str] = None
    current_depth: Optional[int] = None

    # Buffer for preamble (depth=0 content before first boundary)
    preamble: List[str] = []

    for line in content.split('\n'):
        match = HEADING_PATTERN.match(line)
        if match:
            title = match.group(2).strip()
            inferred = infer_numbering_depth(title)

            if inferred == depth:
                # This is a boundary heading
                if current_section and current_title is not None and current_depth is not None:
                    text = '\n'.join(current_section).strip()
                    if text:
                        chunks.append({
                            "text": text,
                            "title": current_title,
                            "title_level": current_depth,
                            "md_file": filename,
                        })
                # Attach preamble to first numbered chunk
                if preamble and not chunks:
                    current_section = preamble + [line]
                    preamble = []
                else:
                    current_section = [line]
                current_title = title
                current_depth = inferred
                continue
            else:
                # Non-boundary heading: its content belongs to current chunk
                if current_title is not None:
                    current_section.append(line)
                else:
                    # Preamble area (before first boundary)
                    preamble.append(line)
                continue

        # Non-heading lines
        if current_title is not None:
            current_section.append(line)
        else:
            preamble.append(line)

    # Last chunk
    if current_section and current_title is not None and current_depth is not None:
        text = '\n'.join(current_section).strip()
        if text:
            chunks.append({
                "text": text,
                "title": current_title,
                "title_level": current_depth,
                "md_file": filename,
            })

    return chunks


def _split_by_section(content: str, filename: str, min_title_level: int = 1, max_title_level: int = 6) -> List[Dict[str, Any]]:
    """
    Split Markdown content by section headers (# through ######).

    Args:
        content: Markdown content
        filename: Source file name
        min_title_level: Minimum title level to include (1-6)
        max_title_level: Maximum title level to include (1-6)

    Returns:
        List of section chunks
    """
    # Pattern to match Markdown headers: # through ######
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    chunks = []
    lines = content.split('\n')

    current_section = []
    current_title = None
    current_level = None

    for line in lines:
        match = header_pattern.match(line)
        if match:
            # If we have a current section, save it
            if current_section and current_title is not None and current_level is not None:
                # Check if this section's level is within the range
                if min_title_level <= current_level <= max_title_level:
                    chunks.append({
                        "text": '\n'.join(current_section).strip(),
                        "title": current_title,
                        "title_level": current_level,
                        "md_file": filename
                    })

            # Start new section
            level = len(match.group(1))
            title = match.group(2).strip()

            # Only start tracking if within range, otherwise just continue without tracking
            if min_title_level <= level <= max_title_level:
                current_section = [line]
                current_title = title
                current_level = level
            else:
                current_section = []
                current_title = None
                current_level = None
        else:
            # Add line to current section if we're tracking one
            if current_title is not None:
                current_section.append(line)

    # Don't forget the last section
    if current_section and current_title is not None and current_level is not None:
        if min_title_level <= current_level <= max_title_level:
            chunks.append({
                "text": '\n'.join(current_section).strip(),
                "title": current_title,
                "title_level": current_level,
                "md_file": filename
            })

    return chunks


def _split_by_paragraph(content: str, filename: str, min_chars: int) -> List[Dict[str, Any]]:
    """
    Split Markdown content by paragraphs (empty lines) with minimum character threshold.

    Args:
        content: Markdown content
        filename: Source file name
        min_chars: Minimum character count for a paragraph

    Returns:
        List of paragraph chunks
    """
    # Split by one or more empty lines
    raw_paragraphs = re.split(r'\n\s*\n+', content)

    # Clean up paragraphs: remove leading/trailing whitespace
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    if not paragraphs:
        return []

    # Merge short paragraphs with adjacent ones
    merged = []
    i = 0
    while i < len(paragraphs):
        current = paragraphs[i]

        # If current paragraph is too short, try to merge
        if len(current) < min_chars and i < len(paragraphs) - 1:
            # Try merging with next paragraph
            merged_with_next = current + '\n\n' + paragraphs[i + 1]
            if len(merged_with_next) >= min_chars:
                merged.append(merged_with_next)
                i += 2
                continue

        # If still too short and not first paragraph, try merging with previous
        if len(current) < min_chars and merged:
            merged[-1] = merged[-1] + '\n\n' + current
            i += 1
            continue

        # Otherwise, add as is
        merged.append(current)
        i += 1

    # Convert to chunks
    chunks = []
    for idx, para in enumerate(merged):
        chunks.append({
            "text": para,
            "paragraph_index": idx,
            "md_file": filename
        })

    return chunks
