<template>
  <div class="page-container">
    <!-- 顶部基本信息 -->
    <el-card class="info-card">
      <template #header>
        <div class="card-header">
          <span>{{ run?.run_name || '单COT生成详情' }}</span>
          <div>
            <el-tag :type="statusTagType(run?.status)" size="large">
              {{ statusLabel(run?.status) }}
            </el-tag>
            <el-button
              v-if="run?.status === 'running'"
              type="warning"
              :loading="pauseLoading"
              style="margin-left: 12px"
              @click="handlePause"
            >
              暂停运行
            </el-button>
            <el-button
              v-if="run?.status === 'paused' || run?.status === 'failed'"
              type="success"
              :loading="resumeLoading"
              style="margin-left: 12px"
              @click="handleResume"
            >
              恢复运行
            </el-button>
            <el-button @click="goBack" style="margin-left: 12px">
              <el-icon><ArrowLeft /></el-icon>
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border v-if="run">
        <el-descriptions-item label="流水线">{{ run.pipeline_name }}</el-descriptions-item>
        <el-descriptions-item label="Run ID">{{ run.run_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(run.status)" size="small">{{ statusLabel(run.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="源文件">{{ run.source_file?.filename || '—' }}</el-descriptions-item>
        <el-descriptions-item label="正文字段">{{ run.source_input?.text_field || '—' }}</el-descriptions-item>
        <el-descriptions-item label="模型判定 CoT 类型">{{ recommendedCotTypeLabel }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ run.llm?.model || '—' }}</el-descriptions-item>
        <el-descriptions-item label="输入文献数">{{ run.input_count ?? 1 }}</el-descriptions-item>
        <el-descriptions-item label="样本数">{{ run.sample_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="成功/失败">
          <span style="color: #67c23a">{{ run.success_count ?? 0 }}</span>
          <span> / </span>
          <span :style="{ color: (run.failed_count ?? 0) > 0 ? '#f56c6c' : '#606266' }">{{ run.failed_count ?? 0 }}</span>
          <span v-if="processingCount > 0" style="color: #e6a23c; margin-left: 4px">
            / {{ processingCount }} 处理中
          </span>
          <span style="color: #909399; font-size: 12px; margin-left: 4px">
            （共 {{ run.input_count ?? 1 }} 篇）
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(run.created_at) }}</el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="run?.error_message"
        type="error"
        :title="run.error_message"
        show-icon
        style="margin-top: 12px"
      />
      <el-alert
        v-else-if="run?.stop_reason"
        type="warning"
        :title="run.stop_reason"
        show-icon
        style="margin-top: 12px"
      />
    </el-card>

    <!-- 总进度条 -->
    <el-card style="margin-top: 16px" v-if="run">
      <div class="overall-progress">
        <div class="progress-header">
          <span class="progress-title">流水线总进度</span>
          <span class="progress-count">
            完成 {{ run.completed_steps || 0 }}/{{ run.total_steps || 0 }} 步
            <span v-if="run.skipped_steps">，跳过 {{ run.skipped_steps }}</span>
          </span>
        </div>
        <el-progress
          :percentage="run.progress_percentage || 0"
          :status="overallStatus"
          :stroke-width="20"
        />
        <div v-if="run.input_count > 1 && run.progress_label" class="batch-progress-label">
          <el-tag :type="run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'primary'" size="small">
            {{ run.progress_label }}
          </el-tag>
        </div>
        <div class="step-tracker">
          <div
            v-for="step in run.steps"
            :key="step.step_key"
            class="step-dot"
            :class="stepDotClass(step)"
            :title="step.display_name"
          ></div>
        </div>
      </div>
    </el-card>

    <!-- 文献级阶段进度 -->
    <el-card
      v-if="documentStageMatrix.length"
      class="document-stage-card"
      style="margin-top: 16px"
    >
      <template #header>
        <div class="card-header">
          <div class="matrix-title-wrap">
            <el-tag type="warning" size="small">文献级</el-tag>
            <span>文献级阶段进度</span>
          </div>
          <div class="matrix-legend">
            <span v-for="legend in stageLegends" :key="legend.status" class="legend-item">
              <i class="legend-dot" :class="`doc-status-${legend.status}`"></i>
              {{ legend.label }}
            </span>
          </div>
        </div>
      </template>

      <div class="doc-grid">
        <div
          v-for="doc in documentStageMatrix"
          :key="doc.source_index"
          class="doc-block"
          :class="[`doc-status-${doc.status || 'pending'}`, { 'block-selected': activeDocumentDetail?.source_index === doc.source_index }]"
          @click="selectDocument(doc.source_index)"
          :title="`文献 ${(doc.source_index ?? 0) + 1}: ${documentStatusLabel(doc)}`"
        >
          {{ (doc.source_index ?? 0) + 1 }}
        </div>
      </div>

      <div style="margin-top: 16px" v-if="activeDocumentDetail">
        <el-divider content-position="left">
          文献 {{ (activeDocumentDetail.source_index ?? 0) + 1 }} — {{ activeDocumentDetail.source }}
          <el-tag :type="statusTagType(activeDocumentDetail.status)" size="small" style="margin-left: 6px">
            {{ documentStatusLabel(activeDocumentDetail) }}
          </el-tag>
          <el-tag v-if="activeDocumentDetail.cot_type" type="info" size="small" style="margin-left: 4px">
            {{ activeDocumentDetail.cot_type }}
          </el-tag>
        </el-divider>

        <div class="doc-steps-container">
          <div
            v-for="(step, index) in activeDocumentDetail.steps"
            :key="step.step_key"
            class="doc-step-card"
            :class="{
              'step-completed': step.status === 'completed',
              'step-running': step.status === 'running',
              'step-failed': step.status === 'failed',
              'step-skipped': step.status === 'skipped',
            }"
          >
            <div class="step-header">
              <div class="step-index" :class="{
                'index-completed': step.status === 'completed',
                'index-failed': step.status === 'failed',
                'index-skipped': step.status === 'skipped',
              }">
                {{ step.status === 'completed' ? '✓' : step.status === 'skipped' ? '—' : (index + 1) }}
              </div>
              <div class="step-info">
                <div class="step-name">{{ step.display_name }}</div>
                <div class="step-badges">
                  <el-tag :type="statusTagType(step.status)" size="small">
                    {{ statusLabel(step.status) }}
                  </el-tag>
                </div>
              </div>
            </div>

            <div class="step-actions">
              <span v-if="step.status === 'running'" class="running-indicator">
                <el-icon class="is-loading"><Loading /></el-icon>
                {{ step.progress_label || '正在执行...' }}
              </span>
              <span v-else-if="step.progress_label" class="step-label">
                {{ step.progress_label }}
              </span>

              <el-button
                v-if="step.status === 'completed' && step.artifact_path"
                type="success"
                size="small"
                link
                @click="previewArtifact(step.artifact_path, step.display_name)"
              >
                <el-icon><Document /></el-icon>
                查看产物
              </el-button>
            </div>

            <div v-if="step.error" class="step-error">
              <el-text type="danger" size="small">{{ step.error }}</el-text>
            </div>

            <div v-if="index < activeDocumentDetail.steps.length - 1" class="step-connector"></div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 步骤列表（仅旧 run 无文献级矩阵时展示） -->
    <el-card v-if="!documentStageMatrix.length" style="margin-top: 16px" v-loading="loading">
      <template #header>
        <span>流水线步骤</span>
      </template>

      <div class="steps-container" v-if="run">
        <div
          v-for="(step, index) in run.steps"
          :key="step.step_key"
          class="step-card"
          :class="{
            'step-completed': step.status === 'completed',
            'step-running': step.status === 'running',
            'step-failed': step.status === 'failed',
            'step-skipped': step.status === 'skipped',
          }"
        >
          <div class="step-header">
            <div class="step-index" :class="{
              'index-completed': step.status === 'completed',
              'index-failed': step.status === 'failed',
              'index-skipped': step.status === 'skipped',
            }">
              {{ step.status === 'completed' ? '✓' : step.status === 'skipped' ? '—' : (index + 1) }}
            </div>
            <div class="step-info">
              <div class="step-name">{{ step.display_name }}</div>
              <div class="step-badges">
                <el-tag :type="statusTagType(step.status)" size="small">
                  {{ statusLabel(step.status) }}
                </el-tag>
                <el-tag v-if="step.cot_type" type="info" size="small" style="margin-left: 4px">
                  {{ step.cot_type }}
                </el-tag>
              </div>
            </div>
          </div>

          <div v-if="step.status === 'running'" class="step-progress">
            <el-progress
              :percentage="step.progress_current || 0"
              :stroke-width="12"
              striped
              striped-flow
            >
              <template #default>
                <span>{{ step.progress_label || '正在执行...' }}</span>
              </template>
            </el-progress>
          </div>

          <div class="step-actions">
            <span v-if="step.status === 'running'" class="running-indicator">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ step.progress_label || '正在执行...' }}
            </span>
            <span v-else-if="step.progress_label" class="step-label">
              {{ step.progress_label }}
            </span>

            <el-button
              v-if="step.status === 'completed' && step.artifact_path"
              type="success"
              size="small"
              link
              @click="previewArtifact(step.artifact_path, step.display_name)"
            >
              <el-icon><Document /></el-icon>
              查看产物
            </el-button>
          </div>

          <div v-if="index < run.steps.length - 1" class="step-connector"></div>
        </div>
      </div>
    </el-card>

    <!-- 批量处理失败明细 -->
    <el-card style="margin-top: 16px" v-if="run && run.batch_summary && failedBatchItems.length > 0">
      <template #header>
        <div class="card-header">
          <span>失败文献明细</span>
          <el-tag type="danger" size="small">
            {{ failedBatchItems.length }} / {{ run.batch_summary.input_count }} 篇失败
          </el-tag>
        </div>
      </template>
      <el-table :data="failedBatchItems" stripe style="width: 100%">
        <el-table-column prop="source_index" label="序号" width="70" />
        <el-table-column prop="source" label="文献标识" min-width="200" show-overflow-tooltip />
        <el-table-column prop="error" label="失败原因" min-width="300" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 最终导出区 -->
    <el-card style="margin-top: 16px" v-if="run">
      <template #header>
        <div class="card-header">
          <span>最终产物</span>
          <div>
            <el-button
              type="success"
              size="small"
              :disabled="!hasFinalJson"
              @click="downloadExport('json')"
            >
              <el-icon><Download /></el-icon>
              下载 final_samples.json
            </el-button>
            <el-button
              type="success"
              size="small"
              :disabled="!hasFinalJsonl"
              @click="downloadExport('jsonl')"
            >
              <el-icon><Download /></el-icon>
              下载 final_samples.jsonl
            </el-button>
            <el-button
              type="primary"
              size="small"
              :disabled="!hasFinalJson"
              @click="previewArtifact('final_samples.json', 'final_samples.json')"
            >
              <el-icon><Document /></el-icon>
              预览最终样本
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="run.final_samples_preview || []" stripe style="width: 100%">
        <el-table-column prop="cot_type" label="CoT 类型" min-width="180" />
        <el-table-column prop="input" label="Input" min-width="260" show-overflow-tooltip />
        <el-table-column prop="output" label="Output" min-width="260" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!run.final_samples_preview?.length" description="暂无最终样本" />
    </el-card>

    <!-- 输出文件预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewFileName"
      width="760px"
      destroy-on-close
    >
      <div v-loading="previewLoading" class="preview-content">
        <pre v-if="previewContent">{{ previewContent }}</pre>
        <el-empty v-else description="文件内容为空" />
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Document, Download, Loading } from '@element-plus/icons-vue'
import {
  downloadProfessionalCotExport,
  getProfessionalCotArtifact,
  getProfessionalCotRunDetail,
  pauseProfessionalCotRun,
  resumeProfessionalCotRun,
} from '../../api'

