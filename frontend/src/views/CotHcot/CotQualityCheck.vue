<template>
  <div class="page-container">
    <h2>CoT质检</h2>
    <p class="page-intro">对推理链(CoT)内容进行质量检测，区分通过和不通过的记录，并生成评估结果文件。</p>

    <el-card class="form-card">
      <template #header>
        <span class="card-title">质检配置</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="form" label-width="100px" :disabled="taskRunning">
            <el-form-item label="选择文件">
              <FileSelector v-model="form.file_id" :fetch-fn="fetchFileOptions" expected-stage="cot_filter" :disabled="taskRunning" />
            </el-form-item>

            <el-form-item label="输出名称">
              <el-input
                v-model="form.output_name"
                placeholder="请输入输出文件名（系统自动追加用户名和时间戳后缀）"
                clearable
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="startLoading"
                :disabled="!canStart"
                @click="handleStart"
              >
                开始质检
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="config-result">
          <div v-if="qualityCheckResult" class="result-stats">
            <div class="stat-item">
              <span class="stat-label">总记录数</span>
              <span class="stat-value">{{ qualityCheckResult.total }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">通过</span>
              <span class="stat-value">{{ qualityCheckResult.pass_count }} ({{ qualityCheckResult.pass_percent }}%)</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">不通过</span>
              <span class="stat-value">{{ qualityCheckResult.fail_count }} ({{ qualityCheckResult.fail_percent }}%)</span>
            </div>
            <div class="download-area">
              <el-button type="primary" size="small" @click="handleDownload(qualityCheckResult.pass_file_id, 'pass')">
                下载通过文件
              </el-button>
              <el-button type="danger" size="small" @click="handleDownload(qualityCheckResult.fail_file_id, 'fail')">
                下载不通过文件
              </el-button>
              <el-button type="success" size="small" @click="handleDownload(qualityCheckResult.eval_file_id, 'eval')">
                下载评估结果
              </el-button>
            </div>
          </div>
          <div v-else class="result-empty">
            质检完成后将在此显示统计结果
          </div>
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
          <span class="card-title">质检进度</span>
          <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
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
        />
      </div>
    </el-card>

    <!-- Log section -->
    <el-card v-if="taskInfo" class="log-card">
      <template #header>
        <span class="card-title">任务日志</span>
      </template>
      <div class="log-area" v-loading="logLoading">
        <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
        <div v-for="log in logs" :key="log.id" class="log-item">
          <span class="log-time">{{ formatTime(log.created_at) }}</span>
          <span class="log-content">{{ log.log_content }}</span>
        </div>
      </div>
    </el-card>

    <!-- Source detail dialog -->
    <el-dialog v-model="sourceDetailVisible" title="源文件记录详情" width="700px" :append-to-body="true">
      <template v-if="sourceDetailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item v-for="key in sourceMetaFields" :key="key" :label="key">
            {{ sourceDetailFlatRecord[key] != null ? sourceDetailFlatRecord[key] : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-text-fields">
          <div v-for="key in sourceLongTextFields" :key="key" class="text-field-block">
            <div class="field-label">{{ key }}</div>
            <div class="field-content" v-html="renderContent(sourceDetailFlatRecord[key])"></div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 恢复配置弹窗 -->
    <TaskConfigDialog
      v-model:visible="configDialogVisible"
      action="resume"
      :task="taskInfo"
      stage="cot_quality_check"
      @confirm="handleConfigConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  startCotQualityCheck,
  getCotQualityCheckStatus,
  getCotQualityCheckSourceFiles,
  getTaskLogs,
  getTaskList,
  getManagedFiles,
  downloadManagedFile,
  stopTask,
  resumeTask,
} from '../api'
import FileSelector from '../components/FileSelector.vue'
import TaskConfigDialog from '../components/TaskConfigDialog.vue'
import { useSourcePreview } from '../composables/useSourcePreview'
import { buildDefaultOutputFilename } from '../utils/stageLabels'

const form = ref({
  file_id: null,
  output_name: '',
})

const fileOptions = ref([])
const startLoading = ref(false)
const username = computed(() => localStorage.getItem('username') || 'unknown')
const taskInfo = ref(null)
const taskId = ref(null)
const taskRunning = ref(false)
const qualityCheckResult = ref(null)
const logs = ref([])
const logLoading = ref(false)

let pollTimer = null
let logTimer = null

const canStart = computed(() => form.value.file_id && form.value.output_name && !taskRunning.value)

// Auto-fill output name when source file changes
watch(() => form.value.file_id, (newFileId) => {
  if (!newFileId) return
  const file = fileOptions.value.find(f => f.id === newFileId)
  if (file && !form.value.output_name) {
    form.value.output_name = buildDefaultOutputFilename(file.filename, 'cot_quality_check', username.value)
  }
})

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
  sourceDetailFlatRecord,
  sourceMetaFields,
  sourceLongTextFields,
  loadSourcePreview,
  handleSourcePageChange,
  showSourceDetail,
  renderContent,
} = useSourcePreview(
  computed(() => form.value.file_id),
  fileOptions
)

function truncateText(text) {
  if (!text) return '-'
  if (typeof text !== 'string') {
    try { text = JSON.stringify(text) } catch { text = String(text) }
  }
  if (text.length > 80) return text.substring(0, 80) + '...'
  return text
}

const progressPercent = computed(() => {
  if (!taskInfo.value || taskInfo.value.progress_total === 0) return 0
  return Math.round((taskInfo.value.progress_current / taskInfo.value.progress_total) * 100)
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
  const map = { running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', pending: '等待中' }
  return map[taskInfo.value.status] || taskInfo.value.status
})

async function fetchFileOptions(showAll) {
  try {
    const res = await getCotQualityCheckSourceFiles({ show_all: showAll })
    const items = Array.isArray(res) ? res : []
    fileOptions.value = items
    return items
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    return []
  }
}

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
  configDialogVisible.value = true
}

// ----- 恢复配置弹窗 -----
const configDialogVisible = ref(false)

async function handleConfigConfirm(data) {
  const payload = Object.keys(data || {}).length > 0 ? data : undefined
  try {
    await resumeTask(taskId.value, payload)
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
    const res = await startCotQualityCheck({
      file_id: form.value.file_id,
      output_name: form.value.output_name,
    })
    taskId.value = res.task_id
    taskRunning.value = true
    await pollStatus()
    startPolling()
    ElMessage.success('CoT质检任务已启动')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '启动任务失败')
  } finally {
    startLoading.value = false
  }
}

