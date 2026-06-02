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
        <el-descriptions-item label="总步骤">{{ workflow.total_steps }}</el-descriptions-item>
        <el-descriptions-item label="已完成">{{ workflow.completed_steps?.length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(workflow.parent_task.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 总进度条 -->
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

    <!-- 步骤列表 -->
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
            <!-- 运行按钮：前一步完成且当前未运行 -->
            <el-button
              v-if="canRunStep(step, index)"
              type="primary"
              size="small"
              @click="handleRunStep(step)"
            >
              <el-icon><VideoPlay /></el-icon>
              运行
            </el-button>

            <!-- 重试按钮：当前步骤失败 -->
            <el-button
              v-if="step.status === 'failed'"
              type="warning"
              size="small"
              @click="handleRunStep(step)"
            >
              <el-icon><RefreshRight /></el-icon>
              重试
            </el-button>

            <!-- 运行中指示 -->
            <span v-if="step.status === 'running'" class="running-indicator">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ step.progress_label || '正在执行...' }}
            </span>

            <!-- 输出文件链接 -->
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

            <!-- 下载输出文件 -->
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

// --- 动态轮询 ---
function scheduleNextPoll() {
  stopPolling()
  if (!workflow.value?.steps?.some(s => s.status === 'running')) {
    return  // 没有运行中的步骤，停止轮询
  }
  // 有运行中的步骤
  const runningStep = workflow.value.steps.find(s => s.status === 'running')
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

// --- 步骤操作 ---
function canRunStep(step, index) {
  // 第一步：没有前一步要求，只要不是 running 就可以
  if (index === 0 && step.status === 'pending') return true
  // 中间步骤：前一步完成 + 当前未运行
  if (step.status === 'pending' && index > 0) {
    const prevStep = workflow.value.steps[index - 1]
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
    // 刷新状态（fetchWorkflowDetail 内部会自动 scheduleNextPoll）
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

// --- 计算属性 ---
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
</style>