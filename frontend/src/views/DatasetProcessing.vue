<template>
  <div class="page-container">
    <h2>数据集处理</h2>

    <!-- Split section -->
    <el-card class="section-card">
      <template #header>
        <span class="card-title">数据集切分</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="splitForm" label-width="100px" :disabled="splitTaskRunning">
            <el-form-item label="选择文件">
              <FileSelector
                v-model="splitForm.file_id"
                :file-options="splitFileOptions"
                :disabled="splitTaskRunning"
                @upload-success="onSplitFileUploadSuccess"
              />
            </el-form-item>

            <el-form-item label="测试集数量">
              <el-input-number
                v-model="splitForm.test_count"
                :min="5"
                :max="1000"
                :step="1"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item label="输出名称">
              <el-input v-model="splitForm.output_name" placeholder="系统自动追加后缀" clearable />
            </el-form-item>

            <el-form-item label="切分策略">
              <el-select v-model="splitForm.split_strategy" style="width: 100%">
                <el-option label="难度优先 (difficulty_priority)" value="difficulty_priority" />
                <el-option label="题型比例随机 (task_type_random)" value="task_type_random" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="splitStartLoading" :disabled="!canStartSplit" @click="handleStartSplit">
                执行切分
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="config-result">
          <div v-if="splitTaskInfo" class="progress-area">
            <el-progress :percentage="splitProgressPercent" :status="splitProgressStatus" :stroke-width="16" :text-inside="true" />
            <el-tag :type="splitStatusTagType" size="small" style="margin-top: 8px">{{ splitStatusLabel }}</el-tag>
          </div>
          <div v-if="splitResult" class="result-stats">
            <div class="stat-item"><span class="stat-label">测试集数量</span><span class="stat-value">{{ splitResult.test_count }}</span></div>
            <div class="stat-item"><span class="stat-label">训练集数量</span><span class="stat-value">{{ splitResult.train_count }}</span></div>
            <div class="stat-item"><span class="stat-label">跳过非QA</span><span class="stat-value">{{ splitResult.skipped_non_qa }}</span></div>
            <div class="stat-item"><span class="stat-label">测试集题型分布</span><span class="stat-value">{{ splitResult.test_task_counts }}</span></div>
            <div class="stat-item"><span class="stat-label">训练集题型分布</span><span class="stat-value">{{ splitResult.train_task_counts }}</span></div>
          </div>
          <div v-if="!splitTaskInfo && !splitResult" class="result-empty">切分完成后将在此显示统计结果</div>
        </div>
      </div>
    </el-card>

    <!-- Split logs -->
    <el-card v-if="splitTaskInfo" class="log-card">
      <template #header><span class="card-title">切分日志</span></template>
      <div class="log-area" v-loading="splitLogLoading">
        <div v-if="splitLogs.length === 0" class="log-empty">暂无日志</div>
        <div v-for="log in splitLogs" :key="log.id" class="log-item">
          <span class="log-time">{{ formatTime(log.created_at) }}</span>
          <span class="log-content">{{ log.log_content }}</span>
        </div>
      </div>
    </el-card>

    <!-- Assessment section -->
    <el-card class="section-card">
      <template #header>
        <span class="card-title">评分标准生成</span>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="assessForm" label-width="100px" :disabled="assessTaskRunning">
            <el-form-item label="选择文件">
              <FileSelector
                v-model="assessForm.file_id"
                :file-options="assessFileOptions"
                :disabled="assessTaskRunning"
                @upload-success="onAssessFileUploadSuccess"
              />
            </el-form-item>

            <el-form-item label="输出名称">
              <el-input v-model="assessForm.output_name" placeholder="系统自动追加后缀" clearable />
            </el-form-item>

            <el-form-item label="选择Prompt">
              <el-select v-model="assessForm.prompt_id" placeholder="选择评分标准生成Prompt" style="width: 100%" filterable>
                <el-option v-for="p in assessPromptOptions" :key="p.id" :label="'v' + p.version" :value="p.id">
                  <span>v{{ p.version }}</span>
                  <span style="float: right; color: #909399; font-size: 13px">{{ p.content.substring(0, 50) }}{{ p.content.length > 50 ? '...' : '' }}</span>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="LLM配置">
              <el-select v-model="selectedAssessLLMConfigId" placeholder="选择LLM配置" style="width: 100%" filterable @change="handleAssessLLMConfigChange">
                <el-option v-for="cfg in assessLLMConfigs" :key="cfg.id" :label="cfg.name + (cfg.is_global ? ' (全局)' : ' (我的)')" :value="cfg.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="选择模型">
              <el-select v-model="assessForm.model" placeholder="请选择模型" style="width: 100%" :disabled="!selectedAssessLLMConfigId">
                <el-option v-for="m in assessModelOptions" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="assessStartLoading" :disabled="!canStartAssess" @click="handleStartAssess">
                生成评分标准
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="config-result">
          <div v-if="assessTaskInfo" class="progress-area">
            <el-progress :percentage="assessProgressPercent" :status="assessProgressStatus" :stroke-width="16" :text-inside="true" />
            <el-tag :type="assessStatusTagType" size="small" style="margin-top: 8px">{{ assessStatusLabel }}</el-tag>
          </div>
          <div v-if="assessResult" class="result-stats">
            <div class="stat-item"><span class="stat-label">QA条目数</span><span class="stat-value">{{ assessResult.qa_items }}</span></div>
            <div class="stat-item"><span class="stat-label">简答题数量</span><span class="stat-value">{{ assessResult.short_answer_items }}</span></div>
            <div class="stat-item"><span class="stat-label">已生成评分</span><span class="stat-value">{{ assessResult.generated }}</span></div>
            <div class="stat-item"><span class="stat-label">空评分数</span><span class="stat-value">{{ assessResult.empty_assessment }}</span></div>
          </div>
          <div v-if="!assessTaskInfo && !assessResult" class="result-empty">生成完成后将在此显示统计结果</div>
        </div>
      </div>
    </el-card>

    <!-- Assessment logs -->
    <el-card v-if="assessTaskInfo" class="log-card">
      <template #header><span class="card-title">评分日志</span></template>
      <div class="log-area" v-loading="assessLogLoading">
        <div v-if="assessLogs.length === 0" class="log-empty">暂无日志</div>
        <div v-for="log in assessLogs" :key="log.id" class="log-item">
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
  startDatasetSplit, getDatasetSplitStatus, getManagedFiles,
  startDatasetAssessment, getDatasetAssessmentStatus,
  getTaskLogs, getTaskList, getPromptConfigs, getLLMConfigs,
  downloadManagedFile,
} from '../api'
import FileSelector from '../components/FileSelector.vue'

