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

defineProps({
  version: { type: Number, default: null },
  content: { type: String, default: '' },
  timeLabel: { type: String, default: '' },
  contentChanged: { type: Boolean, default: false },
  saveLoading: { type: Boolean, default: false },
  nextVersion: { type: Number, default: 1 },
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