async function pollStatus() {
  if (!taskId.value) return
  try {
    const res = await getCotQualityCheckStatus(taskId.value)
    taskInfo.value = res
    taskRunning.value = res.status === 'running'
    if (res.status === 'completed' || res.status === 'failed') {
      stopPolling()
      taskRunning.value = false
      await fetchLogs()
      if (res.status === 'completed') await loadQualityCheckResult(res)
    }
  } catch (err) {
    console.error('Poll status error:', err)
  }
}

async function loadQualityCheckResult(statusRes) {
  try {
    // Use pass_count and fail_count from status response
    const total = (statusRes.pass_count || 0) + (statusRes.fail_count || 0)
    const passCount = statusRes.pass_count || 0
    const failCount = statusRes.fail_count || 0
    const passPercent = total > 0 ? Math.round(passCount / total * 1000 / 10, 1) : 0
    const failPercent = total > 0 ? Math.round(failCount / total * 1000 / 10, 1) : 0

    qualityCheckResult.value = {
      total,
      pass_count: passCount,
      fail_count: failCount,
      pass_percent: passPercent,
      fail_percent: failPercent,
      pass_file_id: null,
      fail_file_id: null,
      eval_file_id: null,
    }

    // Fetch files to get file_ids for download
    const filesRes = await getManagedFiles({ source_stage: 'cot_quality_check' })
    const cotFiles = filesRes.items || []
    const passFile = cotFiles.find(f => f.filename && f.filename.includes('通过') && !f.filename.includes('不通过'))
    const failFile = cotFiles.find(f => f.filename && f.filename.includes('不通过'))
    const evalFile = cotFiles.find(f => f.filename && f.filename.includes('评估结果'))
    if (qualityCheckResult.value) {
      qualityCheckResult.value.pass_file_id = passFile?.id || null
      qualityCheckResult.value.fail_file_id = failFile?.id || null
      qualityCheckResult.value.eval_file_id = evalFile?.id || null
    }
  } catch (err) {
    console.error('Load quality check result error:', err)
  }
}

