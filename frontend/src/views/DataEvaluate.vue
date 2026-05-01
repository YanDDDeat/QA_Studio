<template>
  <div class="page-container">
    <h2>数据评估</h2>

    <!-- Form section -->
    <el-card class="form-card">
      <template #header>
        <span class="card-title">评估配置</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="form" label-width="100px" :disabled="taskRunning">
            <el-form-item label="选择文件">
              <FileSelector v-model="form.file_id" :file-options="fileOptions" :disabled="taskRunning" @upload-success="onFileUploadSuccess" />
            </el-form-item>

            <el-form-item label="选择Prompt">
              <el-select v-model="form.prompt_id" placeholder="请选择数据评估阶段的Prompt" style="width: 100%" filterable>
                <el-option v-for="p in promptOptions" :key="p.id" :label="`v${p.version}`" :value="p.id">
                  <span>v{{ p.version }}</span>
                  <span style="float: right; color: #909399; font-size: 13px">
                    {{ p.content.substring(0, 50) }}{{ p.content.length > 50 ? '...' : '' }}
                  </span>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="LLM配置">
              <el-select
                v-model="selectedLLMConfigId"
                placeholder="选择LLM配置"
                style="width: 100%"
                filterable
                @change="handleLLMConfigChange"
              >
                <el-option
                  v-for="cfg in llmConfigs"
                  :key="cfg.id"
                  :label="cfg.name + (cfg.is_global ? ' (全局)' : ' (我的)')"
                  :value="cfg.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="选择模型">
              <el-select v-model="form.model" placeholder="请选择LLM模型" style="width: 100%" :disabled="!selectedLLMConfigId">
                <el-option
                  v-for="m in currentModelOptions"
                  :key="m"
                  :label="m"
                  :value="m"
                />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="startLoading"
                :disabled="!canStart"
                @click="handleStart"
              >
                开始评估
              </el-button>
              <el-button
                v-if="canRetry"
                type="warning"
                :loading="startLoading"
                @click="handleRetry"
              >
                重试失败任务
              </el-button>
            </el-form-item>
          </el-form>
        </div>
        <div class="config-preview">
          <PromptPreview :version="drawerVersion" :content="drawerContent" :time-label="formatTime(drawerCreatedAt)" :content-changed="drawerContentChanged" :next-version="nextVersion" :save-loading="saveLoading" @update:content="drawerContent = $event" @save="saveAsNewVersion" />
        </div>
      </div>
    </el-card>

    <!-- Progress section -->
    <el-card v-if="taskInfo" class="progress-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">评估进度</span>
          <el-tag :type="statusTagType" size="small">
            {{ statusLabel }}
          </el-tag>
          <el-button
            v-if="taskInfo.status === 'completed' && taskInfo.file_id"
            type="success"
            size="small"
            @click="router.push('/data-manage?file_id=' + taskInfo.file_id)"
          >
            查看数据
          </el-button>
        </div>
      </template>
      <div class="progress-area">
        <el-progress
          :percentage="progressPercent"
          :status="progressStatus"
          :stroke-width="20"
          :text-inside="true"
          style="margin-bottom: 12px"
        />
        <div class="progress-text">
          已完成 {{ taskInfo.progress_current }}/{{ taskInfo.progress_total }} 条记录，
          已评估 {{ taskInfo.evaluated_count }} 条
          <template v-if="taskInfo.avg_score != null">
            ，平均综合评分 <span class="avg-score">{{ taskInfo.avg_score }}</span>
          </template>
        </div>
      </div>
    </el-card>

    <!-- Evaluation report section (shown after completion) -->
    <el-card v-if="reportData && taskInfo && taskInfo.status === 'completed'" class="report-card">
      <template #header>
        <span class="card-title">评估报告</span>
      </template>
      <div class="report-content">
        <el-descriptions :column="3" border size="default">
          <el-descriptions-item label="评估总数">
            {{ reportData.evaluated_count }} / {{ reportData.total_records }}
          </el-descriptions-item>
          <el-descriptions-item label="平均相关性">
            <span v-if="reportData.avg_relevance != null" class="score-value">{{ reportData.avg_relevance }}</span>
            <span v-else class="score-na">N/A</span>
          </el-descriptions-item>
          <el-descriptions-item label="平均清晰度">
            <span v-if="reportData.avg_clarity != null" class="score-value">{{ reportData.avg_clarity }}</span>
            <span v-else class="score-na">N/A</span>
          </el-descriptions-item>
          <el-descriptions-item label="平均推理">
            <span v-if="reportData.avg_reasoning != null" class="score-value">{{ reportData.avg_reasoning }}</span>
            <span v-else class="score-na">N/A</span>
          </el-descriptions-item>
          <el-descriptions-item label="平均术语">
            <span v-if="reportData.avg_terminology != null" class="score-value">{{ reportData.avg_terminology }}</span>
            <span v-else class="score-na">N/A</span>
          </el-descriptions-item>
          <el-descriptions-item label="平均综合评分">
            <span v-if="reportData.avg_score != null" class="score-value overall-score">{{ reportData.avg_score }}</span>
            <span v-else class="score-na">N/A</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- Results area (lazy-loaded) -->
    <el-card class="results-card">
      <template #header>
        <span class="card-title">生成结果 - {{ currentFileName }}</span>
      </template>
      <div class="results-body">
        <div class="results-toolbar">
          <el-button type="primary" size="small" :loading="resultsLoading" @click="loadResults">
            加载最新结果
          </el-button>
          <span v-if="resultsTotal > 0" class="results-count">共 {{ resultsTotal }} 条</span>
        </div>

        <el-table
          v-if="resultsData.length > 0"
          :data="resultsData"
          v-loading="resultsLoading"
          stripe
          border
          size="small"
          style="width: 100%"
        >
          <el-table-column prop="id" label="ID" width="50" />
          <el-table-column prop="input" label="问题(input)" min-width="180" show-overflow-tooltip />
          <el-table-column prop="score" label="综合评分" width="80" />
          <el-table-column prop="relevance" label="相关性" width="70" />
          <el-table-column prop="clarity" label="清晰度" width="70" />
          <el-table-column prop="reasoning" label="推理" width="70" />
          <el-table-column prop="terminology" label="术语" width="70" />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="showDetail(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="resultsData.length === 0 && !resultsLoading" class="results-empty">
          点击"加载最新结果"查看数据
        </div>

        <div v-if="resultsTotal > 0" class="results-pagination">
          <el-pagination
            v-model:current-page="resultsPage"
            :page-size="10"
            :total="resultsTotal"
            layout="total, prev, pager, next"
            @current-change="handleResultsPageChange"
          />
        </div>
      </div>
    </el-card>

    <!-- Log section -->
    <el-card v-if="taskInfo" class="log-card">
      <template #header>
        <span class="card-title">任务日志</span>
      </template>
      <div class="log-area" v-loading="logLoading">
        <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
        <div
          v-for="log in logs"
          :key="log.id"
          class="log-item"
        >
          <span class="log-time">{{ formatTime(log.created_at) }}</span>
          <span :class="log.log_content.includes('评估完成') ? 'log-success' : log.log_content.includes('解析失败') || log.log_content.includes('LLM调用失败') ? 'log-error' : 'log-content'">
            {{ log.log_content }}
          </span>
        </div>
      </div>
    </el-card>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="记录详情" width="700px" :append-to-body="true">
      <template v-if="detailRecord">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="id">{{ detailRecord.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="score">{{ detailRecord.score ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="relevance">{{ detailRecord.relevance ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="clarity">{{ detailRecord.clarity ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="reasoning">{{ detailRecord.reasoning ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="terminology">{{ detailRecord.terminology ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-text-fields">
          <div class="text-field-block" v-if="detailRecord.input">
            <div class="field-label">问题 (Input)</div>
            <div class="field-content" v-html="renderContent(detailRecord.input)"></div>
          </div>
          <div class="text-field-block" v-if="detailRecord.output">
            <div class="field-label">答案 (Output)</div>
            <div class="field-content" v-html="renderContent(detailRecord.output)"></div>
          </div>
          <div class="text-field-block" v-if="detailRecord.cot">
            <div class="field-label">思维链 (CoT)</div>
            <div class="field-content" v-html="renderContent(detailRecord.cot)"></div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  startDataEvaluate,
  getStageStatus,
  retryStage,
  getTaskLogs,
  getTaskList,
  getDataEvaluateSourceFiles,
  getDataEvaluateReport,
  getPromptConfigs,
  getLLMConfigs,
} from '../api'
import { usePromptDrawer } from '../composables/usePromptDrawer'
import FileSelector from '../components/FileSelector.vue'
import PromptPreview from '../components/PromptPreview.vue'
import { useStageResults } from '../composables/useStageResults'

// ----- Form state -----
const router = useRouter()
const form = ref({
  file_id: null,
  prompt_id: null,
  model: '',
})

const fileOptions = ref([])
const promptOptions = ref([])
const llmConfigs = ref([])
const selectedLLMConfigId = ref(null)
const currentModelOptions = computed(() => {
  const cfg = llmConfigs.value.find(c => c.id === selectedLLMConfigId.value)
  return cfg ? (cfg.models || []) : []
})
const startLoading = ref(false)

// ----- Prompt drawer -----
const {
  drawerVisible,
  drawerContent,
  drawerVersion,
  drawerCreatedAt,
  drawerContentChanged,
  nextVersion,
  saveLoading,
  saveAsNewVersion,
} = usePromptDrawer('data_evaluate', promptOptions, form, selectedLLMConfigId)

// ----- File upload callback -----
function onFileUploadSuccess() {
  fetchFileOptions()
}

// ----- Current file name for results header -----
const currentFileName = computed(() => {
  const targetId = effectiveFileId.value || form.value.file_id
  const f = fileOptions.value.find(f => f.id === targetId)
  return f ? f.filename : '未选择文件'
})

// ----- Task state (must be before useStageResults) -----
const taskInfo = ref(null)

// ----- Stage results (lazy-loaded) -----
const {
  resultsData,
  resultsTotal,
  resultsLoading,
  resultsPage,
  detailVisible,
  detailRecord,
  effectiveFileId,
  loadResults,
  handleResultsPageChange,
  showDetail,
  renderContent,
} = useStageResults(
  'data_evaluate',
  computed(() => form.value.file_id),
  undefined,
  taskInfo
)

// ----- More Task state -----
const taskId = ref(null)
const taskRunning = ref(false)
const logs = ref([])
const logLoading = ref(false)
const reportData = ref(null)

// Polling timer
let pollTimer = null
let logTimer = null

// ----- Computed -----
const canStart = computed(() => {
  return (
    form.value.file_id &&
    form.value.prompt_id &&
    form.value.model &&
    !taskRunning.value
  )
})

const canRetry = computed(() => {
  return taskInfo.value && taskInfo.value.status === 'failed'
})

const progressPercent = computed(() => {
  if (!taskInfo.value || taskInfo.value.progress_total === 0) return 0
  return Math.round(
    (taskInfo.value.progress_current / taskInfo.value.progress_total) * 100
  )
})

const progressStatus = computed(() => {
  if (!taskInfo.value) return ''
  if (taskInfo.value.status === 'completed') return 'success'
  if (taskInfo.value.status === 'failed') return 'exception'
  return ''
})

const statusTagType = computed(() => {
  if (!taskInfo.value) return 'info'
  const s = taskInfo.value.status
  if (s === 'running') return 'primary'
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
})

const statusLabel = computed(() => {
  if (!taskInfo.value) return ''
  const map = {
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    pending: '等待中',
  }
  return map[taskInfo.value.status] || taskInfo.value.status
})

// ----- Data fetching -----
async function fetchFileOptions() {
  try {
    const res = await getDataEvaluateSourceFiles()
    fileOptions.value = Array.isArray(res) ? res : []
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    fileOptions.value = []
  }
}

async function fetchPromptOptions() {
  try {
    const res = await getPromptConfigs({ stage: 'data_evaluate' })
    promptOptions.value = Array.isArray(res) ? res : []
  } catch (err) {
    ElMessage.error('获取Prompt列表失败')
    promptOptions.value = []
  }
}

async function fetchLLMConfigs() {
  try {
    const res = await getLLMConfigs()
    llmConfigs.value = Array.isArray(res) ? res : []
  } catch (err) {
    ElMessage.error('获取LLM配置失败')
    llmConfigs.value = []
  }
}

function handleLLMConfigChange(configId) {
  const cfg = llmConfigs.value.find(c => c.id === configId)
  if (cfg) {
    form.value.model = cfg.default_model || ''
  } else {
    form.value.model = ''
  }
}

// ----- Task operations -----
async function handleStart() {
  if (!canStart.value) return

  startLoading.value = true
  try {
    const payload = {
      file_id: form.value.file_id,
      prompt_id: form.value.prompt_id,
      model: form.value.model,
      llm_config_id: selectedLLMConfigId.value || null,
    }
    const res = await startDataEvaluate(payload)
    taskId.value = res.task_id
    taskRunning.value = true
    reportData.value = null

    // Immediately fetch initial status
    await pollStatus()

    // Start polling
    startPolling()

    ElMessage.success('数据评估任务已启动')
  } catch (err) {
    const detail = err.response?.data?.detail || '启动任务失败'
    ElMessage.error(detail)
  } finally {
    startLoading.value = false
  }
}

async function handleRetry() {
  if (!taskId.value) return

  startLoading.value = true
  try {
    const res = await retryStage('data-evaluate', taskId.value)
    taskId.value = res.task_id
    taskRunning.value = true
    reportData.value = null

    await pollStatus()
    startPolling()

    ElMessage.success('重试任务已启动')
  } catch (err) {
    const detail = err.response?.data?.detail || '重试失败'
    ElMessage.error(detail)
  } finally {
    startLoading.value = false
  }
}

async function pollStatus() {
  if (!taskId.value) return
  try {
    const res = await getStageStatus('data-evaluate', taskId.value)
    taskInfo.value = res
    taskRunning.value = res.status === 'running'

    // Auto-stop polling when task is done
    if (res.status === 'completed' || res.status === 'failed') {
      stopPolling()
      taskRunning.value = false

      // Fetch report on completion
      if (res.status === 'completed') {
        await fetchReport()
      }
    }
  } catch (err) {
    // Silently handle polling errors to avoid spamming
    console.error('Poll status error:', err)
  }
}

async function fetchReport() {
  if (!taskId.value) return
  try {
    const res = await getDataEvaluateReport(taskId.value)
    reportData.value = res
  } catch (err) {
    console.error('Fetch report error:', err)
  }
}

async function fetchLogs() {
  if (!taskId.value) return
  logLoading.value = true
  try {
    const res = await getTaskLogs(taskId.value)
    logs.value = Array.isArray(res) ? res : []
  } catch (err) {
    // Silently handle log fetch errors
    console.error('Fetch logs error:', err)
  } finally {
    logLoading.value = false
  }
}

// ----- Polling control -----
function startPolling() {
  stopPolling()
  // Poll status every 3 seconds
  pollTimer = setInterval(() => {
    pollStatus()
  }, 3000)
  // Refresh logs every 5 seconds
  logTimer = setInterval(() => {
    fetchLogs()
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (logTimer) {
    clearInterval(logTimer)
    logTimer = null
  }
}

// ----- Formatting -----
function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// ----- Lifecycle -----
async function restoreTaskState() {
  try {
    const tasks = await getTaskList({ stage: 'data_evaluate' })
    if (!Array.isArray(tasks) || tasks.length === 0) return

    // Find the latest running task first, then fall back to the latest task overall
    const runningTask = tasks.find(t => t.status === 'running')
    const latestTask = runningTask || tasks[0]

    if (!latestTask) return

    taskId.value = latestTask.id
    taskRunning.value = latestTask.status === 'running'

    // Fetch current status
    await pollStatus()

    // Fetch existing logs
    await fetchLogs()

    // Fetch report if task was completed
    if (latestTask.status === 'completed') {
      await fetchReport()
    }

    // Start polling if the task is still running
    if (latestTask.status === 'running') {
      startPolling()
    }
  } catch (err) {
    console.error('Restore task state error:', err)
  }
}

onMounted(async () => {
  await Promise.all([
    fetchFileOptions(),
    fetchPromptOptions(),
    fetchLLMConfigs(),
  ])
  // Restore previous task state after options are loaded
  await restoreTaskState()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
@import 'katex/dist/katex.min.css';
.page-container {
  max-width: 1200px;
}
.page-container h2 {
  margin-bottom: 16px;
}

.form-card {
  margin-bottom: 20px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}

.progress-card {
  margin-bottom: 20px;
}
.progress-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.progress-area {
  padding: 8px 0;
}
.progress-text {
  color: #606266;
  font-size: 14px;
  margin-top: 4px;
}
.avg-score {
  color: #409eff;
  font-weight: 600;
}

.report-card {
  margin-bottom: 20px;
}
.report-content {
  padding: 8px 0;
}
.score-value {
  font-weight: 600;
  color: #303133;
}
.overall-score {
  color: #409eff;
  font-size: 16px;
}
.score-na {
  color: #909399;
}

.log-card {
  margin-bottom: 20px;
}
.log-area {
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}
.log-empty {
  text-align: center;
  color: #909399;
  padding: 20px;
}
.log-item {
  padding: 6px 0;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  gap: 12px;
}
.log-item:last-child {
  border-bottom: none;
}
.log-time {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
  min-width: 140px;
}
.log-content {
  color: #303133;
  font-size: 13px;
  word-break: break-all;
}
.log-success {
  color: #67c23a;
  font-size: 13px;
  word-break: break-all;
  font-weight: 600;
}
.log-error {
  color: #f56c6c;
  font-size: 13px;
  word-break: break-all;
  font-weight: 600;
}

.config-layout { display: flex; gap: 24px; }
.config-form { flex: 3; min-width: 0; }
.config-preview { flex: 2; min-width: 0; }

/* Results area styles */
.results-card {
  margin-bottom: 20px;
}
.results-body {
  padding-top: 4px;
}
.results-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.results-count {
  color: #909399;
  font-size: 13px;
}
.results-empty {
  text-align: center;
  color: #909399;
  padding: 20px;
}
.results-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

/* Detail dialog styles */
.detail-text-fields {
  margin-top: 16px;
}
.text-field-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.text-field-block .field-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
  font-size: 14px;
}
.text-field-block .field-content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  color: #606266;
}
.empty-field {
  color: #c0c4cc;
}
</style>