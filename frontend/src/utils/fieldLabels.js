/**
 * JSON field name → Chinese label mappings for detail dialogs.
 * Used to dynamically render all available fields in a record.
 */
export const FIELD_LABELS = {
  id: 'ID',
  domain: '领域',
  category: '类别',
  task_type: '题型',
  input: '问题 (Input)',
  output: '答案 (Output)',
  cot: '思维链 (CoT)',
  step_count: '推理步骤数',
  corpus_cate: '语料类别',
  scene: '场景',
  Assessment: '评分标准',
  source: '来源名称',
  source_id: '来源ID',
  source_type: '来源类型',
  originContent: '原始内容',
  knowledge: '知识 (Knowledge)',
  difficulty: '难度',
  relevance: '相关性',
  clarity: '清晰度',
  reasoning: '推理',
  terminology: '术语',
  score: '综合评分',
  passed: '是否通过',
  current_stage: '当前阶段',
  created_at: '创建时间',
  updated_at: '更新时间',
}

/** Threshold for categorizing a field as long text (character count) */
export const LONG_TEXT_THRESHOLD = 200

/** System fields excluded from detail dialogs */
const SYSTEM_FIELDS = new Set(['user_id', 'file_id'])

/** Fields that always display as separate blocks (long-text style) */
const ALWAYS_LONG_TEXT = new Set(['input', 'output', 'cot', 'originContent'])

/**
 * Categorize all fields in a record into meta (short) and long-text groups.
 * input, output, cot, originContent always go to longText regardless of value length.
 * Null values are still included in longText for ALWAYS_LONG_TEXT fields.
 * extra_fields (JSON dict) is expanded: each key becomes a top-level field.
 */
export function categorizeFields(record) {
  // Flatten extra_fields into the record before categorizing
  const flat = { ...record }
  const extra = record.extra_fields
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    delete flat.extra_fields
    for (const [k, v] of Object.entries(extra)) {
      if (!(k in flat)) {
        flat[k] = v
      }
    }
  } else {
    delete flat.extra_fields
  }

  const meta = []
  const longText = []
  for (const key of Object.keys(flat)) {
    if (SYSTEM_FIELDS.has(key)) continue
    if (ALWAYS_LONG_TEXT.has(key)) {
      longText.push(key)
      continue
    }
    const val = flat[key]
    if (val == null) continue
    if (typeof val === 'string' && val.length > LONG_TEXT_THRESHOLD) {
      longText.push(key)
    } else if (typeof val === 'object') {
      // Objects/dicts display as long text (JSON formatted)
      longText.push(key)
    } else {
      meta.push(key)
    }
  }
  return { meta, longText, flat }
}