// ---- Split state ----
const splitForm = ref({ file_id: null, test_count: 20, output_name: '', split_strategy: 'difficulty_priority' })
const splitFileOptions = ref([])
const splitStartLoading = ref(false)
const splitTaskInfo = ref(null)
const splitTaskId = ref(null)
const splitTaskRunning = ref(false)
const splitResult = ref(null)
const splitLogs = ref([])
const splitLogLoading = ref(false)
let splitPollTimer = null
let splitLogTimer = null

const canStartSplit = computed(() => splitForm.value.file_id && splitForm.value.output_name && splitForm.value.test_count >= 5 && !splitTaskRunning.value)

const splitProgressPercent = computed(() => {
  if (!splitTaskInfo.value || splitTaskInfo.value.progress_total === 0) return 0
  return Math.round((splitTaskInfo.value.progress_current / splitTaskInfo.value.progress_total) * 100)
})
const splitProgressStatus = computed(() => {
  if (!splitTaskInfo.value) return ''
  if (splitTaskInfo.value.status === 'completed') return 'success'
  if (splitTaskInfo.value.status === 'failed') return 'exception'
  return ''
})
const splitStatusTagType = computed(() => {
  if (!splitTaskInfo.value) return 'info'
  const s = splitTaskInfo.value.status
  if (s === 'running') return 'primary'
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
})
const splitStatusLabel = computed(() => {
  if (!splitTaskInfo.value) return ''
  const map = { running: '运行中', completed: '已完成', failed: '失败' }
  return map[splitTaskInfo.value.status] || splitTaskInfo.value.status
})

