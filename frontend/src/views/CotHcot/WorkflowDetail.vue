<template>
  <div class="page-container">
    <!-- 顶部基本信息 -->
    <el-card class="info-card">
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
          <el-tag :type="workflow.parent_task.pipeline_mode === 'hcot' ? 'warning' : 'success'" size="small">
            {{ workflow.parent_task.pipeline_mode === 'hcot' ? 'H-CoT（博士论文）' : 'CoT（研究论文）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模型">{{ workflow.parent_task.model }}</el-descriptions-item>
        <el-descriptions-item label="源文件">
          {{ workflow.parent_task.source_file?.filename || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="总 Chunk">
          {{ isChunkMode ? workflow.total_chunks : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="总步骤">
          {{ isChunkMode ? workflow.total_steps : workflow.total_steps }}
        </el-descriptions-item>
        <el-descriptions-item label="已完成步骤">
          {{ isChunkMode ? workflow.completed_steps : completedCount }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(workflow.parent_task.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- ========== 旧格式兼容：扁平步骤展示 ========== -->
    <template v-if="!isChunkMode">
      <!-- 总进度条（旧格式） -->
      <el-card style="margin-top: 16px" v-if="workflow">
        <div class="overall-progress">
          <div class="progress-header">
            <span class="progress-title">流水线总进度</span>
            <span class="progress-count">{{ completedCount }}/{{ workflow.total_steps }} 步</span>
          </div>
          <el-progress
            :percentage="overallPercentage"
            :status="overallStatus"
            :stroke-width="20"
          />
          <div class="step-tracker">
            <div
              v-for="step in workflow.steps"
              :key="step.step_name"
              class="step-dot"
              :class="stepDotClass(step)"
              :title="step.display_name"
            ></div>
          </div>
        </div>
      </el-card>

      <!-- 步骤列表（旧格式） -->
      <el-card style="margin-top: 16px" v-loading="loading">
        <template #header>
          <span>流水线步骤</span>
        </template>

        <div class="steps-container" v-if="workflow">
          <div
            v-for="(step, index) in workflow.steps"
            :key="step.step_name"
            class="step-card"
            :class="{ 'step-completed': step.status === 'completed', 'step-running': step.status === 'running', 'step-failed': step.status === 'failed' }"
          >
            <!-- 步骤头部 -->
            <div class="step-header">
              <div class="step-index" :class="{ 'index-completed': step.status === 'completed', 'index-failed': step.status === 'failed' }">
                {{ step.status === 'completed' ? '✓' : (index + 1) }}
              </div>
              <div class="step-info">
                <div class="step-name">{{ step.display_name }}</div>
                <div class="step-badges">
                  <el-tag :type="statusTagType(step.status)" size="small">
                    {{ statusLabel(step.status) }}
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
                v-if="canRunStep(step, index)"
                type="primary"
                size="small"
                @click="handleRunStep(step)"
              >
                <el-icon><VideoPlay /></el-icon>
                运行
              </el-button>

              <el-button
                v-if="step.status === 'failed'"
                type="warning"
                size="small"
                @click="handleRunStep(step)"
              >
                <el-icon><RefreshRight /></el-icon>
                重试
              </el-button>

              <span v-if="step.status === 'running'" class="running-indicator">
                <el-icon class="is-loading"><Loading /></el-icon>
                {{ step.progress_label || '正在执行...' }}
              </span>

              <el-button
                v-if="step.output_file_id"
                type="success"
                size="small"
                link
                @click="viewOutputFile(step)"
              >
                <el-icon><Document /></el-icon>
                {{ step.output_filename }}
              </el-button>

              <el-button
                v-if="step.output_file_id"
                size="small"
                link
                @click="downloadOutputFile(step)"
              >
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </div>

            <!-- 步骤间连接线 -->
            <div v-if="index < workflow.steps.length - 1" class="step-connector"></div>
          </div>
        </div>
      </el-card>
    </template>

    <!-- ========== 新格式：Chunk 分组展示 ========== -->
    <template v-if="isChunkMode">
      <!-- 总进度条（Chunk 模式） -->
      <el-card style="margin-top: 16px" v-if="workflow">
        <div class="overall-progress">
          <div class="progress-header">
            <span class="progress-title">流水线总进度</span>
            <span class="progress-count">
              已完成 {{ completedChunkCount }}/{{ workflow.total_chunks }} chunk
            </span>
          </div>
          <el-progress
            :percentage="chunkOverallPercentage"
            :status="overallStatus"
            :stroke-width="20"
          />
        </div>
      </el-card>

      <!-- Chunk 进度概览方块 -->
      <el-card style="margin-top: 16px">
        <template #header>
          <span>Chunk 进度概览</span>
        </template>
        <div class="chunk-grid">
          <div
            v-for="chunk in visibleChunks"
            :key="chunk.chunk_index"
            class="chunk-block"
            :class="chunkBlockClass(chunk)"
            @click="selectChunk(chunk.chunk_index)"
            :title="`Chunk ${chunk.chunk_index + 1}: ${chunkStatusLabel(chunk)}`"
          >
            {{ chunk.chunk_index + 1 }}
          </div>
          <span v-if="workflow.total_chunks > 50" class="more-chunks">
            还有 {{ workflow.total_chunks - 50 }} 个 chunk...
          </span>
        </div>
      </el-card>

      <!-- 当前运行的 chunk 详情 -->
      <el-card style="margin-top: 16px" v-if="activeChunkDetail">
        <template #header>
          <span>Chunk {{ activeChunk.chunk_index + 1 }} — {{ activeChunkStatusLabel }}</span>
        </template>
        <div class="steps-container">
          <div
            v-for="(step, index) in activeChunkDetail.steps"
            :key="step.step_name"
            class="step-card"
            :class="{ 'step-completed': step.status === 'completed', 'step-running': step.status === 'running', 'step-failed': step.status === 'failed' }"
          >
            <!-- 步骤头部 -->
            <div class="step-header">
              <div class="step-index" :class="{ 'index-completed': step.status === 'completed', 'index-failed': step.status === 'failed' }">
                {{ step.status === 'completed' ? '✓' : (index + 1) }}
              </div>
              <div class="step-info">
                <div class="step-name">{{ step.display_name }}</div>
                <div class="step-badges">
                  <el-tag :type="statusTagType(step.status)" size="small">
                    {{ statusLabel(step.status) }}
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
                v-if="canRunChunkStep(step, index)"
                type="primary"
                size="small"
                @click="handleRunStep(step)"
              >
                <el-icon><VideoPlay /></el-icon>
                运行
              </el-button>

              <el-button
                v-if="step.status === 'failed'"
                type="warning"
                size="small"
                @click="handleRunStep(step)"
              >
                <el-icon><RefreshRight /></el-icon>
                重试
              </el-button>

              <span v-if="step.status === 'running'" class="running-indicator">
                <el-icon class="is-loading"><Loading /></el-icon>
                {{ step.progress_label || '正在执行...' }}
              </span>

              <el-button
                v-if="step.output_file_id"
                type="success"
                size="small"
                link
                @click="viewOutputFile(step)"
              >
                <el-icon><Document /></el-icon>
                {{ step.output_filename }}
              </el-button>

              <el-button
                v-if="step.output_file_id"
                size="small"
                link
                @click="downloadOutputFile(step)"
              >
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </div>

            <!-- 步骤间连接线 -->
            <div v-if="index < activeChunkDetail.steps.length - 1" class="step-connector"></div>
          </div>
        </div>
      </el-card>

      <!-- 已完成 chunk 列表（折叠） -->
      <el-card style="margin-top: 16px" v-if="completedChunkCount > 0">
        <template #header>
          <span>已完成的 Chunk（{{ completedChunkCount }}/{{ workflow.total_chunks }}）</span>
        </template>
        <el-collapse>
          <el-collapse-item
            v-for="chunk in completedChunks"
            :key="chunk.chunk_index"
            :title="`Chunk ${chunk.chunk_index + 1}`"
          >
            <div class="completed-chunk-summary">
              <span v-for="step in chunk.steps" :key="step.step_name" class="step-mini-tag" :class="step.status === 'completed' ? 'tag-success' : ''">
                {{ step.display_name }}
              </span>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 失败的 chunk 列表 -->
      <el-card style="margin-top: 16px" v-if="failedChunks.length > 0">
        <template #header>
          <span style="color: #f56c6c">失败的 Chunk（{{ failedChunks.length }}）</span>
        </template>
        <el-collapse>
          <el-collapse-item
            v-for="chunk in failedChunks"
            :key="chunk.chunk_index"
            :title="`Chunk ${chunk.chunk_index + 1}`"
          >
            <div class="steps-container">
              <div
                v-for="(step, index) in chunk.steps"
                :key="step.step_name"
                class="step-card"
                :class="{ 'step-completed': step.status === 'completed', 'step-running': step.status === 'running', 'step-failed': step.status === 'failed' }"
              >
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
                    </div>
                  </div>
                </div>
                <div class="step-actions">
                  <el-button
                    v-if="step.status === 'failed'"
                    type="warning"
                    size="small"
                    @click="handleRunStep(step)"
                  >
                    <el-icon><RefreshRight /></el-icon>
                    重试
                  </el-button>
                  <el-button
                    v-if="step.output_file_id"
                    type="success"
                    size="small"
                    link
                    @click="viewOutputFile(step)"
                  >
                    <el-icon><Document /></el-icon>
                    {{ step.output_filename }}
                  </el-button>
                  <el-button
                    v-if="step.output_file_id"
                    size="small"
                    link
                    @click="downloadOutputFile(step)"
                  >
                    <el-icon><Download /></el-icon>
                    下载
                  </el-button>
                </div>
                <div v-if="index < chunk.steps.length - 1" class="step-connector"></div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
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
import {
  ArrowLeft, VideoPlay, RefreshRight, Loading, Document, Download, Promotion,
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

async function fetchWorkflowDetail() {
  try {
    const res = await getCothcotWorkflowDetail(taskId.value)
    workflow.value = res
    // 自动调整轮询
    scheduleNextPoll()
  } catch (err) {
    const detail = err.response?.data?.detail || '获取流水线详情失败'
    ElMessage.error(detail)
  }
}

// --- 数据格式判断 ---
const isChunkMode = computed(() => {
  return workflow.value?.chunks && Array.isArray(workflow.value.chunks)
})

// --- Chunk 计算属性 ---
const completedChunkCount = computed(() => {
  if (!workflow.value?.chunks) return 0
  return workflow.value.chunks.filter(c =>
    c.steps.every(s => s.status === 'completed')
  ).length
})

const runningChunkIndex = computed(() => {
  if (!workflow.value?.chunks) return null
  const chunk = workflow.value.chunks.find(c =>
    c.steps.some(s => s.status === 'running')
  )
  return chunk?.chunk_index ?? null
})

const failedChunks = computed(() => {
  if (!workflow.value?.chunks) return []
  return workflow.value.chunks.filter(c =>
    c.steps.some(s => s.status === 'failed')
  )
})

const completedChunks = computed(() => {
  if (!workflow.value?.chunks) return []
  return workflow.value.chunks.filter(c =>
    c.steps.every(s => s.status === 'completed')
  )
})

const visibleChunks = computed(() => {
  if (!workflow.value?.chunks) return []
  const limit = 50
  return workflow.value.chunks.slice(0, limit)
})

// activeChunkDetail：优先显示正在运行的 chunk，否则显示用户点击选择的 chunk
const activeChunkDetail = computed(() => {
  if (!workflow.value?.chunks) return null
  // 有正在运行的 chunk 时，自动展示它
  if (runningChunkIndex.value !== null) {
    return workflow.value.chunks.find(c => c.chunk_index === runningChunkIndex.value)
  }
  // 用户手动点击选择的 chunk
  if (selectedChunkIndex.value !== null) {
    return workflow.value.chunks.find(c => c.chunk_index === selectedChunkIndex.value)
  }
  return null
})

const activeChunk = computed(() => activeChunkDetail.value)

const activeChunkStatusLabel = computed(() => {
  if (!activeChunkDetail.value) return ''
  return chunkStatusLabel(activeChunkDetail.value)
})

const chunkOverallPercentage = computed(() => {
  if (!workflow.value || !workflow.value.total_chunks) return 0
  return Math.round((completedChunkCount.value / workflow.value.total_chunks) * 100)
})

// --- Chunk 辅助函数 ---
function chunkBlockClass(chunk) {
  const hasRunning = chunk.steps.some(s => s.status === 'running')
  const hasFailed = chunk.steps.some(s => s.status === 'failed')
  const allCompleted = chunk.steps.every(s => s.status === 'completed')
  if (allCompleted) return 'block-completed'
  if (hasRunning) return 'block-running'
  if (hasFailed) return 'block-failed'
  return 'block-pending'
}

function chunkStatusLabel(chunk) {
  const hasRunning = chunk.steps.some(s => s.status === 'running')
  const hasFailed = chunk.steps.some(s => s.status === 'failed')
  const allCompleted = chunk.steps.every(s => s.status === 'completed')
  if (allCompleted) return '已完成'
  if (hasRunning) return '运行中'
  if (hasFailed) return '失败'
  return '未开始'
}

function selectChunk(index) {
  // 如果点击的是当前正在运行的 chunk，不做切换
  if (index === runningChunkIndex.value) return
  // 取消选择同一 chunk（toggle）
  if (selectedChunkIndex.value === index) {
    selectedChunkIndex.value = null
  } else {
    selectedChunkIndex.value = index
  }
}

// --- 动态轮询 ---
function scheduleNextPoll() {
  stopPolling()
  if (isChunkMode.value) {
    // Chunk 模式：检查是否有任何 chunk 中有运行中的步骤
    if (!workflow.value?.chunks?.some(c => c.steps.some(s => s.status === 'running'))) {
      return
    }
    const runningChunk = workflow.value.chunks.find(c => c.steps.some(s => s.status === 'running'))
    const runningStep = runningChunk?.steps.find(s => s.status === 'running')
    const interval = (runningStep?.progress_current > 10) ? 5000 : 2000
    pollTimer = setTimeout(() => {
      fetchWorkflowDetail()
    }, interval)
  } else {
    // 旧格式
    if (!workflow.value?.steps?.some(s => s.status === 'running')) {
      return
    }
    const runningStep = workflow.value.steps.find(s => s.status === 'running')
    const interval = (runningStep?.progress_current > 10) ? 5000 : 2000
    pollTimer = setTimeout(() => {
      fetchWorkflowDetail()
    }, interval)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

// --- 步骤操作（旧格式） ---
function canRunStep(step, index) {
  if (index === 0 && step.status === 'pending') return true
  if (step.status === 'pending' && index > 0) {
    const prevStep = workflow.value.steps[index - 1]
    return prevStep.status === 'completed'
  }
  return false
}

// --- 步骤操作（Chunk 模式） ---
function canRunChunkStep(step, index) {
  if (index === 0 && step.status === 'pending') return true
  if (step.status === 'pending' && index > 0) {
    const steps = activeChunkDetail.value.steps
    const prevStep = steps[index - 1]
    return prevStep.status === 'completed'
  }
  return false
}

async function handleRunStep(step) {
  try {
    const res = await runCothcotStep({
      parent_task_id: taskId.value,
      step_name: step.step_name,
    })
    ElMessage.success(`步骤 '${step.display_name}' 已启动`)
    await fetchWorkflowDetail()
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

function downloadOutputFile(step) {
  downloadManagedFile(step.output_file_id)
}

function downloadPreviewFile() {
  if (previewFileId.value) {
    downloadManagedFile(previewFileId.value)
  }
}

// --- 计算属性（旧格式兼容） ---
const completedCount = computed(() => {
  if (!workflow.value) return 0
  return workflow.value.steps.filter(s => s.status === 'completed').length
})

const overallPercentage = computed(() => {
  if (!workflow.value) return 0
  const completed = completedCount.value
  return Math.round((completed / workflow.value.total_steps) * 100)
})

const overallStatus = computed(() => {
  if (!workflow.value) return ''
  const parentStatus = workflow.value.parent_task.status
  if (parentStatus === 'completed') return 'success'
  if (parentStatus === 'failed') return 'exception'
  return ''
})

const canAutoRun = computed(() => {
  if (!workflow.value) return false
  if (isChunkMode.value) {
    const hasRunning = workflow.value.chunks.some(c => c.steps.some(s => s.status === 'running'))
    const hasFailed = workflow.value.chunks.some(c => c.steps.some(s => s.status === 'failed'))
    const allCompleted = workflow.value.chunks.every(c => c.steps.every(s => s.status === 'completed'))
    return !hasRunning && !allCompleted && !hasFailed
  }
  const hasRunning = workflow.value.steps.some(s => s.status === 'running')
  const hasFailed = workflow.value.steps.some(s => s.status === 'failed')
  const allCompleted = workflow.value.steps.every(s => s.status === 'completed')
  return !hasRunning && !allCompleted && !hasFailed
})

function stepDotClass(step) {
  const map = {
    completed: 'dot-completed',
    running: 'dot-running',
    failed: 'dot-failed',
    pending: 'dot-pending',
  }
  return map[step.status] || 'dot-pending'
}

// --- 辅助函数 ---
function goBack() {
  router.push('/cot-hcot-workflows')
}

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '未开始', paused: '已暂停' }
  return map[s] || s
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

/* 旧格式步骤圆点 */
.step-tracker {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: center;
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

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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
}

.chunk-block:hover {
  transform: scale(1.15);
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
</style>