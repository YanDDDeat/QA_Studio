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
        empty-text="暂无运行中或已暂停的任务"
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
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running'"
              type="warning"
              size="small"
              @click="handleStop(row.task_id)"
            >
              暂停
            </el-button>
            <el-button
              v-if="row.status === 'paused'"
              type="primary"
              size="small"
              @click="handleResume(row.task_id)"
            >
              恢复
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
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMyRunningTasks, getTasks, stopTask, resumeTask } from '../api'

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

async function handleResume(taskId) {
  try {
    await resumeTask(taskId)
    ElMessage.success('任务已恢复')
    fetchRunning()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '恢复失败')
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