// ---- Assessment state ----
const assessForm = ref({ file_id: null, output_name: '', prompt_id: null, model: '' })
const assessFileOptions = ref([])
const assessPromptOptions = ref([])
const assessLLMConfigs = ref([])
const selectedAssessLLMConfigId = ref(null)
const assessModelOptions = computed(() => {
  const cfg = assessLLMConfigs.value.find(c => c.id === selectedAssessLLMConfigId.value)
  return cfg ? (cfg.models || []) : []
})
const assessStartLoading = ref(false)
const assessTaskInfo = ref(null)
const assessTaskId = ref(null)
const assessTaskRunning = ref(false)
const assessResult = ref(null)
const assessLogs = ref([])
const assessLogLoading = ref(false)
let assessPollTimer = null
let assessLogTimer = null

const canStartAssess = computed(() => assessForm.value.file_id && assessForm.value.output_name && assessForm.value.prompt_id && assessForm.value.model && !assessTaskRunning.value)

const assessProgressPercent = computed(() => {
  if (!assessTaskInfo.value || assessTaskInfo.value.progress_total === 0) return 0
  return Math.round((assessTaskInfo.value.progress_current / assessTaskInfo.value.progress_total) * 100)
})
const assessProgressStatus = computed(() => {
  if (!assessTaskInfo.value) return ''
  if (assessTaskInfo.value.status === 'completed') return 'success'
  if (assessTaskInfo.value.status === 'failed') return 'exception'
  return ''
})
const assessStatusTagType = computed(() => {
  if (!assessTaskInfo.value) return 'info'
  const s = assessTaskInfo.value.status
  if (s === 'running') return 'primary'
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
})
const assessStatusLabel = computed(() => {
  if (!assessTaskInfo.value) return ''
  const map = { running: '运行中', completed: '已完成', failed: '失败' }
  return map[assessTaskInfo.value.status] || assessTaskInfo.value.status
})

function handleAssessLLMConfigChange(configId) {
  const cfg = assessLLMConfigs.value.find(c => c.id === configId)
  assessForm.value.model = cfg?.default_model || ''
}

// ---- Split functions ----
async function fetchSplitFileOptions() {
  try { const res = await getManagedFiles(); splitFileOptions.value = res.items || [] }
  catch { ElMessage.error('获取文件列表失败') }
}
function onSplitFileUploadSuccess() { fetchSplitFileOptions() }

async function handleStartSplit() {
  if (!canStartSplit.value) return
  splitStartLoading.value = true
  try {
    const res = await startDatasetSplit({
      file_id: splitForm.value.file_id,
      test_count: splitForm.value.test_count,
      output_name: splitForm.value.output_name,
      split_strategy: splitForm.value.split_strategy,
    })
    splitTaskId.value = res.task_id
    splitTaskRunning.value = true
    await pollSplitStatus()
    startSplitPolling()
    ElMessage.success('切分任务已启动')
  } catch (err) { ElMessage.error(err.response?.data?.detail || '启动切分失败') }
  finally { splitStartLoading.value = false }
}

async function pollSplitStatus() {
  if (!splitTaskId.value) return
  try {
    const res = await getDatasetSplitStatus(splitTaskId.value)
    splitTaskInfo.value = res
    splitTaskRunning.value = res.status === 'running'
    if (res.status === 'completed' || res.status === 'failed') {
      stopSplitPolling()
      splitTaskRunning.value = false
      if (res.status === 'completed') await loadSplitResult()
    }
  } catch (err) { console.error('Poll split error:', err) }
}

