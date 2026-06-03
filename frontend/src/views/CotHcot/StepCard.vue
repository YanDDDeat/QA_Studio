<template>
  <div
    class="step-card"
    :class="{ 'step-completed': step.status === 'completed', 'step-running': step.status === 'running', 'step-failed': step.status === 'failed' }"
  >
    <!-- 步骤头部 -->
    <div class="step-header">
      <div class="step-index" :class="{ 'index-completed': step.status === 'completed', 'index-failed': step.status === 'failed' }">
        {{ step.status === 'completed' ? '✓' : (step.status === 'failed' ? '✗' : (index + 1)) }}
      </div>
      <div class="step-info">
        <div class="step-name">{{ step.display_name }}</div>
        <div class="step-badges">
          <el-tag :type="statusTagType(step.status)" size="small">
            {{ statusLabel(step.status) }}
          </el-tag>
          <el-tag :type="granularityTagType(step.granularity)" size="small" style="margin-left: 4px">
            {{ granularityTag(step.granularity) }}
          </el-tag>
          <el-tag v-if="!step.needs_llm" type="info" size="small" style="margin-left: 4px">
            纯数据合成
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="step.status === 'running'" class="step-progress">
      <el-progress
        :percentage="step.progress_current"
        :stroke-width="12"
        striped
        striped-flow
      >
        <template #default>
          <span>{{ step.progress_label || '正在执行...' }}</span>
        </template>
      </el-progress>
    </div>

    <!-- 步骤操作 -->
    <div class="step-actions">
      <el-button
        v-if="canRun"
        type="primary"
        size="small"
        @click="$emit('run')"
      >
        <el-icon><VideoPlay /></el-icon>
        运行
      </el-button>

      <el-button
        v-if="step.status === 'failed'"
        type="warning"
        size="small"
        @click="$emit('run')"
      >
        <el-icon><RefreshRight /></el-icon>
        重试
      </el-button>

      <span v-if="step.status === 'running'" class="running-indicator">
        <el-icon class="is-loading"><Loading /></el-icon>
        {{ step.progress_label || '正在执行...' }}
      </span>

      <el-button
        v-if="step.output_file_id && step.step_name !== 'export_jsonl'"
        type="success"
        size="small"
        link
        @click="viewOutputFile"
      >
        <el-icon><Document /></el-icon>
        查看
      </el-button>

      <el-button
        v-if="step.output_file_id && step.step_name === 'export_jsonl'"
        type="success"
        size="small"
        link
        @click="downloadOutputFile"
      >
        <el-icon><Download /></el-icon>
        下载训练数据
      </el-button>
    </div>

    <!-- 步骤间连接线 -->
    <div v-if="index < total - 1" class="step-connector"></div>
  </div>
</template>

<script setup>
import { VideoPlay, RefreshRight, Loading, Document, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { downloadManagedFile } from '../../api'

const props = defineProps({
  step: { type: Object, required: true },
  index: { type: Number, required: true },
  total: { type: Number, required: true },
  canRun: { type: Boolean, default: false },
})

const emit = defineEmits(['run', 'view-file'])

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '未开始', paused: '已暂停' }
  return map[s] || s
}

function granularityTag(granularity) {
  const map = { per_chunk: '分段级', document: '文档级', per_l0: 'per-L0' }
  return map[granularity] || granularity
}

function granularityTagType(granularity) {
  const map = { per_chunk: 'warning', document: 'primary', per_l0: 'danger' }
  return map[granularity] || 'info'
}

function viewOutputFile() {
  emit('view-file', props.step)
}

async function downloadOutputFile() {
  try {
    const blob = await downloadManagedFile(props.step.output_file_id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = props.step.output_filename || `训练数据_${props.step.step_name}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch (err) {
    const detail = err.response?.data?.detail || '下载失败'
    ElMessage.error(detail)
  }
}
</script>

<style scoped>
.step-card {
  padding: 16px 20px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  transition: all 0.3s;
  margin-bottom: 4px;
}

.step-card.step-completed {
  background: #f0f9eb;
  border-color: #b3e19d;
}

.step-card.step-running {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.step-card.step-failed {
  background: #fef0f0;
  border-color: #fbc4c4;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-index {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #909399;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.step-index.index-completed {
  background: #67c23a;
}

.step-index.index-failed {
  background: #f56c6c;
}

.step-card.step-running .step-index {
  background: #409eff;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.step-name {
  font-weight: 600;
  font-size: 15px;
}

.step-badges {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-progress {
  margin-top: 8px;
  padding: 4px 0;
}

.step-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0,0,0,0.06);
}

.running-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #409eff;
  font-size: 13px;
}

.step-connector {
  width: 2px;
  height: 16px;
  background: #dcdfe6;
  margin-left: 36px;
  border-radius: 1px;
}
</style>