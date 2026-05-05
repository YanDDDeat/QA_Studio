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
}

/** Fields that contain long text (rendered in full-width blocks) */
export const LONG_TEXT_FIELDS = new Set([
  'input', 'output', 'cot', 'knowledge', 'originContent', 'Assessment',
])

/** Fields displayed in the metadata descriptions table (short values) */
export const META_FIELDS = Object.keys(FIELD_LABELS).filter(
  k => !LONG_TEXT_FIELDS.has(k)
)
