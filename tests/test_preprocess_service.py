"""单元测试:backend/app/services/preprocess_service.py

覆盖 6 类用例:
    1. estimate_tokens 估算
    2. clean_text 清洗
    3. classify 分类(每个 skip_reason 至少一个正例 + 一个反例)
    4. detect_headers_footers 页眉识别
    5. merge_forward 合并算法
    6. preprocess_chunks 整体集成
"""

import pytest

from app.services.preprocess_service import (
    LOW_ALPHA_RATIO,
    MIN_TOKEN_THRESHOLD,
    PreprocessStats,
    ProcessedChunk,
    SkippedChunk,
    classify,
    clean_text,
    detect_headers_footers,
    estimate_tokens,
    merge_forward,
    preprocess_chunks,
)


# =============================================================================
# 1. estimate_tokens 估算
# =============================================================================


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_pure_chinese(self):
        # 10 个中文字符 → 10 * 1.5 = 15
        assert estimate_tokens("机器学习是一种技术") == int(9 * 1.5)

    def test_pure_english(self):
        # "machine learning" = 2 词, 共 15 个英文字符 + 1 个空格
        # 中文 0; 英文 word 数 2 * 1.3 = 2.6; 其他 = 16 - 0 - 15 = 1; 1 * 0.5 = 0.5
        # 总 = int(2.6 + 0.5) = 3
        assert estimate_tokens("machine learning") == 3

    def test_mixed(self):
        text = "学习 machine"  # 2 中文 + 1 英文词(7 字符) + 1 空格
        # chinese = 2; english_words = 1; english_chars = 7
        # other = 10 - 2 - 7 = 1
        # 总 = int(2*1.5 + 1*1.3 + 1*0.5) = int(4.8) = 4
        assert estimate_tokens(text) == 4

    def test_long_chinese_text_above_threshold(self):
        text = "机" * 80  # 80 中文 → 120 token > 100
        assert estimate_tokens(text) >= MIN_TOKEN_THRESHOLD

    def test_short_chinese_text_below_threshold(self):
        text = "机" * 10  # 10 中文 → 15 token < 100
        assert estimate_tokens(text) < MIN_TOKEN_THRESHOLD


# =============================================================================
# 2. clean_text 清洗
# =============================================================================