const router = useRouter()
const route = useRoute()
const runId = computed(() => route.params.id)

const loading = ref(false)
const resumeLoading = ref(false)
const pauseLoading = ref(false)
const run = ref(null)
let pollTimer = null

async function fetchRunDetail() {
  try {
    const res = await getProfessionalCotRunDetail(runId.value)
    run.value = res
    scheduleNextPoll()
  } catch (err) {
    const detail = err.response?.data?.detail || '获取流水线详情失败'
    ElMessage.error(detail)
  }
}

function scheduleNextPoll() {
  stopPolling()
  if (run.value?.status !== 'running' && !run.value?.steps?.some(s => s.status === 'running')) {
    return
  }
  const runningStep = run.value?.steps?.find(s => s.status === 'running')
  const interval = (runningStep?.progress_current > 10) ? 5000 : 2000
  pollTimer = setTimeout(() => {
    fetchRunDetail()
  }, interval)
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const hasFinalJson = computed(() => Boolean(run.value?.final_outputs?.json))
const hasFinalJsonl = computed(() => Boolean(run.value?.final_outputs?.jsonl))
const documentStageMatrix = computed(() => run.value?.document_stage_matrix || [])
const stageLegends = [
  { status: 'completed', label: '已完成' },
  { status: 'running', label: '运行中' },
  { status: 'failed', label: '失败' },
  { status: 'skipped', label: '已跳过' },
  { status: 'pending', label: '未开始' },
]

// --- Document block selection ---
const selectedDocIndex = ref(null)

const runningDocIndex = computed(() => {
  const docs = documentStageMatrix.value
  if (!docs.length) return null
  const doc = docs.find(d => d.status === 'running')
  return doc?.source_index ?? null
})

const activeDocumentDetail = computed(() => {
  const docs = documentStageMatrix.value
  if (!docs.length) return null

  // User manually selected takes priority
  if (selectedDocIndex.value !== null) {
    return docs.find(d => d.source_index === selectedDocIndex.value) || null
  }

  // Auto-show running document when user hasn't made a choice
  if (runningDocIndex.value !== null) {
    return docs.find(d => d.source_index === runningDocIndex.value) || null
  }

  return null
})

function selectDocument(sourceIndex) {
  selectedDocIndex.value = selectedDocIndex.value === sourceIndex ? null : sourceIndex
}

function documentStatusLabel(doc) {
  const steps = doc.steps || []
  if (!steps.length) return '未开始'
  const hasRunning = steps.some(s => s.status === 'running')
  const hasFailed = steps.some(s => s.status === 'failed')
  const allCompleted = steps.every(s => s.status === 'completed')
  if (allCompleted) return '已完成'
  if (hasRunning) return '运行中'
  if (hasFailed) return '失败'
  const allSkipped = steps.every(s => s.status === 'skipped')
  if (allSkipped) return '已跳过'
  return '未开始'
}
const recommendedCotTypeLabel = computed(() => {
  return run.value?.recommended_cot_type?.display_name || run.value?.target_cot_type?.display_name || '待判定'
})

const failedBatchItems = computed(() => {
  const items = run.value?.batch_summary?.items || []
  return items.filter(item => item.status === 'failed' || item.status === 'skipped')
})

const processingCount = computed(() => {
  if (!run.value) return 0
  const total = run.value.input_count ?? 1
  const success = run.value.success_count ?? 0
  const failed = run.value.failed_count ?? 0
  return Math.max(0, total - success - failed)
})

const overallStatus = computed(() => {
  if (!run.value) return ''
  if (run.value.status === 'completed') return 'success'
  if (run.value.status === 'failed') return 'exception'
  return ''
})

const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewContent = ref('')
const previewFileName = ref('')

async function previewArtifact(path, title) {
  previewDialogVisible.value = true
  previewLoading.value = true
  previewContent.value = ''
  previewFileName.value = title || path
  try {
    const res = await getProfessionalCotArtifact(runId.value, path)
    if (res?.content) {
      previewContent.value = res.content
    } else {
      previewContent.value = JSON.stringify(res, null, 2)
    }
  } catch (err) {
    const detail = err.response?.data?.detail || '读取产物失败'
    previewContent.value = detail
  } finally {
    previewLoading.value = false
  }
}

async function extractErrorDetail(err, fallback) {
  const data = err.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const parsed = JSON.parse(text)
      return parsed.detail || fallback
    } catch {
      return fallback
    }
  }
  return data?.detail || fallback
}

