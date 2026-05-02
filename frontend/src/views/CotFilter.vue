<template>
  <div class="page-container">
    <h2>COT过滤</h2>
    <p class="page-intro">将QA记录按推理链(cot)字段是否为空分成两组，生成两个新JSON文件。</p>

    <el-card class="form-card">
      <template #header>
        <span class="card-title">过滤配置</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="form" label-width="100px" :disabled="taskRunning">
            <el-form-item label="选择文件">
              <FileSelector
                v-model="form.file_id"
                :file-options="fileOptions"
                :disabled="taskRunning"
                @upload-success="onFileUploadSuccess"
              />
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
                开始过滤
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="config-result">
          <div v-if="filterResult" class="result-stats">
            <div class="stat-item">
              <span class="stat-label">总记录数</span>
              <span class="stat-value">{{ filterResult.total }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">COT不为空</span>
              <span class="stat-value">{{ filterResult.with_cot_count }} ({{ filterResult.with_cot_percent }}%)</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">COT为空</span>
              <span class="stat-value">{{ filterResult.without_cot_count }} ({{ filterResult.without_cot_percent }}%)</span>
            </div>
            <div class="download-area">
              <el-button type="primary" size="small" @click="handleDownload(filterResult.with_cot_file_id)">
                下载COT不为空
              </el-button>
              <el-button type="success" size="small" @click="handleDownload(filterResult.without_cot_file_id)">
                下载COT为空
              </el-button>
            </div>
          </div>
          <div v-else class="result-empty">
            过滤完成后将在此显示统计结果
          </div>
        </div>
      </div>
    </el-card>

    <!-- Progress section -->
    <el-card v-if="taskInfo" class="progress-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">过滤进度</span>
          <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  startCotFilter,
  getCotFilterStatus,
  getCotFilterSourceFiles,
  getTaskLogs,
  getTaskList,
  getManagedFiles,
  downloadManagedFile,
} from '../api'
import FileSelector from '../components/FileSelector.vue'

const form = ref({
  file_id: null,
  output_name: '',
})

const fileOptions = ref([])
const startLoading = ref(false)
const taskInfo = ref(null)
const taskId = ref(null)
const taskRunning = ref(false)
const filterResult = ref(null)
const logs = ref([])
const logLoading = ref(false)

let pollTimer = null
let logTimer = null

const canStart = computed(() => form.value.file_id && form.value.output_name && !taskRunning.value)

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
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
})

const statusLabel = computed(() => {
  if (!taskInfo.value) return ''
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '等待中' }
  return map[taskInfo.value.status] || taskInfo.value.status
})

async function fetchFileOptions() {
  try {
    const res = await getManagedFiles()
    fileOptions.value = res.items || []
  } catch (err) {
    ElMessage.error('获取文件列表失败')
  }
}

function onFileUploadSuccess() {
  fetchFileOptions()
}

async function handleStart() {
  if (!canStart.value) return
  startLoading.value = true
  try {
    const res = await startCotFilter({
      file_id: form.value.file_id,
      output_name: form.value.output_name,
    })
    taskId.value = res.task_id
    taskRunning.value = true
    await pollStatus()
    startPolling()
    ElMessage.success('COT过滤任务已启动')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '启动任务失败')
  } finally {
    startLoading.value = false
  }
}

async function pollStatus() {
  if (!taskId.value) return
  try {
    const res = await getCotFilterStatus(taskId.value)
    taskInfo.value = res
    taskRunning.value = res.status === 'running'
    if (res.status === 'completed' || res.status === 'failed') {
      stopPolling()
      taskRunning.value = false
      await fetchLogs()
      if (res.status === 'completed') await loadFilterResult()
    }
  } catch (err) {
    console.error('Poll status error:', err)
  }
}

async function loadFilterResult() {
  try {
    const res = await getTaskLogs(taskId.value)
    const logItems = Array.isArray(res) ? res : []
    const resultLog = logItems.find(l => l.log_content && l.log_content.includes('COT过滤完成'))
    if (resultLog) {
      const match = resultLog.log_content.match(/总计 (\d+) 条, COT不为空 (\d+) 条, COT为空 (\d+) 条/)
      if (match) {
        filterResult.value = {
          total: parseInt(match[1]),
          with_cot_count: parseInt(match[2]),
          without_cot_count: parseInt(match[3]),
          with_cot_percent: match[1] > 0 ? Math.round(parseInt(match[2]) / parseInt(match[1]) * 100, 1) : 0,
          without_cot_percent: match[1] > 0 ? Math.round(parseInt(match[3]) / parseInt(match[1]) * 100, 1) : 0,
          with_cot_file_id: null,
          without_cot_file_id: null,
        }
      }
    }
    // Fetch files to get file_ids for download
    const filesRes = await getManagedFiles({ source_stage: 'cot_filter' })
    const cotFiles = filesRes.items || []
    const withCotFile = cotFiles.find(f => f.filename && f.filename.includes('_cot'))
    const withoutCotFile = cotFiles.find(f => f.filename && f.filename.includes('_no_cot'))
    if (filterResult.value) {
      filterResult.value.with_cot_file_id = withCotFile?.id || null
      filterResult.value.without_cot_file_id = withoutCotFile?.id || null
      filterResult.value.with_cot_percent = filterResult.value.total > 0
        ? Math.round(filterResult.value.with_cot_count / filterResult.value.total * 1000 / 10, 1)
        : 0
      filterResult.value.without_cot_percent = filterResult.value.total > 0
        ? Math.round(filterResult.value.without_cot_count / filterResult.value.total * 1000 / 10, 1)
        : 0
    }
  } catch (err) {
    console.error('Load filter result error:', err)
  }
}

async function fetchLogs() {
  if (!taskId.value) return
  logLoading.value = true
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

async function handleDownload(fileId) {
  if (!fileId) { ElMessage.warning('文件不存在'); return }
  try {
    const res = await downloadManagedFile(fileId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `cot_filter_${fileId}.json`
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
    const tasks = await getTaskList({ stage: 'cot_filter' })
    if (!Array.isArray(tasks) || tasks.length === 0) return
    const runningTask = tasks.find(t => t.status === 'running')
    const latestTask = runningTask || tasks[0]
    taskId.value = latestTask.id
    taskRunning.value = latestTask.status === 'running'
    await pollStatus()
    await fetchLogs()
    if (latestTask.status === 'running') startPolling()
    if (latestTask.status === 'completed') await loadFilterResult()
  } catch (err) {
    console.error('Restore task state error:', err)
  }
}

onMounted(async () => {
  await fetchFileOptions()
  await restoreTaskState()
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.page-container { max-width: 1200px }
.page-container h2 { margin-bottom: 16px }
.page-intro { color: #909399; font-size: 14px; margin-bottom: 16px }
.form-card { margin-bottom: 20px }
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
</style>