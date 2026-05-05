<template>
  <div class="page-container">
    <h2>数据中心</h2>
    <p class="page-intro">以 JSON 文件为整体单位查看数据，点击文件预览其内容。</p>

    <!-- File list -->
    <el-card class="file-list-card">
      <div class="file-list-header">
        <span class="file-count">共 {{ fileTotal }} 个文件</span>
        <div class="file-list-controls">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索文件名"
            clearable
            size="small"
            style="width: 180px"
            @input="onSearchChange"
          />
          <el-select v-model="sortMode" size="small" style="width: 140px" @change="fetchFiles">
            <el-option label="最新优先" value="time_desc" />
            <el-option label="最早优先" value="time_asc" />
            <el-option label="文件名排序" value="name_asc" />
          </el-select>
          <el-button type="primary" size="small" @click="fetchFiles">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="pagedFiles"
        v-loading="loading"
        stripe
        highlight-current-row
        @current-change="handleFileSelect"
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column label="来源阶段" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.source_stage" size="small" :type="stageTagType(row.source_stage)">
              {{ stageLabel(row.source_stage) }}
            </el-tag>
            <span v-else class="empty-field">上传文件</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="handleFileSelect(row)">
              查看
            </el-button>
            <el-button type="success" link size="small" @click.stop="handleDownload(row)">
              下载
            </el-button>
            <el-button type="danger" link size="small" @click.stop="handleDeleteFile(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="file-pagination">
        <el-pagination
          v-model:current-page="filePage"
          :page-size="10"
          :total="fileTotal"
          layout="total, prev, pager, next"
          @current-change="fetchFiles"
        />
      </div>
    </el-card>

    <!-- File content preview -->
    <el-card v-if="selectedFile" class="preview-card">
      <div class="preview-header">
        <div class="preview-title">
          <h3>{{ selectedFile.filename }}</h3>
          <span v-if="previewData" class="preview-meta">
            {{ previewData.total_records }} 条记录
          </span>
        </div>
        <el-button type="success" size="small" @click="handleDownload(selectedFile)">下载文件</el-button>
      </div>

      <!-- Record filter controls -->
      <div v-if="filterOptions" class="record-filter-bar">
        <el-select
          v-model="filterTaskType"
          placeholder="题型"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="t in filterOptions.task_types" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select
          v-model="filterDomain"
          placeholder="领域"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="d in filterOptions.domains" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select
          v-model="filterDifficulty"
          placeholder="难度"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="d in filterOptions.difficulties" :key="d" :label="d" :value="d" />
        </el-select>
      </div>

      <div v-loading="previewLoading" class="preview-content">
        <template v-if="previewData && previewData.preview && previewData.preview.length">
          <el-table
            :data="previewData.preview"
            stripe
            border
            size="small"
            style="width: 100%"
          >
            <el-table-column prop="id" label="ID" width="50" />
            <el-table-column prop="input" label="问题(input)" min-width="180" show-overflow-tooltip />
            <el-table-column prop="output" label="答案(output)" min-width="180" show-overflow-tooltip />
            <el-table-column prop="domain" label="领域" width="80" show-overflow-tooltip />
            <el-table-column prop="difficulty" label="难度" width="70" />
            <el-table-column prop="source" label="来源" width="100" show-overflow-tooltip />
            <el-table-column label="操作" width="70" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleRecordSelect(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="preview-pagination">
            <el-pagination
              v-model:current-page="previewPage"
              :page-size="10"
              :total="previewData.total_records"
              layout="total, prev, pager, next"
              @current-change="loadPreview"
            />
          </div>
        </template>

        <div v-else-if="previewData && (!previewData.preview || !previewData.preview.length)" class="empty-field">
          文件内容为空
        </div>
      </div>
    </el-card>

    <!-- Record detail — rendered directly below the preview -->
    <el-card v-if="selectedRecord" class="detail-card">
      <div class="detail-header">
        <h3>记录详情 #{{ selectedRecord.id || '-' }}</h3>
      </div>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="id">{{ selectedRecord.id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="domain">{{ selectedRecord.domain || '-' }}</el-descriptions-item>
        <el-descriptions-item label="category">{{ selectedRecord.category || '-' }}</el-descriptions-item>
        <el-descriptions-item label="task_type">{{ selectedRecord.task_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="source">{{ selectedRecord.source || '-' }}</el-descriptions-item>
        <el-descriptions-item label="source_type">{{ selectedRecord.source_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="source_id">{{ selectedRecord.source_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="difficulty">{{ selectedRecord.difficulty || '-' }}</el-descriptions-item>
        <el-descriptions-item label="corpus_cate">{{ selectedRecord.corpus_cate ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="scene">{{ selectedRecord.scene || '-' }}</el-descriptions-item>
        <el-descriptions-item label="score">{{ selectedRecord.score ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="relevance">{{ selectedRecord.relevance ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="clarity">{{ selectedRecord.clarity ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="reasoning">{{ selectedRecord.reasoning ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="terminology">{{ selectedRecord.terminology ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Assessment">{{ selectedRecord.Assessment || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-text-fields">
        <div class="text-field-block" v-if="selectedRecord.input">
          <div class="field-label">问题 (Input)</div>
          <div class="field-content" v-html="renderContent(selectedRecord.input)"></div>
        </div>
        <div class="text-field-block" v-if="selectedRecord.output">
          <div class="field-label">答案 (Output)</div>
          <div class="field-content" v-html="renderContent(selectedRecord.output)"></div>
        </div>
        <div class="text-field-block" v-if="selectedRecord.cot">
          <div class="field-label">思维链 (CoT)</div>
          <div class="field-content" v-html="renderContent(selectedRecord.cot)"></div>
        </div>
        <div class="text-field-block" v-if="selectedRecord.originContent">
          <div class="field-label">原始内容 (Origin Content)</div>
          <div class="field-content" v-html="renderContent(selectedRecord.originContent)"></div>
        </div>
        <div class="text-field-block" v-if="selectedRecord.knowledge">
          <div class="field-label">知识 (Knowledge)</div>
          <div class="field-content" v-html="renderKnowledge(selectedRecord.knowledge)"></div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import katex from 'katex'
import {
  getManagedFiles,
  getManagedFileContent,
  downloadManagedFile,
  deleteManagedFile,
} from '../api'

const STAGE_MAP = {
  question_generate: '问题生成',
  knowledge_generate: '知识体系生成',
  question_validate: '问题校验',
  answer_generate: '答案生成',
  answer_validate: '答案校验',
  data_evaluate: '数据评估',
}

// File list state
const loading = ref(false)
const files = ref([])
const fileTotal = ref(0)
const filePage = ref(1)
const route = useRoute()
const searchKeyword = ref('')
const sortMode = ref('time_desc')

// Computed: current page slice (backend now paginated, so files already is the page slice)
const pagedFiles = computed(() => files.value)

// File preview state
const selectedFile = ref(null)
const previewLoading = ref(false)
const previewData = ref(null)
const previewPage = ref(1)
const filterOptions = ref(null)
const filterTaskType = ref(null)
const filterDomain = ref(null)
const filterDifficulty = ref(null)

// Record detail state (inline, no dialog)
const selectedRecord = ref(null)

function stageLabel(stage) {
  if (!stage) return '-'
  return STAGE_MAP[stage] || stage
}

function stageTagType(stage) {
  const map = {
    question_generate: '',
    knowledge_generate: 'warning',
    question_validate: 'success',
    answer_generate: '',
    answer_validate: 'success',
    data_evaluate: 'info',
  }
  return map[stage] || ''
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

let searchTimer = null
function onSearchChange() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    filePage.value = 1
    fetchFiles()
  }, 300)
}

async function fetchFiles() {
  loading.value = true
  try {
    const params = {
      page: filePage.value,
      page_size: 10,
      sort: sortMode.value,
    }
    if (searchKeyword.value) params.search = searchKeyword.value
    const res = await getManagedFiles(params)
    files.value = res.items || []
    fileTotal.value = res.total || 0
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    files.value = []
    fileTotal.value = 0
  } finally {
    loading.value = false
  }
}

function handleFileSelect(row) {
  if (row) {
    selectedFile.value = row
    previewPage.value = 1
    selectedRecord.value = null
    // Reset filters when selecting a new file
    filterTaskType.value = null
    filterDomain.value = null
    filterDifficulty.value = null
    loadPreview()
  }
}

async function loadPreview() {
  previewLoading.value = true
  previewData.value = null
  try {
    const params = {
      page: previewPage.value,
      page_size: 10,
    }
    if (filterTaskType.value) params.task_type = filterTaskType.value
    if (filterDomain.value) params.domain = filterDomain.value
    if (filterDifficulty.value) params.difficulty = filterDifficulty.value
    const res = await getManagedFileContent(selectedFile.value.id, params)
    previewData.value = res
    filterOptions.value = res.filter_options || null
  } catch (err) {
    const detail = err.response?.data?.detail || '预览文件内容失败'
    ElMessage.error(detail)
    previewData.value = null
  } finally {
    previewLoading.value = false
  }
}

function handleRecordSelect(row) {
  selectedRecord.value = row || null
}

async function handleDownload(row) {
  try {
    const blob = await downloadManagedFile(row.id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error('下载文件失败')
  }
}

async function handleDeleteFile(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 "${row.filename}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteManagedFile(row.id)
    ElMessage.success('已删除')
    // Clear preview if deleted file was selected
    if (selectedFile.value && selectedFile.value.id === row.id) {
      selectedFile.value = null
      previewData.value = null
      selectedRecord.value = null
    }
    await fetchFiles()
  } catch (err) {
    const detail = err.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}

// ---------- LaTeX / content rendering ----------

function renderLatex(text) {
  if (!text) return ''
  let html = text

  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return match
    }
  })

  html = html.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return match
    }
  })

  return html
}

function renderContent(text) {
  if (!text) return '<span class="empty-field">-</span>'
  let html = escapeHtml(text)
  html = renderLatex(html)
  html = html.replace(/\n/g, '<br>')
  return html
}

function renderKnowledge(knowledge) {
  if (!knowledge) return '<span class="empty-field">-</span>'
  if (typeof knowledge === 'string') return renderContent(knowledge)
  try {
    const formatted = JSON.stringify(knowledge, null, 2)
    return '<pre class="knowledge-json">' + escapeHtml(formatted) + '</pre>'
  } catch {
    return String(knowledge)
  }
}

function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

onMounted(async () => {
  await fetchFiles()
  // Auto-select file if file_id is in URL query params
  const fileId = route.query.file_id
  if (fileId) {
    const id = parseInt(fileId)
    const match = files.value.find(f => f.id === id)
    if (match) {
      selectedFile.value = match
      previewPage.value = 1
      selectedRecord.value = null
      loadPreview()
    } else {
      // File might be on a different page — search through all pages
      await autoSelectFile(id)
    }
  }
})

async function autoSelectFile(targetId) {
  const totalPages = Math.ceil(fileTotal.value / 10)
  for (let p = 1; p <= totalPages; p++) {
    filePage.value = p
    await fetchFiles()
    const match = files.value.find(f => f.id === targetId)
    if (match) {
      selectedFile.value = match
      previewPage.value = 1
      selectedRecord.value = null
      loadPreview()
      return
    }
  }
  ElMessage.warning('未找到指定文件')
}
</script>

<style scoped>
@import 'katex/dist/katex.min.css';

.page-container {}
.page-container h2 {
  margin-bottom: 8px;
}
.page-intro {
  color: #606266;
  font-size: 14px;
  margin-bottom: 16px;
}

.file-list-card {
  margin-bottom: 16px;
}
.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.file-list-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.file-count {
  color: #909399;
  font-size: 13px;
}
.file-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.preview-card {
  margin-bottom: 16px;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.preview-title h3 {
  margin: 0;
  font-size: 16px;
}
.preview-meta {
  color: #909399;
  font-size: 13px;
  margin-left: 12px;
}
.record-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.preview-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.detail-card {
  margin-bottom: 16px;
}
.detail-header h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
}
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
.knowledge-json {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  background: transparent;
}
</style>