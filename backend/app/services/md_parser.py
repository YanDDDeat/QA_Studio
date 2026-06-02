import re
from pathlib import Path
from typing import List, Dict, Any, Optional


HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')


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
    else:
        raise ValueError(f"Unknown split mode: {split_mode}")


def scan_md_headings(content: str) -> Dict[str, Any]:
    """
    Scan Markdown ATX headings in content.

    A valid heading starts at the beginning of a line with 1-6 '#', followed by
    at least one whitespace character and then heading text.
    """
    headings = []
    level_counts: Dict[str, int] = {}

    for line_no, line in enumerate(content.split('\n'), start=1):
        match = HEADING_PATTERN.match(line)
        if not match:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append({
            "level": level,
            "title": title,
            "line": line_no,
        })
        key = str(level)
        level_counts[key] = level_counts.get(key, 0) + 1

    available_levels = sorted({heading["level"] for heading in headings})
    return {
        "headings": headings,
        "available_levels": available_levels,
        "level_counts": level_counts,
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
