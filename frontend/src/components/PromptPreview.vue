<template>
  <div class="prompt-preview">
    <div v-if="version != null" class="preview-content">
      <div class="preview-header">
        <el-tag size="small" type="primary">版本 v{{ version }}</el-tag>
        <span class="preview-time">{{ timeLabel }}</span>
      </div>
      <div v-if="recommendedJson" class="preview-fields">
        <span class="fields-label">建议返回字段至少包括 </span>
        <code class="fields-json">{{ recommendedJson }}</code>
      </div>
      <el-input
        type="textarea"
        :model-value="content"
        :autosize="{ minRows: 6, maxRows: 18 }"
        class="preview-textarea"
        @update:model-value="$emit('update:content', $event)"
      />
      <div class="preview-footer">
        <el-button
          type="primary"
          :loading="saveLoading"
          :disabled="!contentChanged"
          size="small"
          @click="$emit('save')"
        >
          保存 (v{{ nextVersion }})
        </el-button>
      </div>
    </div>
    <div v-else class="preview-empty">
      <el-icon :size="32"><Document /></el-icon>
      <p>请先选择一个提示词</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Document } from '@element-plus/icons-vue'

const RECOMMENDED = {
  question_generate: ['input', 'difficulty', 'task_type'],
  knowledge_generate: ['knowledge', 'scene'],
  question_validate: ['validation_result', 'reason'],
  answer_generate: ['output', 'cot', 'step_count'],
  answer_validate: ['validation_result', 'reason'],
  data_evaluate: ['relevance', 'clarity', 'reasoning', 'terminology', 'score'],
  dataset_assessment: ['Assessment'],
}

const LIST_STAGES = new Set(['question_generate'])

const props = defineProps({
  version: { type: Number, default: null },
  content: { type: String, default: '' },
  timeLabel: { type: String, default: '' },
  contentChanged: { type: Boolean, default: false },
  saveLoading: { type: Boolean, default: false },
  nextVersion: { type: Number, default: 1 },
  stage: { type: String, default: '' },
})

const recommendedJson = computed(() => {
  const keys = RECOMMENDED[props.stage]
  if (!keys || keys.length === 0) return ''
  const obj = {}
  keys.forEach(k => { obj[k] = '' })
  const json = JSON.stringify(obj)
  return LIST_STAGES.has(props.stage) ? `[${json}]` : json
})

defineEmits(['update:content', 'save'])
</script>

<style scoped>
.prompt-preview {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.preview-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.preview-time {
  color: #909399;
  font-size: 13px;
}

.preview-fields {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.fields-label {
  color: #606266;
  font-size: 12px;
  white-space: nowrap;
}

.fields-json {
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  color: #67c23a;
  background: #f0f9eb;
  padding: 2px 6px;
  border-radius: 3px;
  word-break: break-all;
}

.preview-textarea :deep(.el-textarea__inner) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #fff;
  border-radius: 4px;
  overflow-y: auto;
}

.preview-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid #e4e7ed;
}

.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: #909399;
}

.preview-empty p {
  font-size: 14px;
}
</style>