async function loadSplitResult() {
  try {
    const logsRes = await getTaskLogs(splitTaskId.value)
    const logItems = Array.isArray(logsRes) ? logsRes : []
    const resultLog = logItems.find(l => l.log_content && l.log_content.includes('切分完成'))
    if (resultLog) {
      // Parse: "切分完成: 测试集 X 条, 训练集 Y 条, 跳过非QA Z 条 | 测试集题型: 单选=3, ... | 训练集题型: ..."
      const mainMatch = resultLog.log_content.match(/测试集 (\d+) 条, 训练集 (\d+) 条, 跳过非QA (\d+) 条/)
      const testTaskMatch = resultLog.log_content.match(/测试集题型: ([^|]+)/)
      const trainTaskMatch = resultLog.log_content.match(/训练集题型: ([^\n|]+)/)
      if (mainMatch) {
        splitResult.value = {
          test_count: parseInt(mainMatch[1]),
          train_count: parseInt(mainMatch[2]),
          skipped_non_qa: parseInt(mainMatch[3]),
          test_task_counts: testTaskMatch ? testTaskMatch[1].trim() : '',
          train_task_counts: trainTaskMatch ? trainTaskMatch[1].trim() : '',
        }
      }
    }
  } catch (err) { console.error('Load split result error:', err) }
}

async function fetchSplitLogs() {
  if (!splitTaskId.value) return
  splitLogLoading.value = true
  try { const res = await getTaskLogs(splitTaskId.value); splitLogs.value = Array.isArray(res) ? res : [] }
  catch { console.error('Fetch logs error:') }
  finally { splitLogLoading.value = false }
}

function startSplitPolling() {
  stopSplitPolling()
  splitPollTimer = setInterval(() => pollSplitStatus(), 3000)
  splitLogTimer = setInterval(() => fetchSplitLogs(), 5000)
}
function stopSplitPolling() {
  if (splitPollTimer) { clearInterval(splitPollTimer); splitPollTimer = null }
  if (splitLogTimer) { clearInterval(splitLogTimer); splitLogTimer = null }
}

// ---- Assessment functions ----
async function fetchAssessFileOptions() {
  try { const res = await getManagedFiles(); assessFileOptions.value = res.items || [] }
  catch { ElMessage.error('获取文件列表失败') }
}
function onAssessFileUploadSuccess() { fetchAssessFileOptions() }

async function fetchAssessPrompts() {
  try { const res = await getPromptConfigs({ stage: 'dataset_assessment' }); assessPromptOptions.value = Array.isArray(res) ? res : [] }
  catch { ElMessage.error('获取Prompt列表失败') }
}

async function fetchAssessLLMConfigs() {
  try { const res = await getLLMConfigs(); assessLLMConfigs.value = Array.isArray(res) ? res : [] }
  catch { ElMessage.error('获取LLM配置失败') }
}

async function handleStartAssess() {
  if (!canStartAssess.value) return
  assessStartLoading.value = true
  try {
    const res = await startDatasetAssessment({
      file_id: assessForm.value.file_id,
      output_name: assessForm.value.output_name,
      prompt_id: assessForm.value.prompt_id,
      model: assessForm.value.model,
      llm_config_id: selectedAssessLLMConfigId.value || null,
    })
    assessTaskId.value = res.task_id
    assessTaskRunning.value = true
    await pollAssessStatus()
    startAssessPolling()
    ElMessage.success('评分标准生成任务已启动')
  } catch (err) { ElMessage.error(err.response?.data?.detail || '启动评分生成失败') }
  finally { assessStartLoading.value = false }
}

async function pollAssessStatus() {
  if (!assessTaskId.value) return
  try {
    const res = await getDatasetAssessmentStatus(assessTaskId.value)
    assessTaskInfo.value = res
    assessTaskRunning.value = res.status === 'running'
    if (res.status === 'completed' || res.status === 'failed') {
      stopAssessPolling()
      assessTaskRunning.value = false
      if (res.status === 'completed') await loadAssessResult()
    }
  } catch (err) { console.error('Poll assess error:', err) }
}

async function loadAssessResult() {
  try {
    const logsRes = await getTaskLogs(assessTaskId.value)
    const logItems = Array.isArray(logsRes) ? logsRes : []
    const resultLog = logItems.find(l => l.log_content && l.log_content.includes('评分标准生成完成'))
    if (resultLog) {
      assessResult.value = { qa_items: 0, short_answer_items: 0, generated: 0, empty_assessment: 0 }
      const match = resultLog.log_content.match(/简答题 (\d+) 条, 成功 (\d+) 条, 空 (\d+) 条/)
      if (match) {
        assessResult.value.short_answer_items = parseInt(match[1])
        assessResult.value.generated = parseInt(match[2])
        assessResult.value.empty_assessment = parseInt(match[3])
      }
    }
  } catch (err) { console.error('Load assess result error:', err) }
}

