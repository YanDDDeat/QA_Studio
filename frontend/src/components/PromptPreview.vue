<template>
  <div class="prompt-preview">
    <div v-if="version != null" class="preview-content">
      <div class="preview-header">
        <el-tag size="small" type="primary">版本 v{{ version }}</el-tag>
        <span class="preview-time">{{ timeLabel }}</span>
      </div>
      <el-input
        type="textarea"
        :model-value="content"
        :autosize="{ minRows: 6, maxRows: 18 }"
        class="preview-textarea"
        @update:model-value="$emit('update:content', $event)"
      />
      <!-- 附加参考字段选择 -->
      <div class="reference-fields">
        <span class="reference-label">附加参考字段：</span>
        <el-checkbox
          v-for="f in availableFields"
          :key="f.value"
          :model-value="referenceFields.includes(f.value)"
          size="small"
          @update:model-value="toggleField(f.value, $event)"
        >{{ f.value }}</el-checkbox>
      </div>
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
import { Document } from '@element-plus/icons-vue'

const availableFields = [
  { value: 'input', label: '问题(input)' },
  { value: 'output', label: '答案(output)' },
  { value: 'cot', label: '推理过程(cot)' },
  { value: 'knowledge', label: '知识体系(knowledge)' },
  { value: 'domain', label: '领域(domain)' },
  { value: 'difficulty', label: '难度(difficulty)' },
  { value: 'task_type', label: '任务类型(task_type)' },
  { value: 'originContent', label: '原文(originContent)' },
  { value: 'scene', label: '场景(scene)' },
  { value: 'source', label: '来源(source)' },
  { value: 'source_type', label: '来源类型(source_type)' },
  { value: 'step_count', label: '步骤数(step_count)' },
]

const props = defineProps({
  version: { type: Number, default: null },
  content: { type: String, default: '' },
  timeLabel: { type: String, default: '' },
  contentChanged: { type: Boolean, default: false },
  saveLoading: { type: Boolean, default: false },
  nextVersion: { type: Number, default: 1 },
  referenceFields: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:content', 'save', 'update:referenceFields'])

function toggleField(field, checked) {
  const next = checked
    ? [...props.referenceFields, field]
    : props.referenceFields.filter(f => f !== field)
  emit('update:referenceFields', next)
}
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

.reference-fields {
  padding: 8px 0;
  border-bottom: 1px solid #e4e7ed;
}

.reference-label {
  font-size: 13px;
  color: #606266;
  margin-right: 8px;
}

.reference-fields :deep(.el-checkbox) {
  margin-right: 16px;
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