async function fetchLogs() {
  if (!taskId.value) return
  if (logs.value.length === 0) logLoading.value = true
  try {
    const res = await getTaskLogs(taskId.value)
    logs.value = Array.isArray(res) ? res : []
  } catch (err) {
    console.error('Fetch logs error:', err)
  } finally {
    logLoading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => pollStatus(), 3000)
  logTimer = setInterval(() => fetchLogs(), 5000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (logTimer) { clearInterval(logTimer); logTimer = null }
}

async function handleDownload(fileId, type) {
  if (!fileId) { ElMessage.warning('文件不存在'); return }
  try {
    const res = await downloadManagedFile(fileId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    const suffixMap = { pass: 'pass', fail: 'fail', eval: 'eval' }
    link.download = `cot_quality_check_${suffixMap[type] || type}_${fileId}.json`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error('下载失败')
  }
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

async function restoreTaskState() {
  try {
    const tasks = await getTaskList({ stage: 'cot_quality_check' })
    if (!Array.isArray(tasks) || tasks.length === 0) return
    const latestTask = tasks.find(t => t.status === 'running' || t.status === 'paused')
    if (!latestTask) return
    taskId.value = latestTask.id
    taskRunning.value = latestTask.status === 'running'
    await pollStatus()
    await fetchLogs()
    if (latestTask.status === 'running') startPolling()
  } catch (err) {
    console.error('Restore task state error:', err)
  }
}

onMounted(async () => {
  await restoreTaskState()
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.page-container {}
.page-container h2 { margin-bottom: 16px }
.page-intro { color: #909399; font-size: 14px; margin-bottom: 16px }
.form-card { margin-bottom: 20px }
.source-preview-card { margin-bottom: 20px }
.card-title { font-size: 16px; font-weight: 600 }
.config-layout { display: flex; gap: 24px }
.config-form { flex: 3; min-width: 0 }
.config-result { flex: 2; min-width: 0 }

.result-stats { padding: 16px }
.stat-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ebeef5 }
.stat-item:last-of-type { border-bottom: none }
.stat-label { color: #606266; font-size: 14px }
.stat-value { color: #303133; font-size: 14px; font-weight: 600 }
.download-area { margin-top: 16px; display: flex; gap: 12px }
.result-empty { text-align: center; color: #909399; padding: 40px }

.progress-card { margin-bottom: 20px }
.card-header { display: flex; justify-content: space-between; align-items: center }
.progress-area { padding: 8px 0 }

.log-card { margin-bottom: 20px }
.log-area { max-height: 300px; overflow-y: auto; padding: 8px; background: #f5f7fa; border-radius: 4px }
.log-empty { text-align: center; color: #909399; padding: 20px }
.log-item { padding: 6px 0; border-bottom: 1px solid #ebeef5; display: flex; gap: 12px }
.log-item:last-child { border-bottom: none }
.log-time { color: #909399; font-size: 12px; white-space: nowrap; min-width: 140px }
.log-content { color: #303133; font-size: 13px; word-break: break-all }

/* Detail dialog styles */
.detail-text-fields { margin-top: 16px }
.text-field-block { margin-bottom: 16px; padding: 12px; background: #f5f7fa; border-radius: 4px }
.text-field-block .field-label { font-weight: 600; margin-bottom: 8px; color: #303133; font-size: 14px }
.text-field-block .field-content { font-size: 14px; line-height: 1.6; word-break: break-word; color: #606266 }
.empty-field { color: #c0c4cc }

/* Source preview styles */
.results-body {}
.results-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px }
.results-count { color: #909399; font-size: 13px }
.results-empty { text-align: center; color: #909399; padding: 20px }
.results-pagination { margin-top: 12px; display: flex; justify-content: center }
</style>