async function fetchAssessLogs() {
  if (!assessTaskId.value) return
  assessLogLoading.value = true
  try { const res = await getTaskLogs(assessTaskId.value); assessLogs.value = Array.isArray(res) ? res : [] }
  catch { console.error('Fetch logs error:') }
  finally { assessLogLoading.value = false }
}

function startAssessPolling() {
  stopAssessPolling()
  assessPollTimer = setInterval(() => pollAssessStatus(), 3000)
  assessLogTimer = setInterval(() => fetchAssessLogs(), 5000)
}
function stopAssessPolling() {
  if (assessPollTimer) { clearInterval(assessPollTimer); assessPollTimer = null }
  if (assessLogTimer) { clearInterval(assessLogTimer); assessLogTimer = null }
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function restoreSplitTaskState() {
  try {
    const tasks = await getTaskList({ stage: 'dataset_split' })
    if (!Array.isArray(tasks) || tasks.length === 0) return
    const runningTask = tasks.find(t => t.status === 'running')
    const latestTask = runningTask || tasks[0]
    splitTaskId.value = latestTask.id
    splitTaskRunning.value = latestTask.status === 'running'
    await pollSplitStatus()
    await fetchSplitLogs()
    if (latestTask.status === 'running') startSplitPolling()
    if (latestTask.status === 'completed') await loadSplitResult()
  } catch (err) { console.error('Restore split task error:', err) }
}

async function restoreAssessTaskState() {
  try {
    const tasks = await getTaskList({ stage: 'dataset_assessment' })
    if (!Array.isArray(tasks) || tasks.length === 0) return
    const runningTask = tasks.find(t => t.status === 'running')
    const latestTask = runningTask || tasks[0]
    assessTaskId.value = latestTask.id
    assessTaskRunning.value = latestTask.status === 'running'
    await pollAssessStatus()
    await fetchAssessLogs()
    if (latestTask.status === 'running') startAssessPolling()
    if (latestTask.status === 'completed') await loadAssessResult()
  } catch (err) { console.error('Restore assess task error:', err) }
}

onMounted(async () => {
  await Promise.all([
    fetchSplitFileOptions(),
    fetchAssessFileOptions(),
    fetchAssessPrompts(),
    fetchAssessLLMConfigs(),
  ])
  await Promise.all([restoreSplitTaskState(), restoreAssessTaskState()])
})

onUnmounted(() => { stopSplitPolling(); stopAssessPolling() })
</script>

<style scoped>
.page-container { max-width: 1200px }
.page-container h2 { margin-bottom: 16px }
.section-card { margin-bottom: 20px }
.card-title { font-size: 16px; font-weight: 600 }
.config-layout { display: flex; gap: 24px }
.config-form { flex: 3; min-width: 0 }
.config-result { flex: 2; min-width: 0 }

.progress-area { padding: 8px 0 }
.result-stats { padding: 16px }
.stat-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ebeef5 }
.stat-item:last-of-type { border-bottom: none }
.stat-label { color: #606266; font-size: 14px }
.stat-value { color: #303133; font-size: 14px; font-weight: 600 }
.result-empty { text-align: center; color: #909399; padding: 40px }

.log-card { margin-bottom: 20px }
.log-area { max-height: 300px; overflow-y: auto; padding: 8px; background: #f5f7fa; border-radius: 4px }
.log-empty { text-align: center; color: #909399; padding: 20px }
.log-item { padding: 6px 0; border-bottom: 1px solid #ebeef5; display: flex; gap: 12px }
.log-item:last-child { border-bottom: none }
.log-time { color: #909399; font-size: 12px; white-space: nowrap; min-width: 140px }
.log-content { color: #303133; font-size: 13px; word-break: break-all }
</style>