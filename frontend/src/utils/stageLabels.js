export const STAGE_LABELS = {
  question_generate: '问题生成',
  knowledge_generate: '知识体系',
  question_validate: '问题校验',
  answer_generate: '答案生成',
  answer_validate: '答案校验',
  data_evaluate: '数据评估',
  cot_filter: 'COT过滤',
  dataset_split: '数据集切分',
  dataset_assessment: '评分标准生成',
}

export function getStageLabel(stageKey) {
  return STAGE_LABELS[stageKey] || stageKey
}

/** Build default output filename: {srcBase}_{stageLabel}_{username}_{timestamp} */
export function buildDefaultOutputFilename(srcFilename, stageKey, username) {
  const base = srcFilename ? srcFilename.replace(/\.json$/i, '') : 'output'
  const label = getStageLabel(stageKey)
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
  return `${base}_${label}_${username}_${ts}`
}
