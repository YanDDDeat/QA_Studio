from app.services.cot_quality_check_service import (
    _build_user_prompt,
    normalize_cot_quality_check_records,
)


def test_normalize_uses_top_level_samples_array_and_preserves_sample_fields():
    payload = {
        "schema_version": "1.0",
        "run_id": "run-1",
        "sample_count": 2,
        "samples": [
            {
                "input": "问题1",
                "chainofThought": ["步骤1", "步骤2"],
                "output": "答案1",
                "source_index": 0,
                "evidence_trace": {"doc": "A"},
            },
            {
                "input": "问题2",
                "chain_of_thought": "推理2",
                "output": "答案2",
                "cot_type": "L0",
            },
        ],
    }

    records = normalize_cot_quality_check_records(payload)

    assert len(records) == 2
    assert records[0]["source_index"] == 0
    assert records[0]["evidence_trace"] == {"doc": "A"}
    assert records[1]["cot_type"] == "L0"
    assert "schema_version" not in records[0]


def test_normalize_keeps_top_level_list_single_object_and_nested_wrapper_formats():
    list_payload = [{"input": "问题", "chainofThought": "推理", "output": "答案"}]
    assert normalize_cot_quality_check_records(list_payload) == list_payload

    single_payload = {"input": "单条问题", "cot": "单条推理", "output": "单条答案"}
    assert normalize_cot_quality_check_records(single_payload) == [single_payload]

    nested_payload = [{
        "l0_cot_node": {
            "id": "L0-1",
            "input": "嵌套问题",
            "chainofThought": "嵌套推理",
            "output": "嵌套答案",
        },
        "source": "paper.md",
    }]
    normalized = normalize_cot_quality_check_records(nested_payload)

    assert normalized == [{
        "id": "L0-1",
        "input": "嵌套问题",
        "chainofThought": "嵌套推理",
        "output": "嵌套答案",
        "_wrapper_key": "l0_cot_node",
        "source": "paper.md",
    }]


def test_build_user_prompt_formats_list_and_dict_cot_values_readably():
    prompt = _build_user_prompt({
        "input": "问题",
        "chainofThought": [
            "步骤1：观察现象",
            {"step": 2, "reason": "分析原因"},
            ["子步骤A", "子步骤B"],
        ],
        "output": "答案",
    })

    assert "**chain_of_thought：**\n步骤1：观察现象" in prompt
    assert '{"step": 2, "reason": "分析原因"}' in prompt
    assert '["子步骤A", "子步骤B"]' in prompt
    assert "['" not in prompt

    dict_prompt = _build_user_prompt({
        "input": "问题",
        "cot": {"step": 1, "reason": "字典推理"},
        "output": "答案",
    })

    assert '{\n  "step": 1,\n  "reason": "字典推理"\n}' in dict_prompt
