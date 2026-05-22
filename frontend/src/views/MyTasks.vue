<template>
  <div class="page-container">
    <h2>我的任务</h2>

    <!-- 运行中的任务 -->
    <el-card class="section-card">
      <template #header>
        <span class="card-title">运行中的任务</span>
      </template>
      <el-table
        :data="runningTasks"
        style="width: 100%"
        v-loading="runningLoading"
        empty-text="暂无运行中的任务"
      >
        <el-table-column label="阶段" width="140">
          <template #default="{ row }">
            {{ stageLabels[row.stage] || row.stage }}
          </template>
        </el-table-column>
        <el-table-column label="输入文件" min-width="160">
          <template #default="{ row }">
            {{ row.filename || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType[row.status]" size="small">
              {{ statusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress_total ? Math.round(row.progress_current / row.progress_total * 100) : 0"
              :format="() => `${row.progress_current}/${row.progress_total}`"
            />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running'"
              type="warning"
              size="small"
              @click="handleStop(row.task_id)"
            >
              暂停
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 历史任务 -->
    <el-card class="section-card" style="margin-top: 20px;">
      <template #header>
        <div class="history-header">
          <span class="card-title">历史任务</span>
          <div class="history-filters">
            <el-select
              v-model="historyStage"
              placeholder="全部阶段"
              clearable
              style="width: 160px; margin-right: 12px;"
              @change="handleFilterChange"
            >
              <el-option
                v-for="(label, value) in stageLabels"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
            <el-select
              v-model="historyStatus"
              placeholder="全部状态"
              clearable
              style="width: 130px;"
              @change="handleFilterChange"
            >
              <el-option
                v-for="(label, value) in statusLabels"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </div>
        </div>
      </template>
      <el-table
        :data="historyTasks"
        style="width: 100%"
        v-loading="historyLoading"
        empty-text="暂无任务记录"
      >
        <el-table-column label="阶段" width="140">
          <template #default="{ row }">
            {{ stageLabels[row.stage] || row.stage }}
          </template>
        </el-table-column>
        <el-table-column label="输入文件" min-width="160">
          <template #default="{ row }">
            {{ row.filename || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType[row.status]" size="small">
              {{ statusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress_total ? Math.round(row.progress_current / row.progress_total * 100) : 0"
              :format="() => `${row.progress_current}/${row.progress_total}`"
            />
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">
            {{ row.updated_at ? new Date(row.updated_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'paused'"
              type="primary"
              size="small"
              @click="openConfigDialog(row, 'resume')"
            >
              恢复
            </el-button>
            <el-button
              v-if="row.status === 'failed' && stageSlugMap[row.stage]"
              type="warning"
              size="small"
              @click="openConfigDialog(row, 'retry')"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="historyPage"
          v-model:page-size="historyPageSize"
          :total="historyTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchHistory"
          @size-change="handlePageSizeChange"
        />
      </div>
    </el-card>

    <!-- 配置弹窗 -->
    <el-dialog
      v-model="configDialogVisible"
      :title="configAction === 'retry' ? '重试任务配置' : '恢复任务配置'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="阶段">
          <el-tag type="info">{{ stageLabels[configTask?.stage] || configTask?.stage }}</el-tag>
        </el-form-item>
        <el-form-item label="LLM配置">
          <el-select
            v-model="configLLMConfigId"
            placeholder="选择LLM配置"
            style="width: 100%"
            filterable
            @change="handleLLMConfigChange"
          >
            <el-option
              v-for="cfg in llmConfigs"
              :key="cfg.id"
              :label="cfg.name + (cfg.user_id ? ' (我的)' : ' (全局)')"
              :value="cfg.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select
            v-model="configModel"
            placeholder="请选择模型"
            style="width: 100%"
            :disabled="!configLLMConfigId"
          >
            <el-option v-for="m in currentModelOptions" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="提示词">
          <el-select
            v-model="configPromptId"
            placeholder="选择提示词"
            style="width: 100%"
            filterable
            v-loading="promptsLoading"
          >
            <el-option
              v-for="p in configPromptOptions"
              :key="p.id"
              :label="p.name || `v${p.version}`"
              :value="p.id"
            >
              <span>{{ p.name || `v${p.version}` }}{{ p.is_default ? '(默认)' : '' }}</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="configSubmitting" @click="submitConfig">
          确认{{ configAction === 'retry' ? '重试' : '恢复' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMyRunningTasks, getTasks, stopTask, resumeTask, retryStage, getPromptConfigs, getLLMConfigs } from '../api'

// ---------- 常量映射 ----------
const stageLabels = {
  question_generate: '问题生成',
  knowledge_generate: '知识体系',
  question_validate: '问题校验',
  answer_generate: '答案生成',
  answer_validate: '答案校验',
  data_evaluate: '数据评估',
  cot_filter: 'COT过滤',
  dataset_split: '数据集切分',
  dataset_assessment: '评分标准生成',
}

const statusLabels = {
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  pending: '等待中',
}

const statusTagType = {
  running: 'primary',
  paused: 'warning',
  completed: 'success',
  failed: 'danger',
  pending: 'info',
}

const stageSlugMap = {
  question_generate: 'question-generate',
  knowledge_generate: 'knowledge-generate',
  question_validate: 'question-validate',
  answer_generate: 'answer-generate',
  answer_validate: 'answer-validate',
  data_evaluate: 'data-evaluate',
}

// ---------- 运行中任务 ----------
const runningTasks = ref([])
const runningLoading = ref(false)
let pollingTimer = null

async function fetchRunning() {
  runningLoading.value = true
  try {
    const res = await getMyRunningTasks()
    runningTasks.value = Array.isArray(res) ? res : []
  } catch {
    // 静默处理
  } finally {
    runningLoading.value = false
  }
}

async function handleStop(taskId) {
  try {
    await stopTask(taskId)
    ElMessage.success('任务已暂停')
    fetchRunning()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '暂停失败')
  }
}

// ---------- 配置弹窗 ----------
const configDialogVisible = ref(false)
const configTask = ref(null)
const configAction = ref('')
const configPromptId = ref(null)
const configModel = ref('')
const configPromptOptions = ref([])
const promptsLoading = ref(false)
const configSubmitting = ref(false)
const llmConfigs = ref([])
const configLLMConfigId = ref(null)
const currentModelOptions = computed(() => {
  const cfg = llmConfigs.value.find(c => c.id === configLLMConfigId.value)
  return cfg ? (cfg.models || []) : []
})

async function openConfigDialog(row, action) {
  configTask.value = row
  configAction.value = action
  configPromptId.value = row.prompt_id || null
  configModel.value = row.model || ''
  configLLMConfigId.value = null
  configPromptOptions.value = []
  configDialogVisible.value = true

  // 加载 LLM 配置和 prompts
  promptsLoading.value = true
  try {
    const [promptRes, llmRes] = await Promise.all([
      getPromptConfigs({ stage: row.stage }),
      getLLMConfigs(),
    ])
    configPromptOptions.value = Array.isArray(promptRes) ? promptRes : []
    llmConfigs.value = Array.isArray(llmRes) ? llmRes : []

    // 根据当前 model 反查匹配的厂商
    if (row.model) {
      const matched = llmConfigs.value.find(c => (c.models || []).includes(row.model))
      if (matched) {
        configLLMConfigId.value = matched.id
      }
    }
  } catch {
    configPromptOptions.value = []
    llmConfigs.value = []
  } finally {
    promptsLoading.value = false
  }
}

function handleLLMConfigChange(cfgId) {
  const cfg = llmConfigs.value.find(c => c.id === cfgId)
  if (cfg) {
    configModel.value = cfg.default_model || ''
  } else {
    configModel.value = ''
  }
}

async function submitConfig() {
  const row = configTask.value
  if (!row) return

  const data = {}
  if (configPromptId.value && configPromptId.value !== row.prompt_id) {
    data.prompt_id = configPromptId.value
  }
  if (configModel.value && configModel.value !== row.model) {
    data.model = configModel.value
  }
  if (configLLMConfigId.value) {
    data.llm_config_id = configLLMConfigId.value
  }

  configSubmitting.value = true
  try {
    if (configAction.value === 'retry') {
      const slug = stageSlugMap[row.stage]
      if (!slug) return
      await retryStage(slug, row.id, Object.keys(data).length > 0 ? data : undefined)
      ElMessage.success('重试任务已启动')
    } else {
      await resumeTask(row.id, Object.keys(data).length > 0 ? data : undefined)
      ElMessage.success('任务已恢复')
    }
    configDialogVisible.value = false
    fetchRunning()
    fetchHistory()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    configSubmitting.value = false
  }
}

// ---------- 历史任务 ----------
const historyTasks = ref([])
const historyLoading = ref(false)
const historyStage = ref('')
const historyStatus = ref('')
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyTotal = ref(0)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const params = { page: historyPage.value, page_size: historyPageSize.value }
    if (historyStage.value) params.stage = historyStage.value
    if (historyStatus.value) params.task_status = historyStatus.value
    const res = await getTasks(params)
    historyTasks.value = Array.isArray(res.items) ? res.items : []
    historyTotal.value = res.total || 0
  } catch {
    // 静默处理
  } finally {
    historyLoading.value = false
  }
}

function handlePageSizeChange() {
  historyPage.value = 1
  fetchHistory()
}

function handleFilterChange() {
  historyPage.value = 1
  fetchHistory()
}

// ---------- 生命周期 ----------
onMounted(() => {
  fetchRunning()
  fetchHistory()
  pollingTimer = setInterval(fetchRunning, 5000)
})

onUnmounted(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
})
</script>

<style scoped>
.page-container {
  /* 与其他页面一致 */
}

.section-card {
  margin-bottom: 0;
}

.card-title {
  font-weight: 600;
  font-size: 15px;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-filters {
  display: flex;
  align-items: center;
}
</style>