async function downloadExport(type) {
  try {
    const blob = await downloadProfessionalCotExport(runId.value, type)
    const suffix = type === 'jsonl' ? 'jsonl' : 'json'
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${runId.value}_final_samples.${suffix}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    const detail = await extractErrorDetail(err, '下载失败')
    ElMessage.error(detail)
  }
}

function goBack() {
  router.push('/professional-cot-runs')
}

async function handleResume() {
  resumeLoading.value = true
  try {
    await resumeProfessionalCotRun(runId.value)
    ElMessage.success('流水线已恢复运行')
    startPolling()
    await fetchRunDetail()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '恢复失败')
  } finally {
    resumeLoading.value = false
  }
}

async function handlePause() {
  pauseLoading.value = true
  try {
    await pauseProfessionalCotRun(runId.value)
    ElMessage.success('流水线已标记为暂停，将在当前文献完成后停止')
    stopPolling()
    await fetchRunDetail()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '暂停失败')
  } finally {
    pauseLoading.value = false
  }
}

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning', skipped: 'info' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '未开始', paused: '已暂停', skipped: '已跳过' }
  return map[s] || s || '—'
}

function stepDotClass(step) {
  const map = {
    completed: 'dot-completed',
    running: 'dot-running',
    failed: 'dot-failed',
    pending: 'dot-pending',
    skipped: 'dot-skipped',
  }
  return map[step.status] || 'dot-pending'
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchRunDetail()
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.page-container {
  max-width: 1000px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

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

.step-card.step-skipped {
  background: #fafafa;
  border-color: #dcdfe6;
  opacity: 0.86;
}

.document-stage-card :deep(.el-card__header) {
  background: linear-gradient(90deg, #fffaf0 0%, #f8fbff 100%);
}

.matrix-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.matrix-legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  color: #606266;
  font-size: 12px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}

/* Document block grid (similar to chunk-grid in WorkflowDetail) */
.doc-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.doc-block {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  color: #fff;
}

.doc-block:hover {
  transform: scale(1.15);
}

.doc-block.block-selected {
  border-color: #303133;
  transform: scale(1.08);
}

.doc-status-completed {
  background: #67c23a;
  border-color: #67c23a;
}

.doc-status-running {
  background: #409eff;
  border-color: #409eff;
  animation: pulse 1.5s infinite;
}

.doc-status-failed {
  background: #f56c6c;
  border-color: #f56c6c;
}

.doc-status-skipped {
  background: #e6a23c;
  border-color: #e6a23c;
}

.doc-status-pending {
  background: #c0c4cc;
  border-color: #c0c4cc;
  color: #fff;
}

/* Document step detail cards */
.doc-steps-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.doc-step-card {
  padding: 16px 20px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  transition: all 0.3s;
  margin-bottom: 4px;
}

.doc-step-card.step-completed {
  background: #f0f9eb;
  border-color: #b3e19d;
}

.doc-step-card.step-running {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.doc-step-card.step-failed {
  background: #fef0f0;
  border-color: #fbc4c4;
}

.doc-step-card.step-skipped {
  background: #fafafa;
  border-color: #dcdfe6;
  opacity: 0.86;
}

.step-error {
  margin-top: 6px;
}

@media (max-width: 900px) {
  .card-header {
    gap: 10px;
    flex-wrap: wrap;
  }
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

.step-index.index-skipped {
  background: #c0c4cc;
}

.step-card.step-running .step-index {
  background: #409eff;
}

.doc-step-card.step-running .step-index {
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

.step-label {
  color: #606266;
  font-size: 13px;
}

.step-connector {
  width: 2px;
  height: 16px;
  background: #dcdfe6;
  margin-left: 36px;
  border-radius: 1px;
}

.preview-content {
  max-height: 520px;
  overflow-y: auto;
}

.preview-content pre {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
}

.overall-progress {
  padding: 4px 0;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-title {
  font-weight: 600;
  font-size: 14px;
}

.progress-count {
  font-size: 13px;
  color: #666;
}

.batch-progress-label {
  margin-top: 8px;
}

.step-tracker {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.step-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  transition: all 0.3s;
}

.dot-completed {
  background: #67c23a;
}

.dot-running {
  background: #409eff;
  animation: pulse 1.5s infinite;
}

.dot-failed {
  background: #f56c6c;
}

.dot-pending {
  background: #c0c4cc;
}

.dot-skipped {
  background: #dcdfe6;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