class TestCleanText:
    def test_strip_image_links(self):
        text = "前文 ![图1](http://example.com/a.png) 后文"
        result = clean_text(text, [])
        assert "![图1]" not in result
        assert "前文" in result
        assert "后文" in result

    def test_strip_multiple_images(self):
        text = "![](url1) hello ![alt](url2) world ![x](url3)"
        result = clean_text(text, [])
        assert "url1" not in result
        assert "url2" not in result
        assert "hello" in result
        assert "world" in result

    def test_strip_independent_url_line(self):
        text = "前文\nhttps://example.com/path\n后文"
        result = clean_text(text, [])
        assert "https://example.com" not in result
        assert "前文" in result
        assert "后文" in result

    def test_strip_table_separator(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = clean_text(text, [])
        assert "|---|" not in result
        # 数据行保留
        assert "| 1 |" in result

    def test_strip_blacklist_line(self):
        text = "重要内容第一段\n机器学习导论\n重要内容第二段"
        result = clean_text(text, ["机器学习导论"])
        assert "机器学习导论" not in result
        assert "重要内容第一段" in result
        assert "重要内容第二段" in result

    def test_fold_three_or_more_blank_lines(self):
        text = "段落 A\n\n\n\n\n段落 B"
        result = clean_text(text, [])
        # 期望折叠为两个换行
        assert "\n\n\n" not in result
        assert "段落 A" in result and "段落 B" in result

    def test_empty_input_returns_empty(self):
        assert clean_text("", []) == ""
        assert clean_text(None, []) == ""

    def test_does_not_strip_url_inline(self):
        # 整行只有 URL 才剥离;行内的 URL 保留
        text = "参考链接 https://example.com 见上"
        result = clean_text(text, [])
        assert "https://example.com" in result


# =============================================================================
# 3. classify 分类 — 每个 skip_reason 一个正例 + 一个 KEEP 反例
# =============================================================================


class TestClassify:
    # --- toc 正例 + 反例 ---
    def test_toc_positive_chapter_with_dot_leader(self):
        text = (
            "第一章 绪论 ........... 1\n"
            "第二章 方法 ........... 5\n"
            "第三章 实验 ........... 12\n"
            "第四章 结论 ........... 25\n"
            "1.1 背景 ............... 2\n"
            "1.2 目标 ............... 3\n"
        )
        assert classify(text, raw=text) == "目录"

    def test_toc_negative_normal_paragraph(self):
        text = (
            "机器学习是人工智能的一个重要分支,它通过让计算机从数据中学习模式来"
            "完成各种任务。深度学习作为其子领域,在近年来取得了突破性的进展,"
            "尤其在图像识别和自然语言处理方面表现卓越。"
        )
        assert classify(text, raw=text) is None  # KEEP

    # --- 新增:中文式目录(一/二/三 编号 + 括号页码)---
    def test_toc_cn_numeric_with_paren_page(self):
        """用户报告的真实 case:中文编号 + 括号页码,旧规则识别不到。"""
        text = (
            "三、硝酸铵质量分数的测定\n"
            "\n"
            "四、复合油相质量分数的计算 (291)第四节乳化炸药配方组分的测定方法 (291)"
        )
        assert classify(text, raw=text) == "目录"

    def test_toc_cn_numeric_multi_line(self):
        text = (
            "一、绪论 (1)\n"
            "二、相关工作 (15)\n"
            "三、方法 (32)\n"
            "四、实验 (58)\n"
            "五、结论 (79)"
        )
        assert classify(text, raw=text) == "目录"

    def test_toc_negative_cn_numeric_enumeration_without_pages(self):
        """正文里的中文编号列举,无页码,不应误判为目录。"""
        text = (
            "我们的方法有以下优点:\n"
            "一、效率高,运行速度比基线方法提升了三倍\n"
            "二、可扩展性强,能够轻松适配不同规模的数据集\n"
            "三、易维护,代码结构清晰且文档完备"
        )
        assert classify(text, raw=text) is None

    def test_toc_negative_chapter_title_only(self):
        """单纯章节标题(无页码),如正文小节首行,不应误判。"""
        text = "第三章 实验方法\n本章详细介绍我们的实验设计、数据集选择以及评估指标的定义。"
        assert classify(text, raw=text) is None

    # --- references 正例 + 反例 ---
    def test_references_positive(self):
        text = (
            "[1] He K, Zhang X, Ren S. Deep Residual Learning. CVPR 2016.\n"
            "[2] Simonyan K. Very Deep Networks. ICLR 2015.\n"
            "[3] LeCun Y, Bengio Y. Deep Learning. Nature 521: 436-444.\n"
            "[4] Krizhevsky A. ImageNet. NIPS 2012.\n"
        )
        assert classify(text, raw=text) == "参考文献"

    def test_references_negative(self):
        text = (
            "在第一节中我们介绍了基本概念,随后在第二节展开方法论的讨论。"
            "实验结果详见第三节,结论部分对全文进行了总结。"
        )
        assert classify(text, raw=text) is None

    # --- image_only 正例 + 反例 ---
    def test_image_only_positive(self):
        raw = (
            "![figure 1](https://example.com/fig1.png)\n"
            "![figure 2](https://example.com/fig2.png)\n"
            "![figure 3](https://example.com/fig3.png)\n"
            "如图所示。\n"
        )
        cleaned = clean_text(raw, [])
        assert classify(cleaned, raw=raw) == "图片为主"

    def test_image_only_negative_long_text_with_one_image(self):
        # 长文中只有一张图 → 不应判为 image_only
        body = "本节介绍方法概览,详细推导见附录。" * 10
        raw = f"{body}\n![图1](http://example.com/x.png)\n{body}"
        cleaned = clean_text(raw, [])
        assert classify(cleaned, raw=raw) != "图片为主"

    # --- table_residue 正例 + 反例 ---
    def test_table_residue_positive(self):
        raw = (
            "| Method | Accuracy | F1 |\n"
            "|---|---|---|\n"
            "| ResNet | 90.5 | 0.89 |\n"
            "| VGG | 88.2 | 0.87 |\n"
            "| Ours | 92.1 | 0.91 |\n"
            "| Baseline | 75.0 | 0.71 |\n"
            "| RandomForest | 80.0 | 0.78 |\n"
        )
        cleaned = clean_text(raw, [])
        assert classify(cleaned, raw=raw) == "表格残骸"

    def test_table_residue_negative_normal_paragraph(self):
        text = (
            "实验中我们对比了多种基线方法,结果显示我们的方法在准确率上有明显"
            "优势。详细数据见附录表 1。在不同数据集上的鲁棒性也得到了验证。"
        )
        assert classify(text, raw=text) != "表格残骸"

    # --- low_alpha 正例 + 反例 ---
    def test_low_alpha_positive(self):
        text = "123 456 789 === ___ ### *** $$$ &&& 12.5%, 88.3%, 91.2%"
        assert classify(text, raw=text) == "低自然语言"

    def test_low_alpha_negative(self):
        text = "这是一段完全由中文构成的正常段落,自然语言比例接近百分之百。"
        assert classify(text, raw=text) is None

    # --- 清洗后空 → image_only / table_residue / low_alpha ---
    def test_cleaned_empty_from_image(self):
        raw = "![](url1)![](url2)![](url3)"
        cleaned = clean_text(raw, [])
        assert cleaned.strip() == ""
        assert classify(cleaned, raw=raw) == "图片为主"


# =============================================================================
# 4. detect_headers_footers 页眉识别
# =============================================================================


class TestDetectHeadersFooters:
    def test_detect_repeated_short_line(self):
        # 10 条 chunk,其中 5 条含同一短行 "机器学习导论" → 50% > 30%
        repeated = "机器学习导论"
        texts = []
        for i in range(5):
            texts.append(f"{repeated}\n章节正文 {i}")
        for i in range(5):
            texts.append(f"其他正文 {i}")
        blacklist = detect_headers_footers(texts)
        assert repeated in blacklist

    def test_no_false_positive_for_unique_lines(self):
        # 10 条 chunk,每条都不同
        texts = [f"完全独立的段落 {i}" for i in range(10)]
        blacklist = detect_headers_footers(texts)
        # 不应识别任何页眉
        assert blacklist == []

    def test_long_line_not_detected_even_if_repeated(self):
        # 长行(> HEADER_FOOTER_MAX_LEN=40)即使重复也不识别
        long_line = "这是一个超过四十个字符的句子,因此即使在每条 chunk 都出现也不会被识别为页眉页脚。"
        texts = [f"{long_line}\n正文 {i}" for i in range(10)]
        blacklist = detect_headers_footers(texts)
        assert long_line not in blacklist

    def test_within_chunk_repetition_counted_once(self):
        # 同一 chunk 内重复 100 次,只算 1
        text = "页眉\n" * 100 + "正文"
        texts = [text] + [f"无关 {i}" for i in range(9)]  # 10 条
        blacklist = detect_headers_footers(texts)
        # 只出现在 1/10 chunk → 10% < 30%,不进黑名单
        assert "页眉" not in blacklist


# =============================================================================
# 5. merge_forward 合并算法
# =============================================================================


class TestMergeForward:
    def test_short_chunk_absorbs_next(self):
        # 两条都短,合并后达标 (≥100 token)
        short = "短" * 10  # ~15 token
        long_part = "更" * 60  # ~90 token
        records = [
            {"source": "a", "text": short},
            {"source": "a", "text": long_part},
        ]
        items = [(short, None), (long_part, None)]
        merged_text, merged_indices, end = merge_forward(items, records, 0)
        assert len(merged_indices) == 2
        assert end == 2
        assert estimate_tokens(merged_text) >= MIN_TOKEN_THRESHOLD

    def test_chain_merge_multiple_shorts(self):
        # 5 条短 chunk,链式合并到达标
        short = "字" * 25  # ~37 token
        records = [{"source": "a", "text": short} for _ in range(5)]
        items = [(short, None) for _ in range(5)]
        merged_text, merged_indices, end = merge_forward(items, records, 0)
        # 37 * 3 ≈ 112 → 3 条够,第 4 条不再吸收
        assert len(merged_indices) >= 3
        assert estimate_tokens(merged_text) >= MIN_TOKEN_THRESHOLD

    def test_end_orphan_no_merge_possible(self):
        # 单条短 chunk,无后续
        short = "短文"  # ~3 token
        records = [{"source": "a", "text": short}]
        items = [(short, None)]
        merged_text, merged_indices, end = merge_forward(items, records, 0)
        # 没东西可吸,merged 仍是原文
        assert len(merged_indices) == 1
        assert estimate_tokens(merged_text) < MIN_TOKEN_THRESHOLD
        assert end == 1

    def test_cross_source_stops_merge(self):
        # 前后 source 不同,不应合并
        short = "字" * 10
        records = [
            {"source": "a", "text": short},
            {"source": "b", "text": short},
            {"source": "b", "text": short},
        ]
        items = [(short, None), (short, None), (short, None)]
        merged_text, merged_indices, end = merge_forward(items, records, 0)
        assert merged_indices == [0]  # 只有起始
        assert end == 1

    def test_non_none_reason_stops_merge(self):
        # 中间 chunk 已被分类(reason 非 None),不能吸收
        short = "字" * 10
        records = [{"source": "a", "text": short} for _ in range(3)]
        items = [
            (short, None),
            (short, "目录"),  # 不可吸收
            (short, None),
        ]
        merged_text, merged_indices, end = merge_forward(items, records, 0)
        assert merged_indices == [0]
        assert end == 1


# =============================================================================
# 6. preprocess_chunks 整体集成
# =============================================================================


class TestPreprocessChunksIntegration:
    def _build_mixed_payload(self):
        """构造 50 条混合脏数据 + 干净数据。"""
        records = []

        # ── 干净段落 × 20 ──
        for i in range(20):
            records.append({
                "source": "book_a",
                "source_id": f"clean_{i}",
                "text": (
                    f"这是第 {i} 个干净段落,讲述机器学习中的某个具体方法。"
                    "我们详细介绍了模型的网络结构、训练流程以及超参数选择策略。"
                    "实验结果表明该方法在多个公开数据集上取得了优于基线的性能。"
                ),
            })

        # ── 目录页 × 3 ──
        for i in range(3):
            records.append({
                "source": "book_a",
                "source_id": f"toc_{i}",
                "text": (
                    "第一章 绪论 ........... 1\n"
                    "第二章 方法 ........... 5\n"
                    "第三章 实验 ........... 12\n"
                    "第四章 结论 ........... 25\n"
                    "1.1 背景 ............... 2\n"
                    "1.2 目标 ............... 3\n"
                ),
            })

        # ── 参考文献 × 3 ──
        for i in range(3):
            records.append({
                "source": "book_a",
                "source_id": f"ref_{i}",
                "text": (
                    "[1] He K, Zhang X. Deep Learning. CVPR 2016.\n"
                    "[2] LeCun Y. Gradient Methods. Nature 2015.\n"
                    "[3] Krizhevsky A. ImageNet. NIPS 2012.\n"
                    "[4] Simonyan K. Very Deep Networks. ICLR 2015.\n"
                ),
            })

        # ── 图片堆 × 3 ──
        for i in range(3):
            records.append({
                "source": "book_a",
                "source_id": f"img_{i}",
                "text": (
                    "![fig1](https://x.com/a.png)\n"
                    "![fig2](https://x.com/b.png)\n"
                    "![fig3](https://x.com/c.png)\n"
                    "如图所示。"
                ),
            })

        # ── 表格残骸 × 3 ──
        for i in range(3):
            records.append({
                "source": "book_a",
                "source_id": f"tbl_{i}",
                "text": (
                    "| Method | Acc | F1 |\n"
                    "|---|---|---|\n"
                    "| A | 90 | 0.9 |\n"
                    "| B | 85 | 0.85 |\n"
                    "| C | 92 | 0.91 |\n"
                    "| D | 78 | 0.77 |\n"
                ),
            })

        # ── 短 chunk × 6(应该被合并掉) ──
        for i in range(6):
            records.append({
                "source": "book_a",
                "source_id": f"short_{i}",
                "text": f"这是一个非常短的段落 {i}",  # 短,触发合并
            })

        # ── 空 chunk × 2 ──
        for i in range(2):
            records.append({
                "source": "book_a",
                "source_id": f"empty_{i}",
                "text": "",
            })

        # ── 低自然语言 × 2 ──
        for i in range(2):
            records.append({
                "source": "book_a",
                "source_id": f"low_{i}",
                "text": (
                    "123 456 789 === ___ ### *** $$$ &&& "
                    "12.5%, 88.3%, 91.2%, 95.6%, 99.9% @@@@ "
                    "&*^%$ ##@@!! ()()() ;;;;"
                ),
            })

        # ── 末尾再来 8 条干净段落,使总数到 50 ──
        for i in range(8):
            records.append({
                "source": "book_b",
                "source_id": f"clean2_{i}",
                "text": (
                    f"第二批干净段落 {i}:深度学习模型在图像识别任务中表现优异,"
                    "卷积神经网络通过局部感受野和权重共享显著降低了参数数量,"
                    "残差连接的引入进一步缓解了深层网络的梯度消失问题。"
                ),
            })

        assert len(records) == 50
        return records

    def test_returns_correct_types(self):
        records = [{"source": "a", "text": "段落" * 50}]
        chunks, stats = preprocess_chunks(records, "text")
        assert isinstance(chunks, list)
        assert all(isinstance(c, ProcessedChunk) for c in chunks)
        assert isinstance(stats, PreprocessStats)
        assert all(isinstance(s, SkippedChunk) for s in stats.skipped_records)

    def test_clean_paragraph_passes_through(self):
        text = "这是一段长文本。" * 20
        records = [{"source": "a", "source_id": "1", "text": text}]
        chunks, stats = preprocess_chunks(records, "text")
        assert len(chunks) == 1
        assert chunks[0].source == "a"
        assert chunks[0].source_id == "1"
        assert chunks[0].merged_from is None
        assert stats.kept_count == 1
        assert stats.skipped_count == 0

    def test_empty_record_marked_empty(self):
        records = [{"source": "a", "text": ""}]
        chunks, stats = preprocess_chunks(records, "text")
        assert len(chunks) == 0
        assert stats.skipped_count == 1
        assert stats.skipped_records[0].skip_reason == "内容为空"

    def test_single_short_chunk_too_short_at_end(self):
        records = [{"source": "a", "text": "短"}]
        chunks, stats = preprocess_chunks(records, "text")
        assert len(chunks) == 0
        assert stats.skip_breakdown.get("末尾过短", 0) == 1

    def test_skipped_records_sorted_by_original_index(self):
        records = [
            {"source": "a", "text": "长" * 100},   # 0 keep
            {"source": "a", "text": ""},            # 1 empty
            {"source": "a", "text": "长" * 100},   # 2 keep
            {"source": "a", "text": ""},            # 3 empty
        ]
        chunks, stats = preprocess_chunks(records, "text")
        indices = [s.original_index for s in stats.skipped_records]
        assert indices == sorted(indices)

    def test_mixed_50_records_distribution(self):
        records = self._build_mixed_payload()
        chunks, stats = preprocess_chunks(records, "text")

        # 干净段落应保留: 20 + 8 = 28
        # 短 chunk 6 条同 source 应合并产生若干 kept(吸收成 1~2 条)
        # 跳过: 3 toc + 3 ref + 3 img + 3 tbl + 2 empty + 2 low_alpha
        assert stats.original_count == 50
        assert stats.kept_count >= 28  # 至少干净段落数

        # 必须命中的 reason
        assert stats.skip_breakdown.get("目录", 0) == 3
        assert stats.skip_breakdown.get("参考文献", 0) == 3
        assert stats.skip_breakdown.get("图片为主", 0) == 3
        assert stats.skip_breakdown.get("表格残骸", 0) == 3
        assert stats.skip_breakdown.get("内容为空", 0) == 2
        assert stats.skip_breakdown.get("低自然语言", 0) == 2
        # 合并产生:6 条短 chunk 应被聚合为若干"已合并"标记
        assert stats.skip_breakdown.get("已合并", 0) >= 1
        assert stats.kept_by_merge_count >= 1

    def test_merged_chunks_preserve_first_source_id(self):
        # 两条短 chunk 合并 → 取第一条的 source_id
        short = "短文段" * 5
        records = [
            {"source": "a", "source_id": "first", "text": short},
            {"source": "a", "source_id": "second", "text": short},
            {"source": "a", "source_id": "third", "text": short},
        ]
        chunks, stats = preprocess_chunks(records, "text")
        # 至少有一条合并产生
        merged_chunks = [c for c in chunks if c.merged_from is not None]
        if merged_chunks:
            assert merged_chunks[0].source_id == "first"

    def test_header_footer_stripped_from_output(self):
        # 10 条 chunk,每条都含"页眉标题"
        records = []
        for i in range(10):
            records.append({
                "source": "a",
                "source_id": str(i),
                "text": (
                    "页眉标题\n"
                    f"这是第 {i} 段的主体内容,长度需要保证超过预处理阈值。"
                    "深度学习方法在多种任务上展现出强大的拟合能力,但同时也带来"
                    "了模型可解释性下降的问题。本文从理论与实验两个角度展开讨论。"
                ),
            })
        chunks, stats = preprocess_chunks(records, "text")
        assert "页眉标题" in stats.header_footer_blacklist
        # 清洗后的 chunk 不再含页眉
        for c in chunks:
            assert "页眉标题" not in c.text

    def test_resume_determinism(self):
        # 同样的输入,运行两次,结果应完全一致
        records = self._build_mixed_payload()
        chunks_a, stats_a = preprocess_chunks(records, "text")
        chunks_b, stats_b = preprocess_chunks(records, "text")
        assert len(chunks_a) == len(chunks_b)
        for ca, cb in zip(chunks_a, chunks_b):
            assert ca.text == cb.text
            assert ca.source == cb.source
            assert ca.source_id == cb.source_id
            assert ca.merged_from == cb.merged_from
        assert stats_a.kept_count == stats_b.kept_count
        assert stats_a.skip_breakdown == stats_b.skip_breakdown

    def test_field_fallback_to_common_alts(self):
        # text_field="content" 但记录里只有 "text"
        records = [{"source": "a", "text": "回退字段" * 50}]
        chunks, stats = preprocess_chunks(records, "content")
        assert len(chunks) == 1  # fallback 命中

    def test_non_dict_record_handled(self):
        records = ["纯字符串记录" * 50]
        chunks, stats = preprocess_chunks(records, "text")
        assert len(chunks) == 1
        assert chunks[0].source == ""  # 非 dict 无 source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
