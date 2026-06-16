<template>
  <div class="page-container">
    <!-- 顶部基本信息 -->
    <el-card class="info-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>{{ workflow?.parent_task?.pipeline_name || '流水线详情' }}</span>
          <div>
            <el-button v-if="canAutoRun" type="success" @click="handleAutoRun" style="margin-right: 12px">
              <el-icon><Promotion /></el-icon>
              一键运行全部
            </el-button>
            <el-tag :type="statusTagType(workflow?.parent_task?.status)" size="large">
              {{ statusLabel(workflow?.parent_task?.status) }}
            </el-tag>
            <el-button @click="goBack" style="margin-left: 12px">
              <el-icon><ArrowLeft /></el-icon>
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border v-if="workflow">
        <el-descriptions-item label="模式">
          <el-tag :type="isHcotMode ? 'warning' : 'success'" size="small">
            {{ isHcotMode ? 'H-CoT（博士论文）' : 'CoT（研究论文）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模型">{{ workflow.parent_task?.model || '—' }}</el-descriptions-item>
        <el-descriptions-item label="源文件">
          {{ workflow.parent_task?.source_file?.filename || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="总分段">{{ workflow.total_chunks || 0 }}</el-descriptions-item>
        <el-descriptions-item label="总步骤">{{ displayTotalSteps }}</el-descriptions-item>
        <el-descriptions-item label="已完成步骤">{{ workflow.completed_steps || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(workflow.parent_task?.created_at) }}</el-descriptions-item>

      </el-descriptions>
    </el-card>

    <!-- 总进度条 -->
    <el-card style="margin-top: 16px" v-if="workflow">
      <div class="overall-progress">
        <div class="progress-header">
          <span class="progress-title">流水线总进度</span>
          <span class="progress-count">{{ workflow.completed_steps || 0 }}/{{ displayTotalSteps }} 步</span>

        </div>
        <el-progress
          :percentage="overallPercentage"
          :status="overallStatus"
          :stroke-width="20"
        />
      </div>
    </el-card>

    <!-- 阶段渲染：使用 backend workflow.phases -->
    <template v-for="phase in phases" :key="phase.phase_name">
      <!-- phase_name=per_chunk：chunk grid，点击 chunk 展示 fact_card_gen 详情 -->
      <el-card v-if="phase.phase_name === 'per_chunk'" class="phase-card">
        <template #header>
          <div class="phase-header">
            <el-tag type="warning" size="small" style="margin-right: 8px">分段级</el-tag>
            <span>{{ phase.label || '分段事实卡生成' }}</span>
          </div>
        </template>

        <div v-if="phase.chunks?.length" class="chunk-grid">
          <div
            v-for="chunk in visibleChunksForPhase(phase)"
            :key="chunk.chunk_index"
            class="chunk-block"
            :class="[chunkBlockClass(chunk), { 'block-selected': activeChunkDetail?.chunk_index === chunk.chunk_index }]"
            @click="selectChunk(chunk.chunk_index)"
            :title="`Chunk ${chunk.chunk_index + 1}: ${chunkStatusLabel(chunk)}`"
          >
            {{ chunk.chunk_index + 1 }}
          </div>
          <span v-if="phase.chunks.length > chunkVisibleLimit" class="more-chunks">
            还有 {{ phase.chunks.length - chunkVisibleLimit }} 个分段...
          </span>
        </div>
        <el-empty v-else description="暂无分段" />

        <div style="margin-top: 16px" v-if="activeChunkDetail">
          <el-divider content-position="left">
            分段 {{ activeChunkDetail.chunk_index + 1 }} — {{ chunkStatusLabel(activeChunkDetail) }}
          </el-divider>
          <div class="steps-container">
            <template
              v-for="(step, index) in normalizedChunkSteps(activeChunkDetail)"
              :key="`${activeChunkDetail.chunk_index}-${step.step_name}`"
            >
              <step-card
                :step="step"
                :index="index"
                :total="normalizedChunkSteps(activeChunkDetail).length"
                :can-run="canRunStepInList(step, index, normalizedChunkSteps(activeChunkDetail))"
                @run="handleRunStep(step)"
                @view-file="viewOutputFile"
              />
            </template>
          </div>
        </div>
      </el-card>

      <!-- phase_name=document：全文级 flat step list -->
      <el-card v-else-if="phase.phase_name === 'document'" class="phase-card">
        <template #header>
          <div class="phase-header">
            <el-tag type="primary" size="small" style="margin-right: 8px">文档级</el-tag>
            <span>{{ phase.label || '全文级处理' }}</span>
          </div>
        </template>

        <div v-if="phase.steps?.length" class="steps-container">
          <template v-for="(step, index) in phase.steps" :key="step.step_name">
            <step-card
              :step="step"
              :index="index"
              :total="phase.steps.length"
              :can-run="canRunStepInList(step, index, phase.steps)"
              @run="handleRunStep(step)"
              @view-file="viewOutputFile"
            />
          </template>
        </div>
        <el-empty v-else description="暂无步骤" />
      </el-card>

      <!-- phase_name=per_l0：H-CoT 总问题分组 -->
      <el-card
        v-else-if="phase.phase_name === 'per_l0' && isHcotMode"
        class="phase-card"
      >
        <template #header>
          <div class="phase-header">
            <el-tag type="danger" size="small" style="margin-right: 8px">per-L0</el-tag>
            <span>{{ phase.label || '推理树构建' }}</span>
          </div>
        </template>

        <el-collapse v-if="phase.l0_questions?.length" v-model="expandedL0Questions">
          <el-collapse-item
            v-for="l0q in phase.l0_questions"
            :key="l0q.l0_question_index"
            :name="l0q.l0_question_index"
          >
            <template #title>
              <div class="l0-question-title">
                <span class="l0-index-badge">总问题 #{{ l0q.l0_question_index + 1 }}</span>
                <el-tag :type="l0GroupStatusType(l0q)" size="small" style="margin-left: 8px">
                  {{ l0GroupStatusLabel(l0q) }}
                </el-tag>
              </div>
            </template>

            <div class="steps-container l0-steps-container">
              <template
                v-for="(step, index) in normalizedL0Steps(l0q)"
                :key="`${l0q.l0_question_index}-${step.step_name}`"
              >
                <step-card
                  :step="step"
                  :index="index"
                  :total="normalizedL0Steps(l0q).length"
                  :can-run="canRunStepInList(step, index, normalizedL0Steps(l0q))"
                  @run="handleRunStep(step)"
                  @view-file="viewOutputFile"
                />
              </template>
            </div>
          </el-collapse-item>
        </el-collapse>
        <el-empty v-else description="暂无总问题，请先完成 L0 生成" />
      </el-card>

      <!-- phase_name=document_final：最终文档级 flat step list -->
      <el-card v-else-if="phase.phase_name === 'document_final'" class="phase-card">
        <template #header>
          <div class="phase-header">
            <el-tag type="success" size="small" style="margin-right: 8px">文档级</el-tag>
            <span>{{ phase.label || '质检与导出' }}</span>
          </div>
        </template>

        <div v-if="phase.steps?.length" class="steps-container">
          <template v-for="(step, index) in phase.steps" :key="step.step_name">
            <step-card
              :step="step"
              :index="index"
              :total="phase.steps.length"
              :can-run="canRunStepInList(step, index, phase.steps)"
              @run="handleRunStep(step)"
              @view-file="viewOutputFile"
            />
          </template>
        </div>
        <el-empty v-else description="暂无步骤" />
      </el-card>
    </template>


    <!-- 输出文件预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewFileName"
      width="700px"
      destroy-on-close
    >
      <div v-loading="previewLoading" class="preview-content">
        <pre v-if="previewContent">{{ previewContent }}</pre>
        <el-empty v-else description="文件内容为空" />
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="downloadPreviewFile">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import StepCard from './StepCard.vue'
import {
  ArrowLeft, Promotion,
} from '@element-plus/icons-vue'
import {
  getCothcotWorkflowDetail,
  runCothcotStep,
  autoContinueCothcotPipeline,
  getManagedFileContent,
  downloadManagedFile,
} from '../../api'

const router = useRouter()
const route = useRoute()

const taskId = computed(() => parseInt(route.params.id))

// --- 数据 ---
const loading = ref(false)
const workflow = ref(null)
let pollTimer = null

// --- Chunk 选择状态 ---
const selectedChunkIndex = ref(null)
const chunkVisibleLimit = 50

// --- L0 折叠面板 ---
const expandedL0Questions = ref([])
const initializedL0Questions = ref(false)


async function fetchWorkflowDetail() {
  loading.value = !workflow.value
  try {
    const res = await getCothcotWorkflowDetail(taskId.value)
    workflow.value = res
    ensureSelectedChunkExists()
    initializeL0Collapse(res)
    scheduleNextPoll()
  } catch (err) {
    const detail = err.response?.data?.detail || '获取流水线详情失败'
    ElMessage.error(detail)
  } finally {
    loading.value = false
  }
}

function initializeL0Collapse(data) {
  const perL0 = (data?.phases || []).find(p => p.phase_name === 'per_l0')
  const l0Indexes = (perL0?.l0_questions || []).map(l0q => l0q.l0_question_index)
  if (!l0Indexes.length) return

  if (!initializedL0Questions.value) {
    expandedL0Questions.value = l0Indexes
    initializedL0Questions.value = true
    return
  }

  // 轮询刷新时保留用户折叠状态，只把新出现的 L0 问题追加进去。
  const existing = new Set(expandedL0Questions.value)
  for (const index of l0Indexes) {
    if (!existing.has(index)) expandedL0Questions.value.push(index)
  }
}

// --- Phase 计算属性 ---
const phases = computed(() => workflow.value?.phases || [])

const perChunkPhase = computed(() => {
  return phases.value.find(p => p.phase_name === 'per_chunk') || null
})

const isHcotMode = computed(() => workflow.value?.parent_task?.pipeline_mode === 'hcot')

// --- Chunk 计算属性 ---
const runningChunkIndex = computed(() => {
  if (!perChunkPhase.value?.chunks) return null
  const chunk = perChunkPhase.value.chunks.find(c =>
    (c.steps || []).some(s => s.status === 'running')
  )
  return chunk?.chunk_index ?? null
})

const activeChunkDetail = computed(() => {
  const chunks = perChunkPhase.value?.chunks || []
  if (!chunks.length) return null

  // 有正在运行的 chunk 时，自动展示它。
  if (runningChunkIndex.value !== null) {
    return chunks.find(c => c.chunk_index === runningChunkIndex.value) || null
  }

  // 用户手动点击选择的 chunk。
  if (selectedChunkIndex.value !== null) {
    return chunks.find(c => c.chunk_index === selectedChunkIndex.value) || null
  }

  return null
})

function visibleChunksForPhase(phase) {
  return (phase?.chunks || []).slice(0, chunkVisibleLimit)
}

function ensureSelectedChunkExists() {
  if (selectedChunkIndex.value === null) return
  const chunks = perChunkPhase.value?.chunks || []
  if (!chunks.some(c => c.chunk_index === selectedChunkIndex.value)) {
    selectedChunkIndex.value = null
  }
}

function normalizedChunkSteps(chunk) {
  return (chunk?.steps || []).map(step => ({
    ...step,
    chunk_index: step.chunk_index ?? chunk.chunk_index,
  }))
}

function normalizedL0Steps(l0q) {
  return (l0q?.steps || []).map(step => ({
    ...step,
    l0_question_index: step.l0_question_index ?? l0q.l0_question_index,
  }))
}

// --- 总进度 ---
const displayTotalSteps = computed(() => {
  // H-CoT 固定 13 步：chunk数个事实卡 + 合并 + 数值抽象 + L0 + L1 + L2 + L2_CoT + L1_CoT + L0_CoT + 质检 + 导出
  // CoT 固定 7 步：chunk数个事实卡 + 合并 + 数值抽象 + 问题生成 + CoT生成 + 质检 + 导出
  if (!workflow.value) return 0
  const chunks = workflow.value.total_chunks || 1
  return isHcotMode.value ? (chunks + 10) : (chunks + 4)
})

const overallPercentage = computed(() => {
  if (!workflow.value) return 0
  const total = displayTotalSteps.value
  const completed = workflow.value.completed_steps || 0
  if (total === 0) return 0
  return Math.min(100, Math.round((completed / total) * 100))
})

const overallStatus = computed(() => {
  if (!workflow.value) return ''
  const parentStatus = workflow.value.parent_task?.status
  if (parentStatus === 'completed') return 'success'
  if (parentStatus === 'failed') return 'exception'
  return ''
})

// --- canAutoRun ---
const canAutoRun = computed(() => {
  if (!workflow.value) return false
  const parentStatus = workflow.value.parent_task?.status
  return !hasAnyRunning() && parentStatus !== 'completed' && !hasAnyFailed()
})

// --- 全局扫描：基于 phases 检查 chunk/document/l0 所有步骤 ---
function collectAllSteps() {
  const result = []
  for (const phase of phases.value) {
    for (const chunk of phase.chunks || []) {
      result.push(...normalizedChunkSteps(chunk))
    }
    result.push(...(phase.steps || []))
    for (const l0q of phase.l0_questions || []) {
      result.push(...normalizedL0Steps(l0q))
    }
  }
  return result
}

function hasAnyRunning() {
  return collectAllSteps().some(step => step.status === 'running')
}

function hasAnyFailed() {
  return collectAllSteps().some(step => step.status === 'failed')
}

function getFirstRunningStep() {
  return collectAllSteps().find(step => step.status === 'running') || null
}

// --- 动态轮询 ---
function scheduleNextPoll() {
  stopPolling()
  if (!hasAnyRunning()) return

  const runningStep = getFirstRunningStep()

  const interval = (runningStep?.progress_current > 10) ? 5000 : 2000
  pollTimer = setTimeout(() => {
    fetchWorkflowDetail()
  }, interval)
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

// --- 步骤运行逻辑 ---
function canRunStepInList(step, index, steps) {
  if (step.status === 'running' || step.status === 'completed') return false
  if (step.status === 'failed') return true

  if (index === 0 && step.status === 'pending') return true
  // 中间步骤：前一步完成 + 当前未运行
  if (step.status === 'pending' && index > 0) {
    const prevStep = steps[index - 1]
    return prevStep?.status === 'completed'

  }
  return false
}

async function handleRunStep(step) {
  try {
    const params = {
      parent_task_id: taskId.value,
      step_name: step.step_name,
    }
    if (step.l0_question_index != null) {
      params.l0_question_index = step.l0_question_index
    }
    const res = await runCothcotStep(params)
    ElMessage.success(`步骤 '${step.display_name}' 已启动`)
    // 刷新状态（fetchWorkflowDetail 内部会自动 scheduleNextPoll）
    await fetchWorkflowDetail()
    return res
  } catch (err) {
    const detail = err.response?.data?.detail || '启动步骤失败'
    ElMessage.error(detail)
  }
}

async function handleAutoRun() {
  try {
    const res = await autoContinueCothcotPipeline(taskId.value)
    ElMessage.success(res.message || '一键运行已启动')
    await fetchWorkflowDetail()
  } catch (err) {
    const detail = err.response?.data?.detail || '启动一键运行失败'
    ElMessage.error(detail)
  }
}

// --- Chunk 辅助函数 ---
function chunkBlockClass(chunk) {
  const steps = chunk.steps || []
  if (!steps.length) return 'block-pending'
  const hasRunning = steps.some(s => s.status === 'running')
  const hasFailed = steps.some(s => s.status === 'failed')
  const allCompleted = steps.every(s => s.status === 'completed')
  if (allCompleted) return 'block-completed'
  if (hasRunning) return 'block-running'
  if (hasFailed) return 'block-failed'
  return 'block-pending'
}

function chunkStatusLabel(chunk) {
  const steps = chunk.steps || []
  if (!steps.length) return '未开始'
  const hasRunning = steps.some(s => s.status === 'running')
  const hasFailed = steps.some(s => s.status === 'failed')
  const allCompleted = steps.every(s => s.status === 'completed')
  if (allCompleted) return '已完成'
  if (hasRunning) return '运行中'
  if (hasFailed) return '失败'
  return '未开始'
}

function selectChunk(index) {
  // 如果点击的是当前正在运行的 chunk，不做切换；运行中 chunk 会自动展示。
  if (index === runningChunkIndex.value) return
  selectedChunkIndex.value = selectedChunkIndex.value === index ? null : index
}

// --- L0 问题组辅助 ---
function l0GroupStatusLabel(l0q) {
  const steps = normalizedL0Steps(l0q)
  if (!steps.length) return '未开始'
  const hasRunning = steps.some(s => s.status === 'running')
  const hasFailed = steps.some(s => s.status === 'failed')
  const allCompleted = steps.every(s => s.status === 'completed')
  if (allCompleted) return '已完成'
  if (hasRunning) return '运行中'
  if (hasFailed) return '失败'
  return '未开始'
}

function l0GroupStatusType(l0q) {
  const steps = normalizedL0Steps(l0q)
  if (!steps.length) return 'info'
  const hasRunning = steps.some(s => s.status === 'running')
  const hasFailed = steps.some(s => s.status === 'failed')
  const allCompleted = steps.every(s => s.status === 'completed')
  if (allCompleted) return 'success'
  if (hasRunning) return 'primary'
  if (hasFailed) return 'danger'
  return 'info'
}

// --- 文件预览 ---
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewContent = ref('')
const previewFileName = ref('')
const previewFileId = ref(null)

function viewOutputFile(step) {
  previewFileId.value = step.output_file_id
  previewFileName.value = step.output_filename || `步骤 ${step.step_name} 输出`
  previewDialogVisible.value = true
  fetchFileContent(step.output_file_id)
}

async function fetchFileContent(fileId) {
  previewLoading.value = true
  previewContent.value = ''
  try {
    const res = await getManagedFileContent(fileId, { limit: 200 })
    if (typeof res === 'string') {
      try {
        const parsed = JSON.parse(res)
        previewContent.value = JSON.stringify(parsed, null, 2)
      } catch {
        previewContent.value = res
      }
    } else {
      previewContent.value = JSON.stringify(res, null, 2)
    }
  } catch (err) {
    previewContent.value = '文件内容获取失败'
  } finally {
    previewLoading.value = false
  }
}

async function downloadPreviewFile() {
  if (!previewFileId.value) return
  try {
    const blob = await downloadManagedFile(previewFileId.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = previewFileName.value || '输出文件.json'
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


// --- 辅助函数 ---
function goBack() {
  router.push('/app/cot-hcot-workflows')
}

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '未开始', paused: '已暂停' }
  return map[s] || s || '未知'
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

// --- 生命周期 ---
onMounted(async () => {
  await fetchWorkflowDetail()
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

.phase-card {
  margin-top: 16px;
}

.phase-header {
  display: flex;
  align-items: center;
}

/* 步骤卡片 */
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

.preview-content {
  max-height: 500px;
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

/* 总进度条 */
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

/* Chunk 进度概览方块 */
.chunk-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chunk-block {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.chunk-block:hover {
  transform: scale(1.15);
}

.chunk-block.block-selected {
  border-color: #303133;
  transform: scale(1.08);
}

.block-completed { background: #67c23a; color: #fff; }
.block-running { background: #409eff; color: #fff; animation: pulse 1.5s infinite; }
.block-failed { background: #f56c6c; color: #fff; }
.block-pending { background: #c0c4cc; color: #fff; }

.more-chunks {
  font-size: 12px;
  color: #999;
  line-height: 28px;
}

/* L0 问题组 */
.l0-question-title {
  display: flex;
  align-items: center;
}

.l0-index-badge {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.l0-steps-container {
  padding: 8px 0;
}

/* 已完成 chunk 摘要 */
.completed-chunk-summary {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.step-mini-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f5f7fa;
}

.step-mini-tag.tag-success {
  background: #f0f9eb;
  color: #67c23a;

}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>

