"""问题生成前文本预处理 —— 纯函数模块

在 question_generate 阶段调 LLM 之前，对原始 chunks 做：
  1. 清洗：剥离图片链接、md 表格分隔线、页眉页脚、折叠空行
  2. 过滤：识别目录 / 参考文献 / 图片堆 / 表格残骸 / 低自然语言
  3. 合并：对过短 chunk 按顺序向后吸收邻居直到达到阈值

设计原则：
- 纯函数，零数据库依赖，零 IO（除标准库）
- 确定性输出：同样输入永远得到同样输出，便于断点恢复
- 阈值全部写为模块级常量，便于未来调整

公开接口仅 ``preprocess_chunks``，其余函数视为内部实现。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 默认阈值常量(可通过 monkey-patch 用于测试)
# ---------------------------------------------------------------------------

MIN_TOKEN_THRESHOLD = 100           # too_short 触发合并阈值
SHORT_LINE_LEN = 30                 # 行长 < 此值算"短行"
TOC_SHORT_LINE_RATIO = 0.70         # 短行占比 > 此值判定为目录(配合 TOC 模式)
TOC_PATTERN_RATIO = 0.30            # TOC 模式行占比 > 此值即判定为目录
REFERENCES_LINE_RATIO = 0.30        # 参考文献行占比 > 此值判定
IMAGE_CHAR_RATIO = 0.50             # 图片链接占字符比例 > 此值
LOW_ALPHA_RATIO = 0.60              # 自然语言占比 < 此值判定低质
TABLE_CHAR_RATIO = 0.50             # 表格行占字符比例 > 此值
HEADER_FOOTER_MIN_FREQ = 0.30       # 行重复出现率 > 此值视为页眉页脚
HEADER_FOOTER_MAX_LEN = 40          # 仅短行参与页眉页脚识别
HEADER_FOOTER_MIN_COUNT = 3         # 至少在 N 条 chunk 中重复出现(避免小样本误伤)
MERGE_SEPARATOR = "\n\n"            # 合并 chunk 时使用的分隔符


# ---------------------------------------------------------------------------
# 正则模式(模块级编译一次)
# ---------------------------------------------------------------------------

# 图片链接 ![alt](url)
_IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\([^\)]+\)')
# 独立 URL 行(整行只有 URL,允许首尾空白)
_URL_LINE_PATTERN = re.compile(r'^\s*https?://\S+\s*$', re.MULTILINE)
# md 表格分隔线 |---|:---:|---|
_TABLE_SEP_PATTERN = re.compile(r'^\s*\|[\s\-:|]+\|\s*$', re.MULTILINE)
# 行首参考文献 [1] He K, ...
_REF_LINE_PATTERN = re.compile(r'^\s*\[\d+\]\s')
# 章节目录:章/节标题
_TOC_CHAPTER_PATTERN = re.compile(r'^\s*第[一二三四五六七八九十百千\d]+[章节]')
# 章节目录:数字小节(如 1.1 / 2.3.4)
_TOC_SECTION_PATTERN = re.compile(r'^\s*\d+\.\d+\s')
# 章节目录:中文数字编号开头(如 一、 / 二、 / 十、)
_TOC_CN_NUM_PATTERN = re.compile(r'^\s*[一二三四五六七八九十百千]+[、\.]')
# 点引导 + 页码(章节目录的尾巴)
_TOC_DOT_LEADER_PATTERN = re.compile(r'[\.\s]{3,}\d+\s*$')
# 任何"行尾点引导+页码"(独立检测,即使没有章节号也能命中目录)
_DOT_LEADER_TAIL_PATTERN = re.compile(r'\.{3,}\s*\d+\s*$')
# 括号页码 (123) 或 （123）(行内或行尾均可)
_TOC_PAREN_PAGE_PATTERN = re.compile(r'[\(（]\d{1,4}[\)）]')
# 中文字符范围(CJK Unified Ideographs U+4E00..U+9FFF)
_CN_LO = '一'
_CN_HI = '鿿'
# 英文词
_ENGLISH_WORD_PATTERN = re.compile(r'[a-zA-Z]+')
# DOI / 期刊缩写常见关键词(用于参考文献辅助判定)
_REF_KEYWORD_PATTERN = re.compile(
    r'\b(?:doi|DOI|et\s+al\.?|vol\.?|pp\.?|no\.?|pp\s*\d+|ISBN|ISSN|arxiv)\b',
    re.IGNORECASE,
)
# 表格数据行(以 | 开头并以 | 结尾)
_TABLE_ROW_PATTERN = re.compile(r'^\s*\|.*\|\s*$')


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class ProcessedChunk:
    """实际送 LLM 的 chunk(已清洗 / 已合并)。"""

    text: str                          # 清洗+合并后的最终文本
    source: str                        # 来源(沿用原 record 的 source)
    source_id: str                     # 来源 ID(合并时取第一个被合并的)
    merged_from: Optional[list]        # 合并的原始 index 列表;单条则为 None
    original_record: dict              # 原始 record(供主循环继续读 source/source_id 等字段)


@dataclass
class SkippedChunk:
    """被预处理过滤掉或被合并吸收的 chunk。"""

    original_index: int                # 原始 JSON 中的下标
    text: str                          # 原始文本(未清洗,方便审查)
    skip_reason: str                   # 见 _SKIP_REASONS


@dataclass
class PreprocessStats:
    """预处理统计信息,供任务日志与过滤文件使用。"""

    original_count: int                                  # 原始 chunk 数
    kept_count: int                                      # 保留数(含合并产生的)
    kept_by_merge_count: int                             # 其中由合并产生的数量
    skipped_count: int                                   # 跳过总数(含 merged)
    skip_breakdown: dict                                 # 按 reason 分类的数量
    skipped_records: list                                # 跳过明细(SkippedChunk)
    header_footer_blacklist: list = field(default_factory=list)  # 识别出的页眉页脚


# 7 类 + 已合并 标记("已合并"是合并产物,统计时一并展示)
_SKIP_REASONS = frozenset({
    "内容为空",
    "目录",
    "参考文献",
    "图片为主",
    "表格残骸",
    "低自然语言",
    "末尾过短",
    "已合并",
})


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def preprocess_chunks(
    raw_records: list,
    text_field: str,
) -> "tuple[list[ProcessedChunk], PreprocessStats]":
    """对原始 chunks 做清洗 + 过滤 + 合并。

    Args:
        raw_records: 上传 JSON 解析后的原始记录列表(每条通常是 dict)
        text_field: 取文本的字段名(如 "text")

    Returns:
        processed_chunks: 实际要送 LLM 的 chunk 列表
        stats: 统计信息(保留/跳过分布、跳过明细)
    """
    original_count = len(raw_records)

    # ── 步骤 1:抽取原始文本 ──
    texts = [_extract_text(r, text_field) for r in raw_records]

    # ── 步骤 2:预扫描页眉页脚 ──
    blacklist = detect_headers_footers(texts)

    # ── 步骤 3:逐条清洗 + 分类 ──
    # processed_items[i] = (cleaned_text, skip_reason_or_None)
    processed_items: "list[tuple[str, Optional[str]]]" = []
    for text in texts:
        if not text:
            processed_items.append(("", "内容为空"))
            continue
        cleaned = clean_text(text, blacklist)
        reason = classify(cleaned, raw=text)
        processed_items.append((cleaned, reason))

    # ── 步骤 4:合并 too_short + 收集跳过 ──
    final_chunks: "list[ProcessedChunk]" = []
    skipped: "list[SkippedChunk]" = []
    kept_by_merge = 0

    i = 0
    while i < len(processed_items):
        text, reason = processed_items[i]

        if reason is None:
            tokens = estimate_tokens(text)
            if tokens >= MIN_TOKEN_THRESHOLD:
                # 达标,直接通过
                final_chunks.append(
                    _make_chunk(text, raw_records[i], merged_from=None)
                )
                i += 1
                continue

            # 触发合并:向后吸收(同 source、reason 为 None)
            merged_text, merged_indices, end = merge_forward(
                processed_items, raw_records, i
            )
            if estimate_tokens(merged_text) >= MIN_TOKEN_THRESHOLD:
                final_chunks.append(
                    _make_chunk(
                        merged_text,
                        raw_records[i],
                        merged_from=merged_indices,
                    )
                )
                if len(merged_indices) > 1:
                    kept_by_merge += 1
                # 被吸收的(merged_indices[1:])标记为 merged
                for idx in merged_indices[1:]:
                    skipped.append(
                        SkippedChunk(idx, texts[idx], "已合并")
                    )
                i = end
            else:
                # 末尾孤儿:无法吸收到足够 token
                skipped.append(
                    SkippedChunk(i, texts[i], "末尾过短")
                )
                # 即使没达标,仍要前进到 end(避免单条无限循环)
                # merge_forward 至少返回 i+1;若 end>i+1 说明吸收了但仍不足,
                # 这些被吸收的也算被丢弃 → 全部记为 末尾过短
                for idx in merged_indices[1:]:
                    skipped.append(
                        SkippedChunk(idx, texts[idx], "末尾过短")
                    )
                i = end
        else:
            skipped.append(SkippedChunk(i, texts[i], reason))
            i += 1

    # 跳过记录按原始 index 升序排列,方便用户审查
    skipped.sort(key=lambda s: s.original_index)

    # 统计分布
    breakdown: dict = {}
    for s in skipped:
        breakdown[s.skip_reason] = breakdown.get(s.skip_reason, 0) + 1

    stats = PreprocessStats(
        original_count=original_count,
        kept_count=len(final_chunks),
        kept_by_merge_count=kept_by_merge,
        skipped_count=len(skipped),
        skip_breakdown=breakdown,
        skipped_records=skipped,
        header_footer_blacklist=list(blacklist),
    )
    return final_chunks, stats


# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """粗估 token 数,针对 qwen 类 tokenizer。

    公式:中文字数 × 1.5 + 英文单词数 × 1.3 + 其他字符 × 0.5
    """
    if not text:
        return 0
    chinese = sum(1 for c in text if _CN_LO <= c <= _CN_HI)
    english_words = _ENGLISH_WORD_PATTERN.findall(text)
    english_word_count = len(english_words)
    english_char_count = sum(len(w) for w in english_words)
    other = max(0, len(text) - chinese - english_char_count)
    return int(chinese * 1.5 + english_word_count * 1.3 + other * 0.5)


# ---------------------------------------------------------------------------
# 页眉页脚识别
# ---------------------------------------------------------------------------


def detect_headers_footers(texts: "list[str]") -> "list[str]":
    """统计所有 chunk 中的短行(<= HEADER_FOOTER_MAX_LEN 字)出现频率,
    出现率 > HEADER_FOOTER_MIN_FREQ 的行视为页眉/页脚,加入黑名单。

    同一 chunk 内的同行只算一次(避免局部重复影响判定)。
    """
    line_counter: Counter = Counter()
    total = max(len(texts), 1)
    for text in texts:
        if not text:
            continue
        seen_in_this_chunk = set()
        for line in text.splitlines():
            stripped = line.strip()
            if 0 < len(stripped) <= HEADER_FOOTER_MAX_LEN and stripped not in seen_in_this_chunk:
                line_counter[stripped] += 1
                seen_in_this_chunk.add(stripped)
    return [
        line for line, count in line_counter.items()
        if count >= HEADER_FOOTER_MIN_COUNT
        and count / total >= HEADER_FOOTER_MIN_FREQ
    ]


# ---------------------------------------------------------------------------
# 文本清洗
# ---------------------------------------------------------------------------


def clean_text(text: str, header_footer_blacklist: "list[str]") -> str:
    """按顺序执行:
    1. 剥离图片链接 ![alt](url)
    2. 剥离独立 URL 行
    3. 剥离 md 表格分隔线 |---|---|
    4. 剥离命中黑名单的整行
    5. 折叠 3+ 空行为 2 空行
    """
    if not text:
        return ""

    # 1. 图片链接
    text = _IMAGE_PATTERN.sub("", text)
    # 2. 独立 URL 行
    text = _URL_LINE_PATTERN.sub("", text)
    # 3. md 表格分隔线(整行)
    text = _TABLE_SEP_PATTERN.sub("", text)

    # 4. 命中黑名单的整行 — 逐行过滤
    if header_footer_blacklist:
        blacklist_set = set(header_footer_blacklist)
        kept_lines = []
        for line in text.splitlines():
            if line.strip() in blacklist_set:
                continue
            kept_lines.append(line)
        text = "\n".join(kept_lines)

    # 5. 折叠 3+ 空行 → 2 空行(保留段落分隔)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# ---------------------------------------------------------------------------
# 分类
# ---------------------------------------------------------------------------


def classify(cleaned: str, raw: str) -> Optional[str]:
    """按优先级判定 skip_reason,命中即返回;
    都不命中且不 too_short 时返回 None(留给步骤 4 决定合并或保留)。

    优先级:
      1. toc           目录页
      2. references    参考文献
      3. image_only    图片为主
      4. table_residue 表格残骸
      5. low_alpha     低自然语言

    too_short 不在此处判定 — 由步骤 4 通过 estimate_tokens 处理。
    """
    # 0. 清洗后全空 → 看 raw 形态判定
    if not cleaned or not cleaned.strip():
        if _image_char_ratio(raw) > IMAGE_CHAR_RATIO:
            return "图片为主"
        if _table_char_ratio(raw) > TABLE_CHAR_RATIO:
            return "表格残骸"
        return "低自然语言"

    # 1. 目录
    if _is_toc(cleaned):
        return "目录"

    # 2. 参考文献
    if _is_references(cleaned):
        return "参考文献"

    # 3. 图片为主(图片比例高 + 剥离后内容仍偏短)
    if (
        _image_char_ratio(raw) > IMAGE_CHAR_RATIO
        and estimate_tokens(cleaned) < MIN_TOKEN_THRESHOLD
    ):
        return "图片为主"

    # 4. 表格残骸(表格行占比高 + 自然语言比例低)
    if _is_table_residue(cleaned, raw):
        return "表格残骸"

    # 5. 低自然语言
    if _natural_language_ratio(cleaned) < LOW_ALPHA_RATIO:
        return "低自然语言"

    return None


# ---------------------------------------------------------------------------
# 合并:对过短 chunk 向后吸收
# ---------------------------------------------------------------------------


def merge_forward(
    processed_items: "list[tuple[str, Optional[str]]]",
    raw_records: list,
    start_idx: int,
) -> "tuple[str, list[int], int]":
    """对 start_idx 处的过短 chunk 向后吸收邻居。

    停止条件(任一满足):
      - 已达 MIN_TOKEN_THRESHOLD
      - 越界
      - 下一条 reason != None(被过滤的 chunk 不能用于合并)
      - 下一条 source 与起始不同(防止跨来源拼接)

    Returns:
        (merged_text, merged_indices, end)
        - merged_text:已合并文本
        - merged_indices:被合并的原始 index 列表(至少含 start_idx)
        - end:循环应继续的位置(已消费的下一位)
    """
    start_text = processed_items[start_idx][0]
    start_source = _get_source(raw_records[start_idx])

    merged_text = start_text
    merged_indices = [start_idx]
    end = start_idx + 1
    n = len(processed_items)

    while end < n and estimate_tokens(merged_text) < MIN_TOKEN_THRESHOLD:
        next_text, next_reason = processed_items[end]
        # 不能吸收已被分类标记的 chunk(toc/references/...)
        if next_reason is not None:
            break
        # 跨 source 不合并
        next_source = _get_source(raw_records[end])
        if next_source != start_source:
            break

        merged_text = merged_text + MERGE_SEPARATOR + next_text
        merged_indices.append(end)
        end += 1

    return merged_text, merged_indices, end


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _extract_text(record, text_field: str) -> str:
    """从单条 record 中取文本,带常见字段 fallback。"""
    if isinstance(record, dict):
        val = record.get(text_field, "")
        if val:
            return str(val)
        # 与原 question_generate.py 主循环保持一致的 fallback
        for alt in ["text", "content", "body", "paragraph"]:
            alt_val = record.get(alt, "")
            if alt_val:
                return str(alt_val)
        return ""
    if record is None:
        return ""
    return str(record)


def _get_source(record) -> str:
    """从 record 取 source 字段,缺失返回空串。"""
    if isinstance(record, dict):
        return record.get("source", "") or ""
    return ""


def _get_source_id(record) -> str:
    """从 record 取 source_id 字段,缺失返回空串。"""
    if isinstance(record, dict):
        return record.get("source_id", "") or ""
    return ""


def _make_chunk(
    text: str,
    first_record: dict,
    merged_from: Optional[list],
) -> ProcessedChunk:
    """根据合并后的文本与第一条原始 record 构造 ProcessedChunk。"""
    return ProcessedChunk(
        text=text,
        source=_get_source(first_record),
        source_id=_get_source_id(first_record),
        merged_from=merged_from,
        original_record=first_record if isinstance(first_record, dict) else {},
    )


def _image_char_ratio(text: str) -> float:
    """图片链接 ![..](..) 占总字符的比例。"""
    if not text:
        return 0.0
    img_chars = sum(len(m.group(0)) for m in _IMAGE_PATTERN.finditer(text))
    return img_chars / len(text)


def _table_char_ratio(text: str) -> float:
    """表格行(以 | 开头并以 | 结尾)占总字符的比例。"""
    if not text:
        return 0.0
    total = len(text)
    table_chars = 0
    for line in text.splitlines():
        if _TABLE_ROW_PATTERN.match(line):
            table_chars += len(line)
    return table_chars / total


def _natural_language_ratio(text: str) -> float:
    """中英文字符占总字符的比例 — 衡量"自然语言含量"。"""
    if not text:
        return 0.0
    chinese = sum(1 for c in text if _CN_LO <= c <= _CN_HI)
    english_chars = sum(len(w) for w in _ENGLISH_WORD_PATTERN.findall(text))
    return (chinese + english_chars) / len(text)


def _is_toc(text: str) -> bool:
    """目录判定（含中文式目录支持）。

    命中任一即判定为 TOC:
      A) 章节模式行 >= 2 行 AND 占非空行比例 > TOC_PATTERN_RATIO
         AND 至少 1 个页码标记（点引导 / 括号页码）
         → 标准多行目录
      B) 短行(< SHORT_LINE_LEN)占比 > TOC_SHORT_LINE_RATIO
         AND 非空行 >= 5 AND 至少 1 个页码标记
         → 短行密集型目录

    章节模式：第X章/节 | 数字小节(1.1) | 中文数字(一、二、)
    页码标记：行尾点引导(... 123) | 括号页码 (123) / （123）

    要求"页码标记"是为了不误伤正文里的中文列举段落
    （如 "一、效率高 二、可扩展 三、易维护"）。
    """
    non_empty_lines = [l for l in text.splitlines() if l.strip()]
    if not non_empty_lines:
        return False

    chapter_pattern_hits = 0      # 章节模式行计数
    page_marker_hits = 0          # 页码标记次数（点引导 / 括号页码）
    short_line_hits = 0
    for line in non_empty_lines:
        stripped = line.strip()
        # 章节模式判定
        is_chapter = (
            _TOC_CHAPTER_PATTERN.match(stripped) is not None
            or _TOC_SECTION_PATTERN.match(stripped) is not None
            or _TOC_CN_NUM_PATTERN.match(stripped) is not None
        )
        if is_chapter:
            chapter_pattern_hits += 1
        # 页码标记判定（同一行可能既有章节又有页码，分开计数）
        if (
            _TOC_DOT_LEADER_PATTERN.search(stripped)
            or _DOT_LEADER_TAIL_PATTERN.search(stripped)
            or _TOC_PAREN_PAGE_PATTERN.search(stripped)
        ):
            page_marker_hits += 1
        if len(stripped) < SHORT_LINE_LEN:
            short_line_hits += 1

    chapter_ratio = chapter_pattern_hits / len(non_empty_lines)
    short_ratio = short_line_hits / len(non_empty_lines)

    # A. 多行章节式目录
    if (
        chapter_pattern_hits >= 2
        and chapter_ratio > TOC_PATTERN_RATIO
        and page_marker_hits >= 1
    ):
        return True
    # B. 短行密集型目录
    if (
        short_ratio > TOC_SHORT_LINE_RATIO
        and len(non_empty_lines) >= 5
        and page_marker_hits >= 1
    ):
        return True
    return False


def _is_references(text: str) -> bool:
    """参考文献判定。

    命中任一即判定:
      A) 行首 [n] 行占比 > REFERENCES_LINE_RATIO,且至少 2 行命中
      B) DOI / 期刊缩写关键词密集(每 100 字符 > 1 次,且 >= 3 次)
    """
    non_empty_lines = [l for l in text.splitlines() if l.strip()]
    if not non_empty_lines:
        return False

    ref_line_hits = sum(
        1 for line in non_empty_lines if _REF_LINE_PATTERN.match(line)
    )
    if (
        ref_line_hits >= 2
        and ref_line_hits / len(non_empty_lines) > REFERENCES_LINE_RATIO
    ):
        return True

    # 关键词密度
    keyword_hits = len(_REF_KEYWORD_PATTERN.findall(text))
    if keyword_hits >= 3 and keyword_hits / max(len(text), 1) * 100 > 1.0:
        return True

    return False


def _is_table_residue(cleaned: str, raw: str) -> bool:
    """表格残骸判定:原文表格行占比高且清洗后自然语言低。"""
    if _table_char_ratio(raw) > TABLE_CHAR_RATIO:
        if _natural_language_ratio(cleaned) < LOW_ALPHA_RATIO:
            return True
    return False
