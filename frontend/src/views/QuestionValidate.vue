<template>
  <div class="page-container">
    <h2>问题校验</h2>

    <!-- Form section -->
    <el-card class="form-card">
      <template #header>
        <span class="card-title">校验配置</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="form" label-width="100px" :disabled="taskRunning">
            <el-form-item label="选择文件">
              <FileSelector v-model="form.file_id" :fetch-fn="fetchFileOptions" expected-stage="knowledge_generate" :disabled="taskRunning" />
            </el-form-item>

            <el-form-item label="选择Prompt">
              <el-select v-model="form.prompt_id" placeholder="请选择问题校验阶段的Prompt" style="width: 100%" filterable>
                <el-option v-for="p in promptOptions" :key="p.id" :label="`v${p.version}`" :value="p.id">
                  <span>v{{ p.version }}{{ p.is_default ? '(默认)' : '' }}</span>
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

            <el-form-item label="输出文件名">
              <el-input
                v-model="form.output_filename"
                placeholder="请输入输出文件名（系统自动追加用户名和时间戳后缀）"
                clearable
              />
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
                开始校验
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

    <!-- Source file preview -->
    <el-card v-if="form.file_id" class="source-preview-card">
      <template #header>
        <span class="card-title">源文件预览 - {{ sourceFileName }}</span>
      </template>
      <div class="results-body">
        <div class="results-toolbar">
          <el-button type="primary" size="small" :loading="sourceLoading" @click="loadSourcePreview">加载预览</el-button>
          <span v-if="sourceTotal > 0" class="results-count">共 {{ sourceTotal }} 条</span>
        </div>
        <el-table v-if="sourceData.length > 0" :data="sourceData" v-loading="sourceLoading" stripe border size="small" style="width: 100%">
          <el-table-column
            v-for="col in sourceColumns"
            :key="col.prop"
            :prop="col.prop"
            :label="col.label"
            :width="col.width"
            :min-width="col.minWidth"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ truncateText(row[col.prop]) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="showSourceDetail(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="sourceData.length === 0 && !sourceLoading" class="results-empty">点击"加载预览"查看源文件内容</div>
        <div v-if="sourceTotal > 0" class="results-pagination">
          <el-pagination v-model:current-page="sourcePage" :page-size="10" :total="sourceTotal" layout="total, prev, pager, next" @current-change="handleSourcePageChange" />
        </div>
      </div>
    </el-card>

    <!-- Progress section -->
    <el-card v-if="taskInfo" class="progress-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">校验进度</span>
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
          <el-button
            v-if="taskInfo.status === 'running'"
            type="danger"
            size="small"
            @click="handleStop"
          >
            停止
          </el-button>
          <el-button
            v-if="taskInfo.status === 'paused'"
            type="primary"
            size="small"
            @click="handleResume"
          >
            恢复
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
          通过 <span class="pass-count">{{ taskInfo.pass_count }}</span> 条，
          失败 <span class="fail-count">{{ taskInfo.fail_count }}</span> 条
        </div>
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
          <el-table-column
            v-for="col in tableColumns"
            :key="col.prop"
            :prop="col.prop"
            :label="col.label"
            :width="col.width"
            :min-width="col.minWidth"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ truncateText(row[col.prop]) }}
            </template>
          </el-table-column>
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
          <span :class="log.log_content.includes('校验通过') ? 'log-pass' : log.log_content.includes('校验失败') ? 'log-fail' : 'log-content'">
            {{ log.log_content }}
          </span>
        </div>
      </div>
    </el-card>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="记录详情" width="700px" :append-to-body="true">
      <template v-if="detailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item v-for="key in metaFields" :key="key" :label="FIELD_LABELS[key] || key">
            {{ detailRecord[key] != null ? detailRecord[key] : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-text-fields">
          <div v-for="key in longTextFields" :key="key" class="text-field-block" v-if="detailRecord[key]">
            <div class="field-label">{{ FIELD_LABELS[key] || key }}</div>
            <div class="field-content" v-html="renderContent(detailRecord[key])"></div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Source detail dialog -->
    <el-dialog v-model="sourceDetailVisible" title="源文件记录详情" width="700px" :append-to-body="true">
      <template v-if="sourceDetailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item v-for="key in sourceMetaFields" :key="key" :label="FIELD_LABELS[key] || key">
            {{ sourceDetailRecord[key] != null ? sourceDetailRecord[key] : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-text-fields">
          <div v-for="key in sourceLongTextFields" :key="key" class="text-field-block" v-if="sourceDetailRecord[key]">
            <div class="field-label">{{ FIELD_LABELS[key] || key }}</div>
            <div class="field-content" v-html="renderSourceContent(sourceDetailRecord[key])"></div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  startQuestionValidate,
  stopTask,
  resumeTask,
  getStageStatus,
  retryStage,
  getTaskLogs,
  getTaskList,
  getQuestionValidateSourceFiles,
  getPromptConfigs,
  getLLMConfigs,
} from '../api'
import { usePromptDrawer } from '../composables/usePromptDrawer'
import FileSelector from '../components/FileSelector.vue'
import PromptPreview from '../components/PromptPreview.vue'
import { useStageResults } from '../composables/useStageResults'
import { useSourcePreview } from '../composables/useSourcePreview'
import { buildDefaultOutputFilename } from '../utils/stageLabels'
import { FIELD_LABELS, LONG_TEXT_FIELDS, META_FIELDS } from '../utils/fieldLabels'

// ----- Form state -----
const router = useRouter()
const form = ref({
  file_id: null,
  prompt_id: null,
  model: '',
  output_filename: '',
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

const username = computed(() => localStorage.getItem('username') || 'unknown')

// Auto-fill output filename when source file changes
watch(() => form.value.file_id, (newFileId) => {
  if (!newFileId) return
  const file = fileOptions.value.find(f => f.id === newFileId)
  if (file && !form.value.output_filename) {
    form.value.output_filename = buildDefaultOutputFilename(file.filename, 'question_validate', username.value)
  }
})

// ----- Prompt drawer -----
const {
  drawerContent,
  drawerVersion,
  drawerCreatedAt,
  drawerContentChanged,
  nextVersion,
  saveLoading,
  saveAsNewVersion,
} = usePromptDrawer('question_validate', promptOptions, form, selectedLLMConfigId)

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
  tableColumns,
  loadResults,
  handleResultsPageChange,
  showDetail,
  truncateText,
  renderContent,
} = useStageResults(
  'question_validate',
  computed(() => form.value.file_id),
  undefined,
  taskInfo
)

// ----- Source file preview -----
const {
  sourceData,
  sourceTotal,
  sourceLoading,
  sourcePage,
  sourceFileName,
  sourceColumns,
  sourceDetailVisible,
  sourceDetailRecord,
  sourceMetaFields,
  sourceLongTextFields,
  loadSourcePreview,
  handleSourcePageChange,
  showSourceDetail,
  renderContent: renderSourceContent,
} = useSourcePreview(
  computed(() => form.value.file_id),
  fileOptions
)

// ----- Detail dialog computed fields -----
const metaFields = computed(() => {
  if (!detailRecord.value) return []
  return META_FIELDS.filter(k => detailRecord.value[k] != null)
})
const longTextFields = computed(() => {
  if (!detailRecord.value) return []
  return LONG_TEXT_FIELDS.filter(k => detailRecord.value[k])
})

// ----- More Task state -----
const taskId = ref(null)
const taskRunning = ref(false)
const logs = ref([])
const logLoading = ref(false)

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
  if (s === 'paused') return 'warning'
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
    paused: '已暂停',
    pending: '等待中',
  }
  return map[taskInfo.value.status] || taskInfo.value.status
})

// ----- Data fetching -----
async function fetchFileOptions(showAll) {
  try {
    const res = await getQuestionValidateSourceFiles({ show_all: showAll })
    const items = Array.isArray(res) ? res : []
    fileOptions.value = items
    return items
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    return []
  }
}

async function fetchPromptOptions() {
  try {
    const res = await getPromptConfigs({ stage: 'question_validate' })
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
async function handleStop() {
  try {
    await stopTask(taskId.value)
    ElMessage.success('已发送停止信号，任务将在当前条处理完后停止')
    if (taskInfo.value) taskInfo.value.status = 'paused'
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '停止失败')
  }
}

async function handleResume() {
  try {
    await resumeTask(taskId.value)
    ElMessage.success('任务已恢复运行')
    if (taskInfo.value) taskInfo.value.status = 'running'
    startPolling()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '恢复失败')
  }
}

async function handleStart() {
  if (!canStart.value) return

  startLoading.value = true
  try {
    const payload = {
      file_id: form.value.file_id,
      prompt_id: form.value.prompt_id,
      model: form.value.model,
      llm_config_id: selectedLLMConfigId.value || null,
      output_filename: form.value.output_filename || undefined,
    }
    const res = await startQuestionValidate(payload)
    taskId.value = res.task_id
    taskRunning.value = true

    // Immediately fetch initial status
    await pollStatus()

    // Start polling
    startPolling()

    ElMessage.success('问题校验任务已启动')
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
    const res = await retryStage('question-validate', taskId.value)
    taskId.value = res.task_id
    taskRunning.value = true

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
    const res = await getStageStatus('question-validate', taskId.value)
    taskInfo.value = res
    taskRunning.value = res.status === 'running'

    // Auto-stop polling when task is done
    if (res.status === 'completed' || res.status === 'failed') {
      stopPolling()
      taskRunning.value = false
    }
  } catch (err) {
    // Silently handle polling errors to avoid spamming
    console.error('Poll status error:', err)
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
    const tasks = await getTaskList({ stage: 'question_validate' })
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
.page-container {}
.page-container h2 {
  margin-bottom: 16px;
}

.form-card {
  margin-bottom: 20px;
}
.source-preview-card {
  margin-bottom: 20px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}

.config-layout {
  display: flex;
  gap: 24px;
}
.config-form {
  flex: 3;
  min-width: 0;
}
.config-preview {
  flex: 2;
  min-width: 0;
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
.pass-count {
  color: #67c23a;
  font-weight: 600;
}
.fail-count {
  color: #f56c6c;
  font-weight: 600;
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
.log-pass {
  color: #67c23a;
  font-size: 13px;
  word-break: break-all;
  font-weight: 600;
}
.log-fail {
  color: #f56c6c;
  font-size: 13px;
  word-break: break-all;
  font-weight: 600;
